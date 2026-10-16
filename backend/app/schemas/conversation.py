from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: Optional[str] = Field("New Conversation", max_length=500, description="Optional title for the conversation")


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDeleteResponse(BaseModel):
    message: str
    conversation_id: UUID
