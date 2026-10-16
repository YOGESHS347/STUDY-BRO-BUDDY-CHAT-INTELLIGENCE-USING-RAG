import os
import logging
from typing import Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Automatically load backend/.env if available
try:
    from dotenv import load_dotenv
    backend_env_path = os.path.join(os.path.dirname(BASE_DIR), "backend", ".env")
    if os.path.exists(backend_env_path):
        load_dotenv(backend_env_path)
except Exception:
    pass

# ============================================================
# VECTOR DATABASE CONFIGURATION
# ============================================================

VECTOR_STORE_BACKEND = os.getenv("VECTOR_STORE_BACKEND", "local")
VECTOR_DB_PATH = os.path.join(BASE_DIR, "vector_db", "qdrant")
COLLECTION_NAME = "documents"

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


# ============================================================
# EMBEDDINGS CONFIGURATION
# ============================================================

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
VECTOR_DIMENSION = EMBEDDING_DIMENSION


# ============================================================
# RETRIEVAL CONFIGURATION
# ============================================================

TOP_K_PER_QUERY = 20
FINAL_PER_QUERY = 5
SINGLE_QUERY_FINAL_K = 7
SIMILARITY_THRESHOLD = 0.40


# ============================================================
# LLM / GENERATION CONFIGURATION
# ============================================================

LLM_MODEL_NAME = "Qwen/Qwen3-4B-GGUF:Q4_K_M"
LLM_SERVER_URL = "http://127.0.0.1:8080/v1"
MAX_TOKENS = 1800
TEMPERATURE = 0.2



# ============================================================
# LOGGING SETUP
# ============================================================

LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "rag.log")


def setup_logging(
    log_level: int = logging.INFO,
    log_to_file: bool = True,
    log_file_path: str = LOG_FILE,
) -> None:
    """
    Configures centralized logging for the Document Intelligence RAG application.
    Logs detailed diagnostic information to a file while keeping console output clean.
    """
    handlers = []

    # File handler for detailed debug and operational logs
    if log_to_file:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Console handler for operational warnings and errors only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=handlers,
        force=True,
    )

    # Suppress verbose logs from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
