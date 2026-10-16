import os
import uuid
from pathlib import Path
import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue

# Ensure environment variables are loaded
from app.core.config import settings
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
RAG_ENGINE_DIR = PROJECT_ROOT / "document-intelligence-rag"
if str(RAG_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_ENGINE_DIR))

from config import (
    VECTOR_DB_PATH,
    COLLECTION_NAME,
    VECTOR_DIMENSION,
    VECTOR_STORE_BACKEND,
    QDRANT_URL,
    QDRANT_API_KEY,
)
from vector_store.vector_store import VectorStore
from retrieval.retrieval import Retriever
from embeddings.embeddings import EmbeddingModel


class MockDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


def test_qdrant_cloud_connection_and_schema():
    """
    Verify Qdrant Cloud connection, authentication, and production collection schema.
    Production collection 'documents' must exist with dimension 384 and Cosine distance.
    Local 4,125 vectors must NOT be migrated to the cloud.
    """
    assert QDRANT_URL, "QDRANT_URL must be configured"
    assert QDRANT_API_KEY, "QDRANT_API_KEY must be configured"

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    assert COLLECTION_NAME in collection_names, f"Collection '{COLLECTION_NAME}' must exist in Qdrant Cloud"

    info = client.get_collection(COLLECTION_NAME)
    # Validate vector size & distance
    vectors_config = info.config.params.vectors
    if hasattr(vectors_config, "size"):
        assert vectors_config.size == 384
        assert vectors_config.distance == Distance.COSINE
    elif isinstance(vectors_config, dict):
        # In case of named vectors
        default_vector = next(iter(vectors_config.values()))
        assert default_vector.size == 384
        assert default_vector.distance == Distance.COSINE

    # Confirm points count is unmigrated (local 4,125 vectors must not be copied)
    assert info.points_count < 4000, f"Cloud 'documents' collection has {info.points_count} points (local 4,125 vectors must not be copied)"


def test_qdrant_cloud_multi_tenant_isolation():
    """
    Verify strict tenant vector isolation on Qdrant Cloud using a temporary test collection.
    User A must never retrieve vectors belonging to User B and vice versa.
    """
    assert QDRANT_URL and QDRANT_API_KEY

    temp_coll_name = f"test_isolation_{uuid.uuid4().hex[:8]}"
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    try:
        # 1. Create temporary test collection
        client.create_collection(
            collection_name=temp_coll_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        client.create_payload_index(
            collection_name=temp_coll_name,
            field_name="user_id",
            field_schema="keyword",
        )

        store = VectorStore(
            collection_name=temp_coll_name,
            backend="qdrant_cloud",
            qdrant_url=QDRANT_URL,
            qdrant_api_key=QDRANT_API_KEY,
        )
        embed_model = EmbeddingModel()

        user_a_id = str(uuid.uuid4())
        doc_a_id = str(uuid.uuid4())
        text_a = "Quantum computing relies on superposition and quantum entanglement to process data."
        emb_a = embed_model.embed_query(text_a)

        user_b_id = str(uuid.uuid4())
        doc_b_id = str(uuid.uuid4())
        text_b = "Cellular photosynthesis synthesizes glucose from carbon dioxide, water, and sunlight."
        emb_b = embed_model.embed_query(text_b)

        doc_a = MockDoc(
            page_content=text_a,
            metadata={
                "source": "quantum_notes.pdf",
                "page": 1,
                "file_type": "pdf",
                "content_type": "text",
            },
        )
        doc_b = MockDoc(
            page_content=text_b,
            metadata={
                "source": "biology_notes.pdf",
                "page": 14,
                "file_type": "pdf",
                "content_type": "text",
            },
        )

        # 2. Ingest User A and User B vectors
        store.add_documents([doc_a], [emb_a], user_id=user_a_id, document_id=doc_a_id)
        store.add_documents([doc_b], [emb_b], user_id=user_b_id, document_id=doc_b_id)

        # 3. Verify total points in temporary collection
        count_res = client.count(collection_name=temp_coll_name, exact=True)
        assert count_res.count == 2

        # 4. Search as User A with user_id filter
        filter_a = Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_a_id))]
        )
        results_a = client.query_points(
            collection_name=temp_coll_name,
            query=emb_a,
            query_filter=filter_a,
            limit=5,
            with_payload=True,
        )
        assert len(results_a.points) == 1
        assert results_a.points[0].payload["user_id"] == user_a_id
        assert results_a.points[0].payload["document_id"] == doc_a_id
        assert "Quantum" in results_a.points[0].payload["text"]

        # 5. Search as User B with user_id filter using User A's query embedding
        # Even when querying with quantum concepts, User B must NEVER see User A's data!
        filter_b = Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_b_id))]
        )
        results_b = client.query_points(
            collection_name=temp_coll_name,
            query=emb_a,  # user A's query
            query_filter=filter_b,
            limit=5,
            with_payload=True,
        )
        # Should only return User B's documents
        for pt in results_b.points:
            assert pt.payload["user_id"] == user_b_id
            assert pt.payload["user_id"] != user_a_id
            assert "Quantum" not in pt.payload["text"]

    finally:
        # 6. Cleanup temporary test collection
        try:
            client.delete_collection(collection_name=temp_coll_name)
        except Exception:
            pass


