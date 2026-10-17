"""Bounded upload admission, off-loop processing and cooperative cancellation."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import logging
import os
import secrets
import tempfile
import threading
import time

import fitz
from fastapi import HTTPException
from prometheus_client import Histogram, Counter
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from chunking import chunk_text

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_BODY_BYTES = MAX_FILE_BYTES + 65536
MAX_PAGES = 300
MAX_TEXT = 1_000_000
MAX_PAGE_TEXT = 100_000
MAX_CHUNKS = 1500
BODY_SECONDS = 15
PROCESSING_SECONDS = 90
STAGE_SECONDS = Histogram('doclens_upload_stage_seconds', 'Upload stage duration', ['stage'])
FAILURES = Counter('doclens_upload_failures_total', 'Upload failures', ['stage', 'kind'])
logger = logging.getLogger('doclens')
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='doclens-upload')
_admission = threading.BoundedSemaphore(1)


class Lease:
    transferred = False
    def __init__(self):
        self.lock = threading.Lock()
        self.released = False
    def release(self):
        with self.lock:
            if not self.released:
                self.released = True
                _admission.release()


class UploadGate:
    """Authenticate/admit before multipart parsing; spool at most one bounded body."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST' or scope['path'] not in ('/documents/process', '/documents/extract'):
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        secret = os.getenv('DOCLENS_SESSION_SECRET', '').encode()
        supplied = headers.get(b'x-doclens-internal-key', b'')
        async def error(status, detail):
            await JSONResponse({'detail': detail}, status_code=status)(scope, receive, send)
        if not secret:
            return await error(503, 'Backend authentication is not configured.')
        if not supplied or not secrets.compare_digest(secret, supplied):
            return await error(401, 'Unauthorized.')
        if not _admission.acquire(blocking=False):
            return await error(429, 'Another PDF is processing. Try again when it finishes.')
        lease = Lease()
        scope.setdefault('state', {})['upload_lease'] = lease
        try:
            length = headers.get(b'content-length')
            if length is not None:
                try:
                    size = int(length)
                    if size < 0: raise ValueError()
                except ValueError:
                    return await error(400, 'Invalid content length.')
                if size > MAX_BODY_BYTES:
                    return await error(413, 'PDF upload exceeds the 32 MiB limit.')
            with tempfile.SpooledTemporaryFile(max_size=1024*1024) as body:
                started = time.monotonic()
                total = 0
                while True:
                    remaining = BODY_SECONDS - (time.monotonic() - started)
                    if remaining <= 0:
                        return await error(408, 'Upload transfer timed out.')
                    try:
                        message = await asyncio.wait_for(receive(), remaining)
                    except asyncio.TimeoutError:
                        return await error(408, 'Upload transfer timed out.')
                    if message['type'] == 'http.disconnect':
                        return
                    data = message.get('body', b'')
                    total += len(data)
                    if total > MAX_BODY_BYTES:
                        return await error(413, 'PDF upload exceeds the 32 MiB limit.')
                    await run_in_threadpool(body.write, data)
                    if not message.get('more_body', False):
                        break
                STAGE_SECONDS.labels('transfer').observe(time.monotonic() - started)
                await run_in_threadpool(body.seek, 0)
                delivered = False
                async def replay():
                    nonlocal delivered
                    if delivered:
                        return await receive()
                    data = await run_in_threadpool(body.read, 65536)
                    if not data:
                        delivered = True
                    return {'type': 'http.request', 'body': data, 'more_body': not delivered}
                await self.app(scope, replay, send)
        finally:
            if not lease.transferred:
                lease.release()


@dataclass
class Budget:
    deadline: float = field(default_factory=lambda: time.monotonic()+PROCESSING_SECONDS)
    cancelled: threading.Event = field(default_factory=threading.Event)
    stage: str = 'extraction'
    stage_started: float = field(default_factory=time.monotonic)
    def check(self):
        if self.cancelled.is_set() or time.monotonic() >= self.deadline:
            raise HTTPException(504, 'PDF processing timed out or was cancelled before publication.')
    def enter(self, name):
        STAGE_SECONDS.labels(self.stage).observe(time.monotonic()-self.stage_started)
        self.stage = name
        self.stage_started = time.monotonic()
        self.check()


