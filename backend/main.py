from typing import Optional

import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from chunking import chunk_text
from embeddings import create_embedding, create_embeddings
from vector_store import (
    create_collection,
    store_chunks,
    search_chunks,
)
from generation import generate_answer


# --------------------------------------------------
# FastAPI app
# --------------------------------------------------

app = FastAPI(
    title="DocLens API",
    description="Backend API for DocLens",
    version="0.1.0",
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
async def extract_document(file: UploadFile = File(...)):

    # Only support PDFs for V1
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are currently supported."
        )

    # Read uploaded PDF
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

    # Extract every page separately
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
async def process_document(file: UploadFile = File(...)):

    # Only support PDFs for V1
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are currently supported."
        )

    # Read uploaded PDF
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

    chunks = []

    # --------------------------------------------------
    # Extract + chunk every page
    # --------------------------------------------------

    for page_number, page in enumerate(
        document,
        start=1
    ):
        text = page.get_text("text")

        # Skip pages containing no usable text
        if not text.strip():
            continue

        page_chunks = chunk_text(
            text,
            chunk_size=1000,
            overlap=200
        )

        # Attach metadata to every chunk
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

    # No usable text found
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No extractable text was found in this PDF."
        )

    # --------------------------------------------------
    # Create embeddings
    # --------------------------------------------------

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = create_embeddings(texts)

    # --------------------------------------------------
    # Store in Qdrant
    # --------------------------------------------------

    create_collection()

    store_chunks(
        chunks=chunks,
        embeddings=embeddings
    )

    # --------------------------------------------------
    # Response
    # --------------------------------------------------

    return {
        "filename": file.filename,
        "total_chunks": len(chunks),
        "indexed": True
    }


# --------------------------------------------------
# Ask questions
# --------------------------------------------------

@app.post("/ask")
def ask_question(request: AskRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    # --------------------------------------------------
    # Embed the question
    # --------------------------------------------------

    question_embedding = create_embedding(
        question
    )

    # --------------------------------------------------
    # Retrieve relevant chunks
    # --------------------------------------------------

    results = search_chunks(
        query_embedding=question_embedding,
        limit=3,
        document_name=request.document_name
    )

    # --------------------------------------------------
    # Generate grounded answer
    # --------------------------------------------------

    answer = generate_answer(
        question=question,
        retrieved_chunks=results
    )

    # --------------------------------------------------
    # Build citations from Qdrant metadata
    # --------------------------------------------------

    citations = []

    for result in results:
        payload = result.payload

        citations.append({
            "document_name": payload["document_name"],
            "page_number": payload["page_number"],
            "chunk_id": payload["chunk_id"]
        })

    # --------------------------------------------------
    # Response
    # --------------------------------------------------

    return {
        "answer": answer,
        "citations": citations
    }
