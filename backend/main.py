
import logging
import time
import os
import secrets
from typing import Optional


import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram
from pydantic import BaseModel


from chunking import chunk_text
from embeddings import create_embedding, create_embeddings
from vector_store import (
    hybrid_search, complete_document_context,
)
from document_coverage import needs_document_coverage, CoverageUnavailable
from generation import generate_answer


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("doclens")

# --------------------------------------------------
# Authentication metrics
# --------------------------------------------------

AUTH_LOGIN_SUCCESS = Counter(
    "doclens_auth_login_success_total",
    "Total successful DocLens admin logins",
)

AUTH_LOGIN_FAILURE = Counter(
    "doclens_auth_login_failure_total",
    "Total failed DocLens admin login attempts",
)

# --------------------------------------------------
# RAG retrieval metrics
# --------------------------------------------------

RAG_RETRIEVAL_DURATION = Histogram(
    "doclens_rag_retrieval_duration_seconds",
    "Time spent retrieving and reranking document chunks",
)

RAG_RETRIEVED_CHUNKS = Histogram(
    "doclens_rag_retrieved_chunks",
    "Number of document chunks returned by retrieval",
    buckets=(0, 1, 2, 3, 5, 10, 20, float("inf")),
)


# --------------------------------------------------
# Internal API authentication
# --------------------------------------------------

def require_internal_auth(
    x_doclens_internal_key: Optional[str] = Header(default=None),
):
    expected_key = os.getenv("DOCLENS_SESSION_SECRET")

    if not expected_key:
        logger.error("Backend authentication secret is not configured")
        raise HTTPException(
            status_code=503,
            detail="Backend authentication is not configured."
        )

    if not x_doclens_internal_key or not secrets.compare_digest(
        x_doclens_internal_key,
        expected_key,
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized."
        )


# --------------------------------------------------
# FastAPI app
# --------------------------------------------------

app = FastAPI(
    title="DocLens API",
    description="Backend API for DocLens",
    version="0.1.0",
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from upload_processing import UploadGate, handle as handle_upload
UPLOAD_OPENAPI = {
    "parameters": [{"in": "header", "name": "X-DocLens-Internal-Key", "required": True, "schema": {"type": "string"}}],
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file"], "additionalProperties": False,
        "properties": {"file": {"type": "string", "format": "binary"}},
    }}}},
}
app.add_middleware(UploadGate)


# --------------------------------------------------
# Prometheus monitoring
# --------------------------------------------------

Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics"],
).instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False
)


# --------------------------------------------------
# Request models
# --------------------------------------------------

class AskRequest(BaseModel):
    question: str
    document_name: Optional[str] = None
    comprehensive: bool = False


# --------------------------------------------------
# Authentication event monitoring
# --------------------------------------------------

class AuthEvent(BaseModel):
    outcome: str


@app.post("/internal/auth-event", include_in_schema=False)
def record_auth_event(
    event: AuthEvent,
    _: None = Depends(require_internal_auth),
):
    if event.outcome == "success":
        AUTH_LOGIN_SUCCESS.inc()
    elif event.outcome == "failure":
        AUTH_LOGIN_FAILURE.inc()
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid authentication event."
        )

    return {"recorded": True}


# --------------------------------------------------
# Health check
# --------------------------------------------------


@app.get("/")
def root():
    return {
        "message": "DocLens API is running"
    }


# --------------------------------------------------
# Extract PDF text page-by-page
# --------------------------------------------------

@app.post("/documents/extract", openapi_extra=UPLOAD_OPENAPI)
async def extract_document(request: Request):
    return await handle_upload(request, extract_only=True)


@app.post("/documents/process", openapi_extra=UPLOAD_OPENAPI)
async def process_document(request: Request):
    return await handle_upload(request)


# --------------------------------------------------
# Ask questions
# --------------------------------------------------

@app.post("/ask")
def ask_question(
    request: AskRequest,
    _: None = Depends(require_internal_auth),
):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    comprehensive = request.comprehensive or needs_document_coverage(question)
    retrieval_start = time.perf_counter()
    try:
        if comprehensive:
            results = complete_document_context(request.document_name)
        else:
            results = hybrid_search(
                query=question, query_embedding=create_embedding(question),
                limit=3, document_name=request.document_name,
            )
    except CoverageUnavailable as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        RAG_RETRIEVAL_DURATION.observe(time.perf_counter() - retrieval_start)

    RAG_RETRIEVED_CHUNKS.observe(len(results))

    # Log retrieval results without logging
    # the user's full question.
    logger.info(
        "Retrieval completed | document=%s | results=%d",
        request.document_name,
        len(results)
    )

    for index, result in enumerate(
        results,
        start=1
    ):
        logger.info(
            "Retrieved result | rank=%d | page=%s | chunk=%s",
            index,
            result.payload["page_number"],
            result.payload["chunk_id"]
        )

    # Generate grounded answer + sources actually used
    generation_result = generate_answer(
        question=question,
        retrieved_chunks=results,
        comprehensive=comprehensive,
    )

    answer = generation_result["answer"]
    source_ids = generation_result["source_ids"]

    logger.info(
        "Answer generated | document=%s | sources_used=%d",
        request.document_name,
        len(source_ids)
    )

    # --------------------------------------------------
    # Build citations only from sources Gemini used
    # --------------------------------------------------

    citations = []

    for source_id in source_ids:

        # Gemini source numbering starts at 1
        if not isinstance(source_id, int) or isinstance(source_id, bool):
            continue
        result_index = source_id - 1

        if 0 <= result_index < len(results):

            payload = results[result_index].payload

            citation = {
                "document_name": payload["document_name"],
                "page_number": payload["page_number"],
                "chunk_id": payload["chunk_id"]
            }

            # Prevent duplicate citations
            if citation not in citations:
                citations.append(citation)

    return {
        "answer": answer,
        "citations": citations
    }

