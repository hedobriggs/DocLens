"""Opt-in, synthetic-data Milestone 1 API. Run platform_api:app, not main:app."""
from contextlib import asynccontextmanager
from datetime import date
import hashlib
import math
import logging
import psycopg
import os
import re
import secrets
from uuid import UUID, uuid4

import fitz
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from psycopg.types.json import Jsonb
from starlette.concurrency import run_in_threadpool

from chunking import chunk_text
from platform_jobs import Jobs
from platform_core import Database, Embeddings, Identity, Originals, password_matches, password_hash, token_hash

MAX_BYTES = 10 * 1024 * 1024


def uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(404, 'Not found.') from None


def scope(conn, kind: str, scope_id: UUID, writing=False):
    if kind not in ('workspaces', 'libraries'):
        raise HTTPException(404, 'Not found.')
    table = 'workspaces' if kind == 'workspaces' else 'libraries'
    row = conn.execute(f'SELECT * FROM platform.{table} WHERE id=%s', (scope_id,)).fetchone()
    args = (scope_id, None) if kind == 'workspaces' else (None, scope_id)
    if not row or not conn.execute('SELECT platform.can_scope(%s,%s,%s) AS allowed', (*args, writing)).fetchone()['allowed']:
        raise HTTPException(404, 'Not found.')
    return row


