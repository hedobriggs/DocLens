from typing import Optional

import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
async def process_document(file: UploadFile = File(...)):

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
def ask_question(request: AskRequest):

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
    # Hybrid retrieval
    #
    # Combines:
    # 1. Dense semantic search
    # 2. BM25 keyword search
    # 3. Reciprocal Rank Fusion (RRF)
    # --------------------------------------------------

    results = hybrid_search(
        query=question,
        query_embedding=question_embedding,
        limit=3,
        document_name=request.document_name
    )

    # Temporary retrieval debugging
    print("\n------------------------------")
    print("HYBRID RETRIEVAL")
    print("QUESTION:", repr(question))
    print("DOCUMENT:", repr(request.document_name))

    for index, result in enumerate(
        results,
        start=1
    ):
        print(
            index,
            "Page:",
            result.payload["page_number"],
            "Chunk:",
            result.payload["chunk_id"]
        )

    print("------------------------------\n")

    # Generate grounded answer
    answer = generate_answer(
        question=question,
        retrieved_chunks=results
    )

    # Build citations
    citations = []

    for result in results:

        payload = result.payload

        citations.append({
            "document_name": payload["document_name"],
            "page_number": payload["page_number"],
            "chunk_id": payload["chunk_id"]
        })

    return {
        "answer": answer,
        "citations": citations
    }
