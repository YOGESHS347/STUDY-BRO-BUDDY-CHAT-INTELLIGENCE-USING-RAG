# Phase 11 Frozen Baseline: Advanced RAG v2

**Baseline Freeze Date:** September 19, 2026  
**Status:** FROZEN & CERTIFIED BASELINE  
**Auditor:** Antigravity AI Engineering Assistant  
**System:** Enterprise Document Intelligence RAG Platform  
**Environment:** Python 3.12.10 (`document-intelligence-rag/.venv`), Node.js 11.12.1 / Vite 8.3.0, Local Qwen3-4B-Q4_K_M via `llama-server.exe` (Port 8080), Dual Vector Stores (Local Qdrant + Qdrant Cloud), Supabase PostgreSQL.

---

## 1. Frozen Aggregate Metrics

| Metric | Frozen Baseline Value | Measurement Method |
| :--- | :---: | :--- |
| **Benchmark Suite Size** | **30 Cases** | Categories A through J (`eval_dataset.py`) |
| **Precision @ 1** | **1.0000** (100.0%) | 25/25 in-domain queries returned relevant doc at Rank 1 |
| **Precision @ 3** | **0.9733** (97.33%) | Evaluated across all in-domain queries |
| **Mean Reciprocal Rank (MRR)** | **1.0000** | Top-1 document matched ground truth target |
| **Out-of-Domain Refusal Rate** | **100.0%** | 5/5 out-of-domain and adversarial inputs rejected |
| **Code-Intent Precision** | **100.0%** | 5/5 code queries promoted verified code chunks |
| **Mean Concept Coverage** | **87.33%** | Substring concept match (see finding below) |
| **Mean Retrieval Latency** | **53.68 ms** | Total end-to-end retrieval time |
| **P95 Retrieval Latency** | **104.87 ms** | 95th percentile latency |

---

## 2. Category-Level Performance Breakdown

| Category | Description | Cases | P@1 | P@3 | MRR | Concept Cov | Latency (Mean) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **A** | Core Definitions | 7 | 1.0000 | 0.9524 | 1.0000 | 83.3% | 86.24 ms |
| **B** | Conceptual Explanations | 4 | 1.0000 | 1.0000 | 1.0000 | 81.2% | 30.61 ms |
| **C** | Code / Implementation | 5 | 1.0000 | 1.0000 | 1.0000 | 100.0% | 65.36 ms |
| **D** | Specific Factual Recall | 2 | 1.0000 | 1.0000 | 1.0000 | 87.5% | 44.49 ms |
| **E** | Multi-Concept Queries | 3 | 1.0000 | 0.8889 | 1.0000 | 88.9% | 53.76 ms |
| **F** | Multi-Document Queries | 1 | 1.0000 | 1.0000 | 1.0000 | 33.3% | 36.81 ms |
| **G** | Conversational Follow-Up | 2 | 1.0000 | 1.0000 | 1.0000 | 100.0% | 60.33 ms |
| **H** | Out-of-Domain Refusal | 3 | N/A | N/A | N/A | Refusal: 100% | 11.64 ms |
| **I** | Adversarial / Ambiguous | 2 | N/A | N/A | N/A | Refusal: 100% | 0.03 ms |
| **J** | Long Multi-Part Overview | 1 | 1.0000 | 1.0000 | 1.0000 | 100.0% | 114.65 ms |

---

## 3. Grounding & Code Retrieval Findings

### 3.1. Payment Abstraction Grounding Truth
- **Corpus Scan:** Exact token scan across all 4,125 local vectors confirmed **0 occurrences** of the word `"payment"`.
- **Query:** *"Show me the Payment abstraction example."*
- **Behavior:**
  1. Retrieves general abstraction material (`285_OOPS lecture notes Complete.pdf`, Page 115).
  2. Grounded Generator explains that abstract classes and pure virtual functions exist, but explicitly communicates that payment-specific material is not present in the reference documents.
  3. **Zero code hallucination** and **zero fabricated citations**.

