# Document Intelligence RAG — Master Run Guide

Comprehensive guide to setting up and running all services across the Document Intelligence RAG full-stack project.

---

## ⚡ Quick Run (3 Terminals)

To run the complete system, open **3 separate PowerShell terminals** and execute:

### 🖥️ Terminal 1 — Local Qwen LLM Server (Port 8080)
```powershell
llama-server.exe -m "C:\Users\yoges\.cache\huggingface\hub\models--Qwen--Qwen3-4B-GGUF\snapshots\bc640142c66e1fdd12af0bd68f40445458f3869b\Qwen3-4B-Q4_K_M.gguf" --port 8080 -c 4096
```

---

### ⚙️ Terminal 2 — FastAPI Backend (Port 8000)
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\backend
..\document-intelligence-rag\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

---

### 🌐 Terminal 3 — Vite + React Frontend (Port 5173)
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\frontend
npm run dev
```

---

## 🔗 Service URLs & Endpoints

| Service | URL | Notes |
| :--- | :--- | :--- |
| **Frontend Web Application** | [http://localhost:5173](http://localhost:5173) | Main UI (Auth, Chat, Document Uploads) |
| **Backend Swagger Docs** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | Interactive API exploration & testing |
| **Backend Health Check** | [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health) | Verifies server and database connection |
| **Local LLM Health / Metrics** | [http://127.0.0.1:8080/health](http://127.0.0.1:8080/health) | llama-server health check |

---

## 📦 First-Time Installation & Setup

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

## 🧪 Testing Commands

### Backend Automated Test Suite
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\backend
..\document-intelligence-rag\.venv\Scripts\pytest.exe tests/ -v
```

### Frontend Automated Test Suite
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\frontend
npm test
```

---

## 🔍 Standalone CLI Engine & Retrieval Tests

### Interactive CLI RAG
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\document-intelligence-rag
.venv\Scripts\python.exe app.py
```

### Run Retrieval Diagnostic Tests
```powershell
cd c:\Users\yoges\OneDrive\Desktop\ragllm\document-intelligence-rag
.venv\Scripts\python.exe test_retrieval.py
.venv\Scripts\python.exe test_all_queries.py
```
