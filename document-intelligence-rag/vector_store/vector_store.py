from pathlib import Path
from typing import List, Optional
from uuid import uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)

from ingestion.ingestion import load_all_documents
from embeddings.embeddings import EmbeddingModel
from config import (
    VECTOR_DB_PATH,
    COLLECTION_NAME,
    VECTOR_DIMENSION,
    VECTOR_STORE_BACKEND,
    QDRANT_URL,
    QDRANT_API_KEY,
)


# ============================================================
# VECTOR STORE
# ============================================================

class VectorStore:

    def __init__(
        self,
        db_path: Path = VECTOR_DB_PATH,
        collection_name: str = COLLECTION_NAME,
        vector_dimension: int = VECTOR_DIMENSION,
        backend: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
    ):
        self.db_path = Path(db_path)
        self.collection_name = collection_name
        self.vector_dimension = vector_dimension
        self.backend = backend or VECTOR_STORE_BACKEND

        # Connect to either Qdrant Cloud or Local Qdrant
        if self.backend == "qdrant_cloud" and (qdrant_url or QDRANT_URL):
            url = qdrant_url or QDRANT_URL
            api_key = qdrant_api_key or QDRANT_API_KEY
            print(f"[QDRANT] Connecting VectorStore to Qdrant Cloud: {url}")
            self.client = QdrantClient(
                url=url,
                api_key=api_key,
            )
        else:
            print(f"[QDRANT] Connecting VectorStore to local path: {self.db_path}")
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            self.client = QdrantClient(
                path=str(self.db_path)
            )

        self._create_collection()

    # ========================================================
    # CREATE COLLECTION
    # ========================================================

    def _create_collection(self):

        try:
            collections = (
                self.client
                .get_collections()
                .collections
            )
            collection_names = [
                collection.name
                for collection in collections
            ]
        except Exception as e:
            print(f"[QDRANT] Warning getting collections: {e}")
            collection_names = []

        if self.collection_name not in collection_names:

            self.client.create_collection(

                collection_name=self.collection_name,

                vectors_config=VectorParams(
                    size=self.vector_dimension,
                    distance=Distance.COSINE,
                ),
            )

            print(
                f"[QDRANT] Collection '{self.collection_name}' created."
            )

        # Create payload indexes for user_id and document_id for multi-tenant isolation performance
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="user_id",
                field_schema="keyword",
            )
        except Exception:
            pass

        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="document_id",
                field_schema="keyword",
            )
        except Exception:
            pass

    # ========================================================
    # CLEAR COLLECTION
    # ========================================================

    def clear(self):

        if self.client.collection_exists(
            self.collection_name
        ):

            self.client.delete_collection(
                self.collection_name
            )

            print(
                "[QDRANT] Collection deleted."
            )

        self._create_collection()

        print(
            "[QDRANT] Collection recreated."
        )

    # ========================================================
    # ADD DOCUMENTS
    # ========================================================

    def add_documents(
        self,
        documents: List,
        embeddings: List[List[float]],
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ):

        if not documents:
            print(
                "[QDRANT] No documents to store."
            )
            return

        if len(documents) != len(embeddings):

            raise ValueError(
                "Documents and embeddings "
                "count do not match."
            )

        points = []

        for document, embedding in zip(
            documents,
            embeddings,
        ):

            metadata = (
                document.metadata.copy()
                if hasattr(document, "metadata") and document.metadata
                else {}
            )

            resolved_user_id = user_id or metadata.get("user_id")
            resolved_document_id = document_id or metadata.get("document_id")

            # In cloud mode, multi-tenant isolation requires user_id and document_id
            if self.backend == "qdrant_cloud":
                if not resolved_user_id or not str(resolved_user_id).strip():
                    raise ValueError(
                        "user_id and document_id are strictly required for cloud vector storage."
                    )
                if not resolved_document_id or not str(resolved_document_id).strip():
                    raise ValueError(
                        "user_id and document_id are strictly required for cloud vector storage."
                    )

            # ------------------------------------------------
            # Basic metadata
            # ------------------------------------------------

            doc_id_val = (
                str(resolved_document_id)
                if resolved_document_id
                else metadata.get("source", "unknown")
            )

            source = metadata.get(
                "source",
                str(resolved_document_id) if resolved_document_id else "Unknown",
            )

            file_type = metadata.get(
                "file_type",
                "unknown",
            )

            content_type = metadata.get(
                "content_type",
                "unknown",
            )

            chunk_index = metadata.get(
                "chunk_index",
                0,
            )

            chunk_id = metadata.get(
                "chunk_id",
                f"{doc_id_val}_chunk_{chunk_index}",
            )

            # ------------------------------------------------
            # Create deterministic point ID
            # ------------------------------------------------

            if resolved_user_id:
                unique_string = (
                    f"{resolved_user_id}|"
                    f"{doc_id_val}|"
                    f"{chunk_id}|"
                    f"{document.page_content}"
                )
            else:
                unique_string = (
                    f"{doc_id_val}|"
                    f"{chunk_id}|"
                    f"{document.page_content}"
                )

            point_id = str(
                uuid5(
                    NAMESPACE_URL,
                    unique_string,
                )
            )

            # ------------------------------------------------
            # Build Qdrant payload
            # ------------------------------------------------

            payload = {

                # Actual chunk text
                "text": document.page_content,

                # Document information
                "document_id": doc_id_val,

                "source": source,

                "file_type": file_type,

                # Content information
                "content_type": content_type,

                # Chunk information
                "chunk_id": chunk_id,

                "chunk_index": chunk_index,
            }

            if resolved_user_id:
                payload["user_id"] = str(resolved_user_id)

            # ------------------------------------------------
            # Preserve all additional metadata
            # ------------------------------------------------

            for key, value in metadata.items():

                if key not in payload:

                    payload[key] = value

            # ------------------------------------------------
            # Create Qdrant point
            # ------------------------------------------------

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        # ----------------------------------------------------
        # Store vectors
        # ----------------------------------------------------

        self.client.upsert(

            collection_name=self.collection_name,

            points=points,
        )

        print(
            f"[QDRANT] Stored "
            f"{len(points)} vectors."
        )

    # ========================================================
    # COUNT VECTORS
    # ========================================================

    def count(self) -> int:

        result = self.client.count(

            collection_name=self.collection_name,

            exact=True,
        )

        return result.count

    # ========================================================
    # GET SAMPLE
    # ========================================================

    def get_sample(self):

        """
        Retrieve one stored point so we can
        inspect the metadata.
        """

        result = self.client.scroll(

            collection_name=self.collection_name,

            limit=1,

            with_payload=True,

            with_vectors=False,
        )

        points = result[0]

        if not points:

            return None

        return points[0]

    # ========================================================
    # DELETE DOCUMENT VECTORS
    # ========================================================

    def delete_document_vectors(
        self,
        document_id: str,
        user_id: str,
    ) -> None:
        """
        Delete all vector points belonging to a specific document_id and user_id.
        Ensures strict tenant isolation so only the owner's vectors are deleted.
        """
        from qdrant_client.models import (
            Filter,
            FieldCondition,
            MatchValue,
            FilterSelector,
        )

        del_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=str(user_id)),
                ),
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=str(document_id)),
                ),
            ]
        )

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=del_filter),
        )

        print(
            f"[QDRANT] Deleted vectors for doc_id={document_id}, user_id={user_id}"
        )

    def close(self):
        """Closes the underlying Qdrant client connection releasing local locks."""
        if hasattr(self, "client") and self.client:
            try:
                self.client.close()
            except Exception:
                pass