### 3.2. Code-Intent Retrieval
- All 6 target code queries successfully retrieve and boost relevant code snippets:
  - Abstraction code → Page 115 (Pure virtual function Base/Derived C++ class)
  - Inheritance code → Page 96 (Inheritance C++ class)
  - Encapsulation code → Page 8 (Encapsulated Item class with private data)
  - Polymorphism code → Page 3 (Function overloading code)
- **Concept-Conditioned Penalty:** Code chunks lacking matching concept keywords are penalized by `-0.15`, preventing ungrounded code promotion.

### 3.3. Conversational Follow-Up Context
- Elliptical follow-up queries are dynamically re-anchored using preceding conversational turns:
  - *"What is abstraction?"* → *"Give me an example."* → Re-anchored to abstraction code (Page 115).
  - *"What is inheritance?"* → *"Show me code."* → Re-anchored to inheritance code (Page 96).
  - *"What is encapsulation?"* → *"Explain it with an example."* → Re-anchored to encapsulation code (Page 8).

### 3.4. Grounding Gate
- Two-tier gating enforced:
  - **Tier 1 (Retriever):** Confidence threshold `0.40` filters out irrelevant semantic noise.
  - **Tier 2 (Generator):** Missing context triggers standardized refusal; `rag_service.py` clears all citations.

---

## 4. Multi-Tenant Isolation & Security

- **JWT Authority:** `sub` claim is the authoritative tenant identifier.
- **Vector Store Isolation:** Mandatory `user_id` payload filter on Qdrant Cloud searches.
- **Automated Isolation Suite:** `backend/tests/test_qdrant_isolation.py` passed 4/4 tests:
  - Cloud connection & schema verification: PASSED
  - Cross-tenant data leak prevention: PASSED
  - Missing `user_id` fail-safe: PASSED
  - Local database preservation: PASSED

---

## 5. Automated Test Suite Results

```
[TEST SUITE BASELINE SUMMARY]
-----------------------------------------------------------------------------------------
Suite                   Command                     Tests   Result    Execution Time
-----------------------------------------------------------------------------------------
Backend Pytest Suite    pytest backend/tests/       67      67 PASSED 461.93s
Frontend Vitest Suite   npm test -- --run           45      45 PASSED 3.13s
Frontend Production     npm run build               2,614   SUCCESS   0.65s (tsc + vite)
Live RAG Regressions    test_live_acceptance.py    7       7 PASSED  ~35s
-----------------------------------------------------------------------------------------
```

---

## 6. Data Preservation & Safety Baseline

- **Local Reference Qdrant:** Exactly **4,125 vectors** across the 5 reference files:
  - `285_OOPS lecture notes Complete.pdf`: 258 vectors
  - `AI & ML DIGITAL NOTES - Copy.xlsx`: 1,143 vectors
  - `COMPUTER NETWORKS NOTES.txt`: 339 vectors
  - `Operating-System (1).csv`: 10 vectors
  - `PYTHON PROGRAMMING NOTES.docx`: 2,375 vectors
- **Qdrant Cloud:** 57 production user vectors intact.
- **Supabase Database:** 188 conversations, 84 messages, and 37 documents intact.
- **Models:**
  - Embedding: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
  - LLM: `Qwen3-4B-Q4_K_M.gguf` on `llama-server.exe` (Port 8080)
- **Virtual Environment:** Single virtual environment (`document-intelligence-rag/.venv`).

---

## 7. Known Limitations

1. **Payment-Specific Content Absent:** The current reference knowledge base contains pure virtual function and OOP abstraction lecture notes, but no financial/payment-specific domain documents.
2. **Local Qdrant Single-Process Lock:** Embedded local Qdrant uses file locking; concurrent multi-process access is reserved for Qdrant Cloud.
3. **Substring Concept Coverage Artifact:** The 87.3% concept coverage reflects exact literal substring matching in evaluation scripts where source notes use equivalent natural language synonyms.

---

## 8. Baseline Certification

This document represents the frozen, validated baseline for Phase 11. No architectural changes or feature implementations shall proceed without maintaining or improving upon these metrics.
