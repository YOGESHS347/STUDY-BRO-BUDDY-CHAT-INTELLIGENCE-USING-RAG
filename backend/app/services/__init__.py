"""Business logic and service abstractions."""
from app.services.user_service import user_service, UserService
from app.services.document_service import document_service, DocumentService
from app.services.conversation_service import conversation_service, ConversationService
from app.services.rag_service import rag_service, RAGService
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse

# Aliases for backward compatibility
RAGQueryRequest = ChatQueryRequest
RAGQueryResponse = ChatQueryResponse

__all__ = [
    "user_service",
    "UserService",
    "document_service",
    "DocumentService",
    "conversation_service",
    "ConversationService",
    "rag_service",
    "RAGService",
    "ChatQueryRequest",
    "ChatQueryResponse",
    "RAGQueryRequest",
    "RAGQueryResponse",
]
