from observability import tracked, measure

import logging
import os
import secrets
from typing import Optional

import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from chunking import chunk_text
from embeddings import create_embedding, create_embeddings
from vector_store import (
    create_collection,
    delete_document,
    store_chunks,
    hybrid_search,
)
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

@app.post("/documents/extract")
async def extract_document(
    file: UploadFile = File(...),
    _: None = Depends(require_internal_auth),
):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are currently supported."
        )

    pdf_bytes = await file.read()

    try:
        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read this PDF."
        )

    pages = []

    for page_number, page in enumerate(
        document,
        start=1
    ):
        text = page.get_text("text")

        pages.append({
            "page_number": page_number,
            "text": text
        })

    document.close()

    return {
        "filename": file.filename,
        "page_count": len(pages),
        "pages": pages
    }


# --------------------------------------------------
# Process + index PDF
# --------------------------------------------------

@app.post("/documents/process")
@tracked("upload")
def process_document(
    file: UploadFile = File(...),
    _: None = Depends(require_internal_auth),
):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are currently supported."
        )

    # UploadFile is spooled to disk by Starlette; bound the in-memory PDF copy.
    pdf_bytes = file.file.read(50 * 1024 * 1024 + 1)
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF files must be 50 MiB or smaller.")

    try:
        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read this PDF."
        )

    chunks = []

    # Extract and chunk each page
    for page_number, page in enumerate(
        document,
        start=1
    ):

        text = page.get_text("text")

        if not text.strip():
            continue

        page_chunks = chunk_text(
            text,
            chunk_size=1000,
            overlap=200
        )

        for chunk_number, chunk in enumerate(
            page_chunks,
            start=1
        ):

            chunk_id = (
                f"p{page_number}-c{chunk_number}"
            )

            chunks.append({
                "text": chunk,
                "metadata": {
                    "document_name": file.filename,
                    "page_number": page_number,
                    "chunk_id": chunk_id
                }
            })

    document.close()

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No extractable text was found in this PDF."
        )

    # Create embeddings
    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = create_embeddings(texts)

    with measure("indexing"):
        # Store in Qdrant
        create_collection()

        # Prevent duplicate chunks when a document
        # with the same filename is uploaded again.
        delete_document(file.filename)

        store_chunks(
            chunks=chunks,
            embeddings=embeddings
        )

    return {
        "filename": file.filename,
        "total_chunks": len(chunks),
        "indexed": True
    }


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

    # Create semantic embedding for the question
    question_embedding = create_embedding(
        question
    )

    # --------------------------------------------------
    # Hybrid retrieval + reranking
    #
    # Combines:
    # 1. Dense semantic search
    # 2. BM25 keyword search
    # 3. Reciprocal Rank Fusion (RRF)
    # 4. Cross-encoder reranking
    # --------------------------------------------------

    results = hybrid_search(
        query=question,
        query_embedding=question_embedding,
        limit=3,
        document_name=request.document_name
    )

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
        retrieved_chunks=results
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

