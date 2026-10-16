# Document Intelligence RAG Backend

A high-performance FastAPI backend service providing multi-user database persistence (via Supabase PostgreSQL), clean service boundaries, and future integration with the Document Intelligence RAG Engine.

---

## Architecture Overview

```
ragllm/
├── document-intelligence-rag/     # Single source of truth for RAG logic & vector store
│   ├── data/                      # Multi-format source documents
│   ├── vector_db/                 # Local Qdrant persistent storage (4,125 vectors)
│   ├── retrieval/                 # Hybrid & semantic retrieval + reranking
│   ├── generation/                # Local Qwen LLM generation
│   └── .venv/                     # Shared development Python environment
│
└── backend/                       # Modern FastAPI Backend
    ├── app/
    │   ├── api/routes/            # Versioned API routes (/api/v1)
    │   ├── core/                  # Configuration & database session pooler
    │   ├── models/                # Modern SQLAlchemy 2.x ORM models
    │   ├── schemas/               # Pydantic v2 validation & response schemas
    │   ├── services/              # Business logic & RAG integration interfaces
    │   └── main.py                # Application entry point & CORS
    ├── tests/                     # Automated test suites
    ├── .env                       # Local secrets (never committed)
    ├── .env.example               # Template environment configuration
    ├── requirements.txt           # Python dependencies
    └── README.md
```

---

## Features (Phase 1 Foundation)

- **FastAPI Framework**: Asynchronous, high-speed RESTful API with automated OpenAPI / Swagger documentation.
- **SQLAlchemy 2.x**: Fully typed models (`Mapped`, `mapped_column`) mirroring the Supabase schema (`users`, `documents`, `conversations`, `messages`, `ingestion_jobs`).
- **Connection Pooling**: Configured for Supabase PostgreSQL Session Pooler (`pool_pre_ping=True`, `pool_recycle=300`, `pool_size=10`).
- **Multi-User Security Design**: Strict tenant isolation on documents, conversations, and future vector payloads by `user_id`.
- **RAG Abstraction Layer**: Clean service abstraction ready to invoke `document-intelligence-rag` without duplicating code or modifying the existing 4,125-vector database.
- **CORS Configured**: Ready for frontend integration (e.g., Vite on `http://localhost:5173`).

---

## Getting Started

### 1. Prerequisites

- Python 3.10+
- The shared virtual environment in `document-intelligence-rag/.venv`

### 2. Environment Configuration

Copy `.env.example` to `.env` in the `backend/` folder:

```powershell
cp .env.example .env
```

Edit `backend/.env` to configure your Supabase Session Pooler connection string:

```ini
ENVIRONMENT=development
API_HOST=127.0.0.1
API_PORT=8000
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]

# Supabase Session Pooler URL (replace with your credentials):
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

# Qdrant Vector Store
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
```

> **Note**: The password and credentials are never hardcoded or exposed in logs. If `DATABASE_URL` is empty, the application starts with database features marked as `not_configured`.

### 3. Running the Backend Server

From the `backend` folder, run:

```powershell
uvicorn app.main:app --reload
```

Or using the virtual environment directly:

```powershell
..\document-intelligence-rag\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

The server will start at:
- **API Root**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

---

## API Endpoints (`/api/v1`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Health check with database connectivity ping |
| `GET` | `/api/v1/users/{user_id}` | Fetch user details (excluding password hash) |
| `GET` | `/api/v1/documents/{user_id}` | Retrieve documents belonging to a user |
| `GET` | `/api/v1/conversations/{user_id}` | Retrieve user conversations |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Retrieve conversation message history |
| `POST` | `/api/v1/chat/query` | RAG query pipeline endpoint |

---

## Running Automated Tests

Run pytest using the shared virtual environment:

```powershell
..\document-intelligence-rag\.venv\Scripts\pytest.exe tests/
```

---

## Connecting with the RAG Engine

The existing `document-intelligence-rag` engine remains the single source of truth for:
- Document parsing and OCR
- Chunking strategies
- Sentence Transformers embeddings
- Local Qdrant vector database (4,125 indexed vectors)
- Query-aware reranking and local Qwen generation

The backend interacts with this engine via `app/services/rag_service.py`. This ensures:
1. No duplicated RAG logic.
2. Existing vector stores and data directories are preserved untouched.
3. User filtering is injected cleanly into retrieval payloads.

---

## Current Limitations & Roadmap

- **Phase 1 (Current)**: Backend foundation, database models, schemas, health checks, route structure, and service interfaces.
- **Phase 2**: Authentication (JWT / Supabase Auth), file upload via Supabase Storage, and connecting `rag_service.py` directly to the `document-intelligence-rag` retriever and local Qwen generator.
- **Phase 3**: Multi-tenant Qdrant Cloud migration and background ingestion jobs.
- **Phase 4**: Frontend web application.
