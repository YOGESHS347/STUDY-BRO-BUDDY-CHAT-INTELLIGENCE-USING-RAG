from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    source: str
    page: Optional[int] = None
    file_type: Optional[str] = None
    score: Optional[float] = None


class ChatQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question for the RAG engine")
    user_id: Optional[UUID] = Field(None, description="Optional legacy user_id - ignored in favor of verified JWT identity")
    conversation_id: Optional[UUID] = Field(None, description="Optional conversation session ID")
    document_id: Optional[UUID] = Field(None, description="Optional document ID for single-document scoping")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="Optional maximum documents to retrieve")
    conversation_history: Optional[List[dict]] = Field(None, description="Optional recent message turns for follow-up resolution")


class ChatQueryResponse(BaseModel):
    answer: str
    sources: List[ChatSource] = Field(default_factory=list)
    conversation_id: Optional[UUID] = None
    has_sufficient_context: bool = True