def test_qdrant_cloud_missing_user_id_fails_safely():
    """
    Verify that in cloud mode, missing user_id raises ValueError to prevent unrestricted searches
    and un-isolated writes.
    """
    import retrieval.retrieval as ret_module
    orig_backend = ret_module.VECTOR_STORE_BACKEND
    try:
        ret_module.VECTOR_STORE_BACKEND = "qdrant_cloud"
        retriever = Retriever()

        # Missing user_id in semantic_search should raise ValueError
        with pytest.raises(ValueError, match="user_id is strictly required"):
            retriever.semantic_search("quantum computing", user_id=None)

        with pytest.raises(ValueError, match="user_id is strictly required"):
            retriever.semantic_search("quantum computing", user_id="")

        # Missing user_id in VectorStore.add_documents with cloud backend should raise ValueError
        store = VectorStore(
            collection_name="documents",
            backend="qdrant_cloud",
            qdrant_url=QDRANT_URL,
            qdrant_api_key=QDRANT_API_KEY,
        )
        mock_doc = MockDoc("some text", {})
        with pytest.raises(ValueError, match="user_id and document_id are strictly required"):
            store.add_documents([mock_doc], [[0.0] * 384], user_id=None, document_id="some-id")

        with pytest.raises(ValueError, match="user_id and document_id are strictly required"):
            store.add_documents([mock_doc], [[0.0] * 384], user_id="user-123", document_id=None)

    finally:
        ret_module.VECTOR_STORE_BACKEND = orig_backend


def test_local_qdrant_database_preserved():
    """
    Verify that local Qdrant database (4,125 vectors) is fully preserved, unmodified,
    and supports unauthenticated backward-compatible local retrieval when user_id is None.
    """
    local_client = QdrantClient(path=str(VECTOR_DB_PATH))
    try:
        count = local_client.count(collection_name=COLLECTION_NAME, exact=True).count
        assert count == 4125, f"Local Qdrant collection must contain exactly 4,125 points, found {count}"
    finally:
        local_client.close()

    import retrieval.retrieval as ret_module
    orig_backend = ret_module.VECTOR_STORE_BACKEND
    try:
        ret_module.VECTOR_STORE_BACKEND = "local"
        retriever = Retriever()
        try:
            # In local mode, user_id=None must succeed without raising ValueError
            results = retriever.semantic_search("What is encapsulation?", user_id=None)
            assert len(results) > 0
            assert results[0]["semantic_score"] >= 0.40
        finally:
            if hasattr(retriever.client, "close"):
                retriever.client.close()
    finally:
        ret_module.VECTOR_STORE_BACKEND = orig_backend