def version(conn, version_id: UUID):
    row = conn.execute('''SELECT v.*,d.workspace_id,d.library_id FROM platform.versions v
                          JOIN platform.documents d ON d.id=v.document_id WHERE v.id=%s''', (version_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Not found.')
    return row


def audit(conn, action, document_id, version_id):
    conn.execute('INSERT INTO platform.audit_events(document_id,version_id,action) VALUES (%s,%s,%s)',
                 (document_id, version_id, action))


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class Metadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=1000)
    jurisdiction: str = Field(min_length=1, max_length=100)
    effective_date: date | None = None
    received_date: date
    document_id: UUID | None = None
    expected_version_id: UUID | None = None
    synthetic: bool


class Search(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1, max_length=1000)
    mode: str = Field(pattern='^(dense|lexical)$')


def create_app(database=None, originals=None, embeddings=None):
    @asynccontextmanager
    async def lifespan(app):
        own_db = database is None
        if own_db:
            app.state.db = Database(os.environ['PLATFORM_DATABASE_URL'], os.environ['PLATFORM_AUTH_DATABASE_URL'])
            app.state.originals = Originals(endpoint=os.environ['PLATFORM_S3_ENDPOINT'], bucket=os.environ['PLATFORM_S3_BUCKET'],
                                           access_key=os.environ['PLATFORM_S3_ACCESS_KEY'], secret_key=os.environ['PLATFORM_S3_SECRET_KEY'])
        yield
        if own_db:
            app.state.db.close()

    api = FastAPI(title='DocLens Workspace Foundation', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    api.state.db = database
    api.state.originals = originals
    api.state.embeddings = embeddings or Embeddings()
    # Same-workspace publication remains synchronous until Milestone 2.
    import threading
    api.state.admission = threading.BoundedSemaphore(2)
    dummy_hash = password_hash('not-an-account-' + secrets.token_urlsafe(32))

    @api.middleware('http')
    async def authenticate(request: Request, call_next):
        try:
            if request.url.path not in ('/session', '/health') or request.method == 'DELETE':
                value = request.headers.get('authorization', '')
                if not value.startswith('Bearer '):
                    raise HTTPException(401, 'Sign in required.')
                request.state.identity = await run_in_threadpool(api.state.db.identity, value[7:])
            response = await call_next(request)
        except HTTPException as exc:
            response = JSONResponse({'detail':exc.detail}, status_code=exc.status_code)
        except psycopg.errors.InsufficientPrivilege:
            response = JSONResponse({'detail':'Not found.'}, status_code=404)
        except psycopg.IntegrityError:
            response = JSONResponse({'detail':'Request conflicts with the current document state.'}, status_code=409)
        except Exception as error:
            # Exception bodies/chains can contain provider, SQL, or object credentials.
            logging.getLogger('doclens.platform').warning('Workspace operation failed (%s)',type(error).__name__)
            response = JSONResponse({'detail':'Workspace service unavailable.'}, status_code=503)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @api.exception_handler(ValidationError)
    async def invalid_input(request, error):
        # Never reflect passwords, scope fields or uploaded text in validation errors.
        return JSONResponse({'detail':'Invalid request.'}, status_code=400)

    @api.get('/health')
    def health():
        return {'status':'ok', 'mode':'synthetic-only-no-provider'}

    @api.post('/session')
    async def login(request: Request):
        raw = await bounded_body(request, 4096)
        credentials = Credentials.model_validate_json(raw)
        def verify():
            email = credentials.email.strip().lower()
            with api.state.db.auth() as conn:
                # Serialize attempts per email. Counters persist across processes/restarts.
                key = token_hash(email)
                conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (key,))
                attempts = conn.execute('''INSERT INTO platform.login_attempts(email_hash,attempts,window_start)
                  VALUES (%s,1,now()) ON CONFLICT(email_hash) DO UPDATE SET
                  attempts=CASE WHEN platform.login_attempts.window_start<now()-interval '10 minutes' THEN 1 ELSE platform.login_attempts.attempts+1 END,
                  window_start=CASE WHEN platform.login_attempts.window_start<now()-interval '10 minutes' THEN now() ELSE platform.login_attempts.window_start END
                  RETURNING attempts''', (key,)).fetchone()['attempts']
                row = conn.execute('SELECT * FROM platform.users WHERE email=%s AND active', (email,)).fetchone()
                good = password_matches(credentials.password, row['password_hash'] if row else dummy_hash)
                if attempts > 10:
                    outcome = (429, None)
                elif not row or not good:
                    outcome = (401, None)
                else:
                    token = secrets.token_urlsafe(32)
                    conn.execute("INSERT INTO platform.sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+interval '8 hours')", (token_hash(token), row['id']))
                    outcome = (200, token)
            return outcome
        status, token = await run_in_threadpool(verify)
        if status != 200:
            raise HTTPException(status, 'Unable to sign in.')
        return {'token':token, 'expires_in':8*3600}

    @api.delete('/session')
    def logout(request: Request):
        with api.state.db.auth() as conn:
            conn.execute('UPDATE platform.sessions SET revoked=true WHERE token_hash=%s', (request.state.identity.token_digest,))
        return Response(status_code=204)

    @api.get('/workspaces')
    def workspaces(request: Request):
        with api.state.db.transaction(request.state.identity) as conn:
            return {'workspaces':conn.execute('''SELECT w.*,o.name AS organisation_name,
              platform.can_scope(w.id,NULL,true) AS can_edit FROM platform.workspaces w
              JOIN platform.organisations o ON o.id=w.organisation_id ORDER BY w.name''').fetchall()}

    @api.get('/libraries')
    def libraries(request: Request):
        with api.state.db.transaction(request.state.identity) as conn:
            return {'libraries':conn.execute('SELECT id,name,organisation_id,rights_basis FROM platform.libraries ORDER BY name').fetchall()}

    @api.get('/{kind}/{scope_id}/documents')
    def documents(kind: str, scope_id: str, request: Request):
        with api.state.db.transaction(request.state.identity) as conn:
            scope(conn, kind, uuid(scope_id))
            column = 'workspace_id' if kind == 'workspaces' else 'library_id'
            return {'documents':conn.execute(f'''SELECT id,title,active_version_id FROM platform.documents
                           WHERE {column}=%s ORDER BY title,id''', (uuid(scope_id),)).fetchall()}

    @api.post('/{kind}/{scope_id}/documents')
    async def upload(kind: str, scope_id: str, request: Request):
        identity = request.state.identity
        target = uuid(scope_id)
        # Scope/auth check before multipart parser or any body consumption.
        def admission_check():
            with api.state.db.transaction(identity) as conn:
                scope(conn, kind, target, True)
        await run_in_threadpool(admission_check)
        if not api.state.admission.acquire(blocking=False):
            raise HTTPException(429, 'Upload capacity reached. Try again later.')
        try:
            meta,data,filename=await parse_upload(request)
            return await run_in_threadpool(publish,identity,kind,target,meta,data,filename)
        finally:
            api.state.admission.release()

    @api.post('/{kind}/{scope_id}/ingestions',status_code=202)
    async def enqueue(kind: str, scope_id: str, request: Request):
        if os.getenv('PLATFORM_DURABLE_JOBS_ENABLED')!='1':
            raise HTTPException(404,'Not found.')
        identity=request.state.identity; target=uuid(scope_id)
        def check():
            with api.state.db.transaction(identity) as conn:
                scope(conn,kind,target,True)
        await run_in_threadpool(check)
        key=request.headers.get('idempotency-key','')
        if not re.fullmatch(r'[A-Za-z0-9._:-]{16,128}',key):
            raise HTTPException(400,'A 16–128 character Idempotency-Key is required.')
        if not api.state.admission.acquire(blocking=False):
            raise HTTPException(429,'Upload capacity reached. Try again later.')
        try:
            meta,data,filename=await parse_upload(request)
            jobs=Jobs(api.state.db,api.state.originals)
            return await run_in_threadpool(jobs.submit,identity,kind,target,key,meta,data,filename)
        finally:
            api.state.admission.release()

    @api.get('/jobs/{job_id}')
    def job_status(job_id: str,request: Request):
        if os.getenv('PLATFORM_DURABLE_JOBS_ENABLED')!='1':
            raise HTTPException(404,'Not found.')
        return Jobs(api.state.db,api.state.originals).status(request.state.identity,uuid(job_id))

    def publish(identity, kind, target, meta, data, filename):
        items = []
        try:
            with fitz.open(stream=data, filetype='pdf') as pdf:
                if pdf.needs_pass or not 1 <= len(pdf) <= 100:
                    raise HTTPException(400, 'Use an unencrypted PDF with 1–100 pages.')
                pages = len(pdf)
                for number, page in enumerate(pdf, 1):
                    for text in chunk_text(page.get_text(), chunk_size=1000, overlap=200):
                        items.append((number, text))
                        if len(items)>1000:
                            raise HTTPException(413, 'Document exceeds the 1000-passage limit.')
        except (fitz.FileDataError, fitz.EmptyFileError):
            raise HTTPException(400, 'Could not read this PDF.') from None
        if not items:
            raise HTTPException(400, 'No extractable text. OCR is not implemented.')
        vectors = api.state.embeddings.encode([text for _,text in items])
        if len(vectors)!=len(items) or any(len(v)!=384 or not all(math.isfinite(x) for x in v) for v in vectors):
            raise HTTPException(503, 'Embedding service failed.')
        vid = uuid4()
        docid = meta.document_id or uuid4()
        digest = hashlib.sha256(data).hexdigest()
        with api.state.db.transaction(identity) as conn:
            selected_scope = scope(conn, kind, target, True)
            if meta.document_id:
                document = conn.execute('SELECT * FROM platform.documents WHERE id=%s FOR UPDATE', (docid,)).fetchone()
                column = 'workspace_id' if kind == 'workspaces' else 'library_id'
                if not document or document[column] != target:
                    raise HTTPException(404, 'Not found.')
                if meta.expected_version_id != document['active_version_id']:
                    raise HTTPException(409, 'Document changed. Reload before uploading a replacement.')
            else:
                if meta.expected_version_id:
                    raise HTTPException(400, 'A replacement document ID is required.')
                conn.execute('''INSERT INTO platform.documents(id,organisation_id,workspace_id,library_id,title)
                  VALUES (%s,%s,%s,%s,%s)''', (docid,selected_scope['organisation_id'], target if kind=='workspaces' else None,
                                           target if kind=='libraries' else None,meta.title))
            key = f"{selected_scope['organisation_id']}/{docid}/{vid}.pdf"
            object_version = api.state.originals.put(key,data,retention_days=selected_scope.get('retention_days',365), legal_hold=selected_scope.get('legal_hold',False))
            conn.execute('''INSERT INTO platform.versions
              (id,document_id,sha256,object_key,object_version_id,byte_size,filename,source,jurisdiction,effective_date,received_date,extractor,chunker,embedding_model,page_count)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
              (vid,docid,digest,key,object_version,len(data),filename,meta.source,meta.jurisdiction,meta.effective_date,meta.received_date,
               f'PyMuPDF/{fitz.VersionBind}','doclens-boundary-1000-overlap-200/v1',api.state.embeddings.name,pages))
            for ordinal, ((page,text), embedding) in enumerate(zip(items,vectors),1):
                conn.execute('''INSERT INTO platform.passages(id,version_id,page_number,ordinal,text,excerpt_sha256,embedding)
                  VALUES (%s,%s,%s,%s,%s,%s,%s)''', (uuid4(),vid,page,ordinal,text,hashlib.sha256(text.encode()).hexdigest(),Jsonb(embedding)))
            # A fresh statement rechecks current membership after object/model work.
            scope(conn,kind,target,True)
            conn.execute('UPDATE platform.documents SET active_version_id=%s WHERE id=%s', (vid,docid))
            audit(conn,'upload',docid,vid)
        return {'document_id':docid,'version_id':vid,'sha256':digest,'passages':len(items),'indexed':True}

    @api.get('/documents/{document_id}/versions')
    def versions(document_id: str, request: Request):
        with api.state.db.transaction(request.state.identity) as conn:
            if not conn.execute('SELECT id FROM platform.documents WHERE id=%s',(uuid(document_id),)).fetchone():
                raise HTTPException(404,'Not found.')
            return {'versions':conn.execute('''SELECT id,document_id,sha256,byte_size,filename,created_at,uploader_id,
              source,jurisdiction,effective_date,received_date,extractor,chunker,embedding_model,page_count
              FROM platform.versions WHERE document_id=%s ORDER BY created_at DESC''',(uuid(document_id),)).fetchall()}

    @api.get('/versions/{version_id}/passages')
    def passages(version_id: str, request: Request):
        with api.state.db.transaction(request.state.identity) as conn:
            row = version(conn,uuid(version_id))
            rows = conn.execute('''SELECT id,version_id,page_number,ordinal,text,excerpt_sha256 FROM platform.passages
                                   WHERE version_id=%s ORDER BY ordinal''',(row['id'],)).fetchall()
            audit(conn,'read-passage',row['document_id'],row['id'])
            return {'passages':rows,'document_sha256':row['sha256'],'coordinates':None}

    @api.get('/versions/{version_id}/original')
    def original(version_id: str, request: Request):
        with api.state.db.transaction(request.state.identity) as conn:
            row = version(conn,uuid(version_id))
            data = api.state.originals.get(row['object_key'],row['sha256'],row['object_version_id'])
            row = version(conn,uuid(version_id))  # current policy after I/O
            audit(conn,'read-original',row['document_id'],row['id'])
            start,end = 0,len(data)-1
            headers={'Accept-Ranges':'bytes','ETag':'"'+row['sha256']+'"',
                     'Content-Disposition':'inline; filename="original.pdf"', 'Content-Security-Policy':"sandbox"}
            status=200
            range_value=request.headers.get('range')
            if range_value:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_value) if len(range_value)<=128 else None
                if not match or not any(match.groups()):
                    return Response(status_code=416,headers={'Content-Range':f'bytes */{len(data)}'})
                first,last=match.groups()
                if first:
                    start=int(first); end=min(int(last) if last else len(data)-1,len(data)-1)
                else:
                    start=max(0,len(data)-int(last))
                if start>end or start>=len(data) or (not first and int(last)==0):
                    return Response(status_code=416,headers={'Content-Range':f'bytes */{len(data)}'})
                headers['Content-Range']=f'bytes {start}-{end}/{len(data)}'; status=206
            return Response(data[start:end+1],status_code=status,media_type='application/pdf',headers=headers)

    @api.post('/workspaces/{workspace_id}/references/{version_id}')
    def select_reference(workspace_id: str, version_id: str, request: Request):
        with api.state.db.transaction(request.state.identity) as conn:
            ws=scope(conn,'workspaces',uuid(workspace_id),True)
            row=version(conn,uuid(version_id))
            document=conn.execute('SELECT * FROM platform.documents WHERE id=%s',(row['document_id'],)).fetchone()
            approved=conn.execute('SELECT 1 FROM platform.reference_approvals WHERE version_id=%s',(row['id'],)).fetchone()
            if not approved or not document['library_id'] or document['organisation_id']!=ws['organisation_id']:
                raise HTTPException(404,'Not found.')
            conn.execute('INSERT INTO platform.workspace_references VALUES (%s,%s) ON CONFLICT DO NOTHING',(uuid(workspace_id),row['id']))
            audit(conn,'select-reference',row['document_id'],row['id'])
            return {'selected':True,'version_id':row['id']}

    @api.post('/workspaces/{workspace_id}/search')
    async def search(workspace_id: str, request: Request):
        target=uuid(workspace_id); identity=request.state.identity
        def check():
            with api.state.db.transaction(identity) as conn:
                scope(conn,'workspaces',target)
        await run_in_threadpool(check)
        query=Search.model_validate_json(await bounded_body(request,8192))
        def retrieve():
            with api.state.db.transaction(identity) as conn:
                scope(conn,'workspaces',target)
                # SQL + RLS determines the candidate set before any model sees text.
                rows=conn.execute('''SELECT p.*,v.document_id,v.sha256 AS document_sha256 FROM platform.passages p
                  JOIN platform.versions v ON v.id=p.version_id JOIN platform.documents d ON d.id=v.document_id
                  WHERE (d.workspace_id=%s AND d.active_version_id=v.id) OR EXISTS (
                   SELECT 1 FROM platform.workspace_references r WHERE r.workspace_id=%s AND r.version_id=v.id)
                  ORDER BY p.id LIMIT 1001''',(target,target)).fetchall()
                if len(rows)>1000:
                    raise HTTPException(409,'Workspace exceeds the Milestone 1 search limit.')
                if query.mode=='dense':
                    embedding=api.state.embeddings.encode([query.query])[0]
                    def score(row):
                        return sum(a*b for a,b in zip(embedding,row['embedding']))
                else:
                    terms=set(re.findall(r'\w+',query.query.lower()))
                    def score(row):
                        return len(terms.intersection(re.findall(r'\w+',row['text'].lower())))
                ranked=sorted(((score(r),r) for r in rows),key=lambda pair:pair[0],reverse=True)[:5]
                results=[]
                for value,row in ranked:
                    if value<=0:
                        continue
                    # Reauthorize every returned passage and workspace after inference.
                    scope(conn,'workspaces',target)
                    if not conn.execute('SELECT id FROM platform.passages WHERE id=%s',(row['id'],)).fetchone():
                        continue
                    allowed=conn.execute("""SELECT p.id FROM platform.passages p
                      JOIN platform.versions v ON v.id=p.version_id JOIN platform.documents d ON d.id=v.document_id
                      WHERE p.id=%s AND ((d.workspace_id=%s AND d.active_version_id=v.id) OR EXISTS (
                        SELECT 1 FROM platform.workspace_references r WHERE r.workspace_id=%s AND r.version_id=v.id))""",
                        (row['id'],target,target)).fetchone()
                    if not allowed:
                        continue
                    results.append({k:row[k] for k in ('id','version_id','document_id','page_number','text','excerpt_sha256','document_sha256')})
                return {'results':results,'mode':query.mode}
        return await run_in_threadpool(retrieve)

    # Worker claims/transitions, reports, exports and hosted generation are not registered.
    # Unknown routes still require authentication and return 404 without object info.
    return api


async def parse_upload(request: Request):
    raw=await bounded_body(request,MAX_BYTES+16384)
    async def stream():
        yield raw
    from starlette.formparsers import MultiPartParser, MultiPartException
    from starlette.datastructures import UploadFile
    try:
        form=await MultiPartParser(request.headers,stream(),max_files=1,max_fields=1,max_part_size=8192).parse()
    except MultiPartException:
        raise HTTPException(400,'Invalid upload.') from None
    try:
        if set(form.keys())!={'file','metadata'} or len(form.multi_items())!=2:
            raise HTTPException(400,'A PDF and metadata are required.')
        file=form['file']
        if not isinstance(file,UploadFile) or file.content_type!='application/pdf':
            raise HTTPException(400,'A PDF is required.')
        meta=Metadata.model_validate_json(form['metadata'])
        if not meta.synthetic:
            raise HTTPException(400,'Only synthetic documents are admitted in this milestone.')
        data=await file.read(MAX_BYTES+1)
        if not data or len(data)>MAX_BYTES:
            raise HTTPException(413,'PDF must be between 1 byte and 10 MiB.')
        filename=(file.filename or 'document.pdf').replace('\\','/').rsplit('/',1)[-1][:255]
        return meta,data,filename
    finally:
        await form.close()


async def bounded_body(request: Request, maximum: int):
    data=bytearray()
    async for part in request.stream():
        data.extend(part)
        if len(data)>maximum:
            raise HTTPException(413,'Request too large.')
    return bytes(data)


app=create_app()
