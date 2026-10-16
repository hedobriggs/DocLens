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

## Uploads and built-in monitoring

The application accepts PDFs up to **50 MiB**, including 25 MB files. The browser,
frontend API and backend validate the file limit. PDF processing runs outside the
backend event loop so health and metrics requests remain responsive. The frontend
allows up to ten minutes for processing; hosting platforms and reverse proxies
may impose shorter limits. Configure any external proxy to accept at least 51 MiB
(to allow multipart overhead) and an appropriate request timeout. The synchronous
workflow is not a background job system; very long documents may still require
an asynchronous ingestion pipeline. File bytes alone do not predict inference time.

`BACKEND_URL` optionally overrides the frontend's internal backend address; the
default `http://backend:8000` works with Docker Compose. For native development set
it to `http://127.0.0.1:8000` in the frontend's server environment.

The existing Compose build includes Prometheus and Grafana by default:

```sh
docker compose up -d --build
```

Supply the existing backend/root environment files and set `GRAFANA_ADMIN_PASSWORD`
securely before starting. Prometheus uses port 9090 and Grafana port 3001, both
bound to loopback. Use a secure tunnel for remote access. Grafana provisions the
**DocLens** dashboard automatically, showing backend availability, request rate,
server errors, p95 request latency, upload outcomes and process memory. Upload
metrics measure completed requests, not per-document processing progress.

Verify that the `doclens-backend` Prometheus target is UP and the Grafana dashboard
contains data after making API requests. The API exposes `/metrics`; keep backend
port 8000 private or restrict external access to this endpoint in your deployment.

Run the upload HTTP regression checks with:

```sh
backend/.venv/bin/python -m unittest discover -s tests -v
```

These checks cover a 25 MiB PDF, over-limit and invalid files, authentication,
metrics, and health responsiveness during inference. Model inference and hosted
generation are isolated in these tests; validate a representative real document
and Gemini response separately before releasing.

### Admin monitoring and metric availability

The admin dashboard includes a **Monitoring** link to an authorized DocLens page.
It opens the Grafana overview using `GRAFANA_PUBLIC_URL` (default:
`http://localhost:3001`). Set this to the URL reachable by the administrator's
browser; a remote browser's localhost is not the server. Grafana has its own
admin/password login. DocLens cookies are never used as Grafana credentials.
Anonymous access and self-registration are disabled.

On first startup the `grafana-permissions` service removes default Viewer/Editor
permissions from the provisioned `doclens-admin` folder. **Keep Grafana on its
loopback binding and do not expose it remotely until that service exits with
code 0.** Recheck after changing Grafana users, organizations or folder permissions.
An existing Grafana volume retains its admin password; changing the environment
variable does not reset it. Rotate the password through Grafana first, then update
the bootstrap configuration. Only trusted administrators should access Grafana.

The overview links to CPU/system, AI, application and storage dashboards. The
Linux host's node-exporter and cAdvisor are private Compose services; they need
read-only host filesystem/process/container metadata mounts. Their values describe
the Docker host, which may be a VM, not the administrator's laptop. Restricted
container platforms may not support those mounts/cgroups. Unavailable collectors
show No data or a down exporter; do not replace them with synthetic zeros.
`container_last_seen` shows observation freshness, not Docker HEALTHCHECK status.

Backend metrics include embedding/reranking/Gemini duration and failures,
upload/indexing duration and outcomes, distinct document and chunk counts, and
apparent Qdrant file bytes (not filesystem allocated blocks). No document names,
questions, contents or usernames are metric labels. Gemini token counters appear
only when the provider returns usage metadata. Optional
`GEMINI_INPUT_USD_PER_MILLION` and `GEMINI_OUTPUT_USD_PER_MILLION` enable a basic
USD estimate using provider-reported prompt and candidate tokens; use current
prices for the configured model. It excludes unsupported billing dimensions
(e.g. caching/thinking/tool charges) and is not an invoice. Without prices the
cost metric has no samples. A missing Gemini key permits ingestion and monitoring,
but answer generation fails explicitly and is counted as a Gemini operation error.

`UPLOAD_TIMEOUT_MS` sets the server-to-backend processing deadline (1–600000 ms,
default 600000). It does not limit the incoming multipart transfer. Headers, response
body and overall upstream deadline are bounded. Timeout responses use HTTP 504;
upstream application statuses are preserved, malformed upstream JSON is an explicit
502, and connection failures have a distinct service-unavailable message. A timeout
does not cancel an already-running backend indexing operation. Check before retrying.
External proxy deadlines remain deployment-specific.

Browser regression checks use the built production app and a controlled upstream:

```sh
cd frontend
npm ci
npm run build
npm run test:e2e
```

Set `CHROMIUM_PATH` to an installed Chromium binary (default `/usr/bin/chromium`).
The test upstream deadline is 1500 ms, exercising the same policy as production
without waiting ten minutes. Tests cover slow success, headers/body deadlines,
application errors, invalid JSON, disconnection, UI reset paths, file-size limits,
and administrator/non-administrator monitoring access.
