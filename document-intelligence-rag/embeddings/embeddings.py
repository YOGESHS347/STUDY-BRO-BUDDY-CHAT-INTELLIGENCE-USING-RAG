import logging
from typing import List

import torch
from sentence_transformers import SentenceTransformer
from langchain_core.documents import Document

from config import EMBEDDING_MODEL_NAME


logger = logging.getLogger(__name__)

# Automatically use NVIDIA GPU if CUDA is available.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ============================================================
# EMBEDDING MODEL
# ============================================================

class EmbeddingModel:
    """
    Handles document and query embeddings.

    Uses CUDA when an NVIDIA GPU is available,
    otherwise falls back to CPU.
    """

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
    ):
        logger.info("Initializing embedding model: %s on device: %s", model_name, DEVICE)

        try:
            self.model = SentenceTransformer(
                model_name,
                device=DEVICE,
            )
            logger.info("Embedding model loaded successfully.")

            if DEVICE == "cuda":
                logger.info("GPU: %s | CUDA: %s", torch.cuda.get_device_name(0), torch.version.cuda)
        except Exception as error:
            logger.exception("Failed to load embedding model '%s': %s", model_name, error)
            raise RuntimeError(f"Embedding model initialization failed: {error}") from error

    # ========================================================
    # DOCUMENT EMBEDDINGS
    # ========================================================

    def embed_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
    ) -> List[List[float]]:
        """
        Convert document chunks into embedding vectors.

        batch_size controls how many chunks are processed
        at a time.
        """

        if not documents:
            return []

        texts = [
            document.page_content
            for document in documents
        ]
        logger.debug("Embedding %d documents with batch size %d", len(texts), batch_size)

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return embeddings.tolist()

    # ========================================================
    # SINGLE QUERY EMBEDDING
    # ========================================================

    def embed_query(
        self,
        query: str,
    ) -> List[float]:
        """
        Convert a user's query into an embedding vector.
        """

        if not query.strip():
            return []

        embedding = self.model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return embedding.tolist()

    # ========================================================
    # VECTOR DIMENSION
    # ========================================================

    def dimension(self) -> int:
        """
        Return the dimensionality of the embedding vector.
        """

        dimension = (
            self.model.get_embedding_dimension()
        )

        return int(dimension)

    # ========================================================
    # DEVICE
    # ========================================================

    def get_device(self) -> str:
        """
        Return the device currently being used.
        """

        return DEVICE


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    embedding_model = EmbeddingModel()

    print()
    print(
        f"[INFO] Vector dimension: "
        f"{embedding_model.dimension()}"
    )

    # --------------------------------------------------------
    # TEST DOCUMENTS
    # --------------------------------------------------------

    test_documents = [

        Document(
            page_content=(
                "CPU scheduling determines which process "
                "will be executed by the CPU."
            ),
            metadata={
                "source": "test.pdf",
                "page": 1,
            },
        ),

        Document(
            page_content=(
                "Operating systems manage processes, "
                "memory, files and hardware resources."
            ),
            metadata={
                "source": "test.pdf",
                "page": 2,
            },
        ),

    ]

    # --------------------------------------------------------
    # EMBED DOCUMENTS
    # --------------------------------------------------------

    document_embeddings = (
        embedding_model.embed_documents(
            test_documents
        )
    )

    print()
    print(
        f"[TEST] Documents embedded: "
        f"{len(document_embeddings)}"
    )

    print(
        f"[TEST] Vector dimension: "
        f"{len(document_embeddings[0])}"
    )

    print(
        f"[TEST] First 10 values:"
    )

    print(
        document_embeddings[0][:10]
    )

    # --------------------------------------------------------
    # EMBED QUERY
    # --------------------------------------------------------

    query = "What is CPU scheduling?"

    query_embedding = (
        embedding_model.embed_query(
            query
        )
    )

    print()
    print(
        f"[TEST] Query: {query}"
    )

    print(
        f"[TEST] Query vector dimension: "
        f"{len(query_embedding)}"
    )

    print(
        "[TEST] First 10 query values:"
    )

    print(
        query_embedding[:10]
    )

    # --------------------------------------------------------
    # FINAL TEST
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("EMBEDDING TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)