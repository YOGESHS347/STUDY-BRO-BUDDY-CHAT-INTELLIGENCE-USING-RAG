from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import ChatSource


class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$", description="Role of the sender")
    content: str = Field(..., min_length=1, description="Message content")


class MessageSendRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000, description="Prompt/question to send in conversation")


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationExchangeResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    sources: List[ChatSource] = Field(default_factory=list)