def extract(data, budget):
    budget.check()
    try:
        document = fitz.open(stream=data, filetype='pdf')
    except Exception:
        raise HTTPException(400, 'Could not read this PDF.') from None
    with document:
        if document.is_encrypted:
            raise HTTPException(400, 'Encrypted PDFs are not supported.')
        if len(document) > MAX_PAGES:
            raise HTTPException(413, f'PDF exceeds the {MAX_PAGES}-page processing limit.')
        pages = []
        total = 0
        for index, page in enumerate(document, 1):
            budget.check()
            text = page.get_text('text')
            total += len(text)
            if len(text) > MAX_PAGE_TEXT or total > MAX_TEXT:
                raise HTTPException(413, 'PDF exceeds the extracted-text processing limit.')
            pages.append({'page_number': index, 'text': text})
        return pages


def work(data, name, budget, extract_only):
    try:
        pages = extract(data, budget)
        budget.enter('chunking')
        if extract_only:
            return {'filename': name, 'page_count': len(pages), 'pages': pages}
        chunks = []
        for page in pages:
            budget.check()
            for number, text in enumerate(chunk_text(page['text'], 1000, 200), 1):
                chunks.append({'text': text, 'metadata': {'document_name': name,
                    'page_number': page['page_number'], 'chunk_id': f"p{page['page_number']}-c{number}"}})
                if len(chunks) > MAX_CHUNKS:
                    raise HTTPException(413, 'PDF exceeds the chunk processing limit.')
        if not chunks:
            raise HTTPException(400, 'No extractable text was found. Scanned PDFs require OCR, which is not supported.')
        from embeddings import create_embeddings
        from vector_store import replace_document
        budget.enter('embedding')
        vectors = create_embeddings([c['text'] for c in chunks], check=budget.check)
        replace_document(name, chunks, vectors, check=budget.check, stage=budget.enter)
        logger.info('PDF processed | bytes=%d | pages=%d | chunks=%d', len(data), len(pages), len(chunks))
        return {'filename': name, 'total_chunks': len(chunks), 'indexed': True}
    except HTTPException as error:
        FAILURES.labels(budget.stage, 'limit_or_cancel' if error.status_code in (413,504) else 'invalid').inc()
        raise
    except Exception as error:
        FAILURES.labels(budget.stage, 'component').inc()
        logger.warning('PDF processing failed | stage=%s | exception=%s', budget.stage, type(error).__name__)
        raise HTTPException(503, f'PDF {budget.stage} failed. Existing indexed data is retained; retry later.') from None
    finally:
        STAGE_SECONDS.labels(budget.stage).observe(time.monotonic()-budget.stage_started)


async def handle(request, extract_only=False):
    async with request.form(max_files=1, max_fields=0) as form:
        if len(form.multi_items()) != 1 or 'file' not in form:
            raise HTTPException(400, 'Exactly one PDF file is required.')
        file = form['file']
        if getattr(file, 'content_type', None) != 'application/pdf':
            raise HTTPException(400, 'Only PDF files are supported.')
        name = file.filename or 'document.pdf'
        if len(name) > 255 or any(c in name for c in ('\r','\n','\x00')):
            raise HTTPException(400, 'Invalid document filename.')
        data = await file.read(MAX_FILE_BYTES+1)
        if not data or len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, 'PDF must contain 1 byte to 32 MiB.')
    budget = Budget()
    lease = request.state.upload_lease
    future = _pool.submit(work, data, name, budget, extract_only)
    lease.transferred = True
    future.add_done_callback(lambda _: lease.release())
    waiting = asyncio.wrap_future(future)
    waiting.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
    try:
        while True:
            done, _ = await asyncio.wait([waiting], timeout=.1)
            if done:
                return waiting.result()
            if time.monotonic() >= budget.deadline:
                budget.cancelled.set()
                raise HTTPException(504, 'PDF processing exceeded 90 seconds. Retry a smaller document.')
            if await request.is_disconnected():
                budget.cancelled.set()
                raise HTTPException(499, 'Upload cancelled before completion.')
    except asyncio.CancelledError:
        budget.cancelled.set()
        raise
