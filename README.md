# DocLens

> **Ask your documents. Find the source.**

DocLens is a document question-answering application built around **Retrieval-Augmented Generation (RAG)**.

The goal is simple: upload documents, ask questions in natural language, and get answers grounded in the original document content.

I'm building DocLens as an end-to-end AI engineering project, with a focus on understanding and implementing the RAG pipeline rather than hiding the core logic behind frameworks.

## How It Works

```text
Document
   ↓
Text Extraction
   ↓
Chunking
   ↓
Embeddings
   ↓
Qdrant Vector Database
   ↓
Semantic Retrieval
   ↓
Relevant Document Context
   ↓
LLM
   ↓
Grounded Answer + Source Citations
```

DocLens separates document processing, retrieval, and answer generation into distinct stages.

Document chunks are converted into embeddings and stored alongside their original text and metadata. When a user asks a question, DocLens embeds the question and searches Qdrant for semantically relevant chunks.

The original retrieved text — not the vectors — is then provided to the language model as context for generating an answer.

## Current Features

The current backend supports:

- PDF text extraction with PyMuPDF
- Page-aware document processing
- Custom text chunking with overlap
- Local embeddings using Sentence Transformers
- Semantic vector search with Qdrant
- Document-level retrieval filtering
- Metadata for document names, page numbers, and chunk IDs
- FastAPI endpoints for document processing

> **Status:** The generation layer and frontend integration are currently in development.

## Tech Stack

### Backend

- Python
- FastAPI
- PyMuPDF
- Sentence Transformers
- Qdrant

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS

### AI

The current embedding model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

LLM-based grounded answer generation is being integrated through a hosted API.

## Project Structure

```text
DocLens/
├── backend/
│   ├── chunking.py
│   ├── embeddings.py
│   ├── main.py
│   ├── vector_store.py
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── dashboard/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   └── package.json
│
└── README.md
```

Local environment files, virtual environments, generated Qdrant data, and API secrets are excluded from version control.

## RAG Pipeline

### 1. Document Ingestion

PDF documents are uploaded through the FastAPI backend and processed page by page using PyMuPDF.

### 2. Chunking

Extracted text is divided into smaller overlapping chunks.

Page information is retained so retrieved content can be traced back to its source.

### 3. Embeddings

Each chunk is converted into a **384-dimensional embedding** using `all-MiniLM-L6-v2`.

### 4. Vector Storage

Embeddings are stored in Qdrant alongside the original chunk text and metadata.

Each stored point contains information such as:

```text
document_name
page_number
chunk_id
text
```

### 5. Retrieval

Questions are embedded using the same embedding model and compared against stored document vectors using cosine similarity.

Qdrant returns the most semantically relevant chunks along with their source metadata.

### 6. Generation

The next stage connects retrieved context to a hosted LLM.

The model receives the user's question and retrieved document context and generates an answer grounded in that context.

Source citations are constructed using metadata retained by the retrieval pipeline.

## Development Roadmap

- [x] PDF text extraction
- [x] Text chunking
- [x] Local embeddings
- [x] Qdrant vector storage
- [x] Semantic retrieval
- [x] Document filtering
- [ ] LLM integration
- [ ] Grounded answer generation
- [ ] Source citations
- [ ] RAG evaluation
- [ ] Frontend/backend integration
- [ ] Authentication and user isolation
- [ ] Streaming responses
- [ ] Improved retrieval and reranking
- [ ] Dockerization
- [ ] Logging and monitoring
- [ ] Cloud deployment

## Why I'm Building This

DocLens is a practical AI engineering project.

Rather than treating RAG as a single framework call, I'm implementing the core stages separately to understand how **document ingestion, embeddings, vector search, retrieval quality, generation, evaluation, and production infrastructure** work together.

The long-term goal is to turn DocLens from a local RAG prototype into a deployed, observable, and production-oriented AI application.

---

**DocLens** — *by Hedobriggs*