# ============================================================
# BUILD VECTOR DATABASE
# ============================================================

def build_vector_database():

    print()
    print("=" * 60)
    print("BUILDING VECTOR DATABASE")
    print("=" * 60)

    # --------------------------------------------------------
    # Step 1: Load documents
    # --------------------------------------------------------

    documents = list(
        load_all_documents("data")
    )

    print()
    print(
        f"[PIPELINE] Total chunks: "
        f"{len(documents)}"
    )

    if not documents:

        print(
            "[ERROR] No documents found."
        )

        return

    # --------------------------------------------------------
    # Step 2: Load embedding model
    # --------------------------------------------------------

    embedding_model = EmbeddingModel()

    print(
        f"[EMBEDDINGS] Dimension: "
        f"{embedding_model.dimension()}"
    )

    print(
        f"[EMBEDDINGS] Device: "
        f"{embedding_model.get_device()}"
    )

    # --------------------------------------------------------
    # Step 3: Create embeddings
    # --------------------------------------------------------

    embeddings = (
        embedding_model.embed_documents(
            documents,
            batch_size=32,
        )
    )

    print()
    print(
        f"[PIPELINE] Created "
        f"{len(embeddings)} embeddings."
    )

    # --------------------------------------------------------
    # Step 4: Remove old local Qdrant database
    # --------------------------------------------------------

    qdrant_path = Path(
        VECTOR_DB_PATH
    )

    if qdrant_path.exists():

        import shutil

        print(
            "[QDRANT] Removing old "
            "local database..."
        )

        shutil.rmtree(
            qdrant_path
        )

        print(
            "[QDRANT] Old database removed."
        )

    # --------------------------------------------------------
    # Step 5: Create completely fresh Qdrant
    # --------------------------------------------------------

    vector_store = VectorStore(

        vector_dimension=(
            embedding_model.dimension()
        )
    )

    # --------------------------------------------------------
    # Step 6: Store vectors + metadata
    # --------------------------------------------------------

    vector_store.add_documents(
        documents,
        embeddings,
    )

    # --------------------------------------------------------
    # Step 7: Verify count
    # --------------------------------------------------------

    total_vectors = (
        vector_store.count()
    )

    print()
    print(
        f"[PIPELINE] Total vectors "
        f"in Qdrant: {total_vectors}"
    )

    # --------------------------------------------------------
    # Step 8: Verify vector count
    # --------------------------------------------------------

    if total_vectors != len(documents):

        print()
        print(
            "[WARNING] Vector count does "
            "not match chunk count!"
        )

        print(
            f"Chunks:  {len(documents)}"
        )

        print(
            f"Vectors: {total_vectors}"
        )

    else:

        print()
        print(
            "[SUCCESS] Chunk count and "
            "vector count match."
        )

    # --------------------------------------------------------
    # Step 9: Inspect one stored point
    # --------------------------------------------------------

    sample = (
        vector_store.get_sample()
    )

    if sample:

        print()
        print("=" * 60)
        print("QDRANT SAMPLE")
        print("=" * 60)

        print(
            f"Point ID: {sample.id}"
        )

        print()
        print("Payload:")

        for key, value in (
            sample.payload or {}
        ).items():

            print(
                f"{key}: {value}"
            )

    print()
    print("=" * 60)
    print("VECTOR DATABASE BUILD COMPLETE")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    build_vector_database()