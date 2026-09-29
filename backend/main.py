from fastapi import FastAPI, UploadFile, File, HTTPException
import fitz

from chunking import chunk_text
from embeddings import create_embeddings
from vector_store import create_collection, store_chunks


app = FastAPI(
    title="DocLens API",
    description="Backend API for DocLens",
    version="0.1.0",
)


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
    for page_number, page in enumerate(document, start=1):

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

    for page_number, page in enumerate(document, start=1):

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

            chunk_id = f"p{page_number}-c{chunk_number}"

            chunks.append({
                "text": chunk,
                "metadata": {
                    "document_name": file.filename,
                    "page_number": page_number,
                    "chunk_id": chunk_id
                }
            })

    document.close()

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
