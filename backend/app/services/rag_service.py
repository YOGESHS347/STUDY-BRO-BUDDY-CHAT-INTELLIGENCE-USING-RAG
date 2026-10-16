import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status

from app.schemas.chat import ChatQueryRequest, ChatQueryResponse, ChatSource

logger = logging.getLogger(__name__)

# Centralized path resolution: add sibling directory document-intelligence-rag to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
RAG_ENGINE_DIR = PROJECT_ROOT / "document-intelligence-rag"

if str(RAG_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_ENGINE_DIR))
    logger.info("Registered RAG engine directory in sys.path: %s", RAG_ENGINE_DIR)


class RAGService:
    """
    Backend service bridge interfacing FastAPI with the Document Intelligence RAG engine.
    Ensures single source of truth for RAG retrieval and generation without duplicating logic.
    """

    def __init__(self):
        self._retriever = None
        self._generator = None

    def get_retriever(self):
        """Lazy-loaded singleton for Retriever."""
        if self._retriever is None:
            logger.info("Initializing RAG Retriever...")
            try:
                from retrieval.retrieval import Retriever
                self._retriever = Retriever()
                logger.info("RAG Retriever initialized.")
            except Exception as e:
                logger.exception("Failed to initialize Retriever: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="RAG vector retrieval service failed to initialize.",
                )
        return self._retriever

    def get_generator(self):
        """Lazy-loaded singleton for Generator."""
        if self._generator is None:
            logger.info("Initializing RAG Generator...")
            try:
                from generation.generation import Generator
                self._generator = Generator()
                logger.info("RAG Generator initialized.")
            except Exception as e:
                logger.exception("Failed to initialize Generator: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="RAG generation service failed to initialize.",
                )
        return self._generator

    async def query(
        self,
        request: ChatQueryRequest,
        user_id: Optional[Union[UUID, str]] = None,
        conversation_history: Optional[List[dict]] = None,
    ) -> ChatQueryResponse:
        """
        Executes end-to-end RAG query flow with conversation awareness,
        bounded context expansion, and calibrated grounding gates.
        """
        import time
        import uuid as uuid_pkg

        start_time = time.perf_counter()
        request_id = str(uuid_pkg.uuid4())[:8]

        question = (request.question or "").strip()
        if not question:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty.",
            )

        # Authenticated user_id takes absolute precedence over client request.user_id
        effective_user_id = str(user_id) if user_id else (str(request.user_id) if request.user_id else None)
        if user_id and request.user_id and str(user_id) != str(request.user_id):
            logger.warning(
                "Overriding client-provided user_id %s with authenticated token user_id %s",
                request.user_id,
                user_id,
            )

        conv_hist = conversation_history or request.conversation_history

        logger.info(
            "RAG [%s] Query start: user_id=%s, conv_id=%s, question_len=%d, has_history=%s",
            request_id,
            effective_user_id,
            request.conversation_id,
            len(question),
            bool(conv_hist),
        )

        # ----------------------------------------------------
        # Step 1: Retrieval with Context & Calibrated Grounding Gate
        # ----------------------------------------------------
        t0 = time.perf_counter()
        retriever = self.get_retriever()
        try:
            user_id_str = effective_user_id
            doc_id_str = str(request.document_id) if request.document_id else None
            documents = retriever.search(
                question,
                user_id=user_id_str,
                document_id=doc_id_str,
                conversation_history=conv_hist,
            )
            if request.top_k and request.top_k > 0:
                documents = documents[:request.top_k]
            retrieval_ms = (time.perf_counter() - t0) * 1000.0
            logger.info("RAG [%s] Retrieved %d candidates (%.2fms).", request_id, len(documents), retrieval_ms)
        except ValueError as val_err:
            logger.warning("Retrieval validation failed: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(val_err),
            )
        except Exception as search_err:
            logger.exception("Retrieval execution failed: %s", search_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during document retrieval.",
            )

        # ----------------------------------------------------
        # Step 2: Grounding Gate Check
        # ----------------------------------------------------
        if not documents:
            logger.info("RAG [%s] Grounding gate triggered: insufficient or ambiguous context.", request_id)
            return ChatQueryResponse(
                answer="The provided documents do not contain enough information to answer this question.",
                sources=[],
                conversation_id=request.conversation_id,
                has_sufficient_context=False,
            )

        # Format structured sources (filter out duplicates and ungrounded chunks)
        sources: List[ChatSource] = []
        seen_citations = set()
        for doc in documents:
            score = round(float(doc.get("rerank_score", doc.get("score", 0.0))), 4)
            source_name = doc.get("source", "Unknown")
            page_num = doc.get("page")
            cit_key = (source_name, page_num)
            if cit_key not in seen_citations:
                seen_citations.add(cit_key)
                sources.append(
                    ChatSource(
                        source=source_name,
                        page=page_num,
                        file_type=doc.get("file_type"),
                        score=score,
                    )
                )

        # ----------------------------------------------------
        # Step 3: Grounded Generation via Local Qwen
        # ----------------------------------------------------
        t1 = time.perf_counter()
        generator = self.get_generator()
        try:
            answer = generator.generate(question, documents)
            gen_ms = (time.perf_counter() - t1) * 1000.0
        except Exception as gen_err:
            logger.exception("Generation execution failed: %s", gen_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during answer generation.",
            )

        # Check for local LLM connectivity failure
        if answer.startswith("[ERROR]"):
            logger.error("LLM generator reported error: %s", answer)
            if "make sure the local llm server is running" in answer.lower():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Local LLM server (Qwen) is currently unreachable on port 8080. Please ensure llama-server is running.",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=answer,
            )

        missing_context_phrase = "the provided documents do not contain enough information to answer this question"
        has_sufficient = missing_context_phrase not in answer.lower()

        # If answer says documents lack info, clear citations to maintain strict grounding integrity
        if not has_sufficient:
            sources = []

        total_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "RAG [%s] Complete: answer_len=%d, has_context=%s, sources=%d, total_latency=%.2fms",
            request_id,
            len(answer),
            has_sufficient,
            len(sources),
            total_ms,
        )

        return ChatQueryResponse(
            answer=answer,
            sources=sources,
            conversation_id=request.conversation_id,
            has_sufficient_context=has_sufficient,
        )

    def ingest_document(
        self,
        file_path: Path,
        user_id: UUID,
        document_id: UUID,
    ):
        """
        Prepared integration point for future document uploads and Supabase Storage.
        Will invoke load_file_with_metadata and push to vector store.
        """
        logger.info(
            "Prepared ingestion point called for file=%s, user_id=%s, doc_id=%s",
            file_path.name,
            user_id,
            document_id,
        )
        from ingestion.ingestion import load_file_with_metadata
        return load_file_with_metadata(
            file_path=file_path,
            user_id=str(user_id),
            document_id=str(document_id),
        )


rag_service = RAGService()
