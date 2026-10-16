# Document Intelligence RAG — Quickstart & Run Commands

Complete guide to starting and running the entire Document Intelligence RAG system (Local LLM Server, FastAPI Backend, Vite + React Frontend, and CLI Engine).

---

## 🚀 Quick Run Guide (3-Terminal Setup)

Open **3 separate PowerShell terminals** and run the following commands:

### Terminal 1: Local Qwen LLM Server (Port 8080)
```powershell
llama-server.exe -m "C:\Users\yoges\.cache\huggingface\hub\models--Qwen--Qwen3-4B-GGUF\snapshots\bc640142c66e1fdd12af0bd68f40445458f3869b\Qwen3-4B-Q4_K_M.gguf" --port 8080 -c 4096
```

---

### Terminal 2: FastAPI Backend (Port 8000)
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\backend
..\document-intelligence-rag\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

---

### Terminal 3: Vite + React Frontend (Port 5173)
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\frontend
npm run dev
```

---

## 🌐 Application URLs

| Service | URL | Description |
| :--- | :--- | :--- |
| **Frontend Web App** | [http://localhost:5173](http://localhost:5173) | Interactive chat UI, document management & dashboard |
| **Backend API (Swagger Docs)** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | Interactive OpenAPI / Swagger API explorer |
| **Backend Health Check** | [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health) | Backend & Database connection status |
| **Local LLM Health** | [http://127.0.0.1:8080/health](http://127.0.0.1:8080/health) | llama-server health & metrics |

---

## 🛠️ First-Time Installation & Setup Commands

If setting up the repository for the first time:

### 1. Backend Setup
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\backend
Copy-Item .env.example .env
..\document-intelligence-rag\.venv\Scripts\pip.exe install -r requirements.txt
```

### 2. Frontend Setup
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\frontend
Copy-Item .env.example .env
npm install
```

---

## 🧪 Testing & Diagnostic Commands

### Run Backend Unit & Integration Tests
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\backend
..\document-intelligence-rag\.venv\Scripts\pytest.exe tests/ -v
```

### Run Frontend Vitest Test Suite
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\frontend
npm test
```

### Run Standalone CLI RAG Engine (Terminal Interactive Mode)
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\document-intelligence-rag
.venv\Scripts\python.exe app.py
```

### Test Retrieval Pipeline Only
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\document-intelligence-rag
.venv\Scripts\python.exe test_retrieval.py
.venv\Scripts\python.exe test_all_queries.py
```