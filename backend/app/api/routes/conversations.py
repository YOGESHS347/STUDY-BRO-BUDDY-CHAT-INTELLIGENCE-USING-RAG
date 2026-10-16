import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.schemas.chat import ChatQueryRequest
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDeleteResponse,
    ConversationResponse,
)
from app.schemas.message import (
    ConversationExchangeResponse,
    MessageResponse,
    MessageSendRequest,
)
from app.services.conversation_service import conversation_service
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: Optional[ConversationCreate] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> ConversationResponse:
    """
    Creates a new conversation for the authenticated user.
    The user_id is derived strictly from the verified JWT sub claim.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    # Ensure foreign key record exists
    conversation_service.ensure_user_exists(db, current_user)

    title = payload.title if payload and payload.title else "New Conversation"
    conv = conversation_service.create_conversation(
        db=db,
        user_id=current_user.id,
        title=title,
    )
    return conv


@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    current_user: AuthenticatedUser = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(100, ge=1, le=500, description="Limit for pagination"),
    db: Optional[Session] = Depends(get_db),
) -> List[ConversationResponse]:
    """
    Retrieve all conversations belonging to the authenticated user.
    Ordered by updated_at DESC.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    return conversation_service.get_conversations_by_user(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> ConversationResponse:
    """
    Retrieve a single conversation by ID.
    Enforces multi-tenant ownership: returns 404 if conversation does not exist
    or does not belong to the authenticated user.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    conv = conversation_service.get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )
    return conv


@router.delete("/{conversation_id}", response_model=ConversationDeleteResponse)
def delete_conversation(
    conversation_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> ConversationDeleteResponse:
    """
    Delete a conversation and its messages.
    Only the conversation owner can delete it.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    deleted = conversation_service.delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    return ConversationDeleteResponse(
        message="Conversation and associated messages deleted successfully.",
        conversation_id=conversation_id,
    )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def list_conversation_messages(
    conversation_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(100, ge=1, le=500, description="Limit for pagination"),
    db: Optional[Session] = Depends(get_db),
) -> List[MessageResponse]:
    """
    Retrieve chronological messages for a conversation (created_at ASC).
    Enforces tenant isolation: caller must be the conversation owner.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    conv = conversation_service.get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    return conversation_service.get_messages_by_conversation(
        db=db,
        conversation_id=conversation_id,
        skip=skip,
        limit=limit,
    )


@router.post("/{conversation_id}/messages", response_model=ConversationExchangeResponse)
async def send_conversation_message(
    conversation_id: UUID,
    request: MessageSendRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> ConversationExchangeResponse:
    """
    Send a user message to a conversation, execute RAG generation,
    persist the assistant answer, and return the exchange with citations.

    Flow:
    1. Verify JWT & extract authoritative user_id.
    2. Verify conversation exists and belongs to authenticated user.
    3. Validate message content.
    4. Persist USER message.
    5. Execute RAG service query scoped to current_user.id.
    6. Persist ASSISTANT message & update conversation.updated_at.
    7. Return user_message, assistant_message, and sources.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    # 1. Verify conversation ownership
    conv = conversation_service.get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    # 2. Validate message content
    content = (request.content or "").strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty.",
        )

    # 3. Persist USER message
    try:
        user_msg = conversation_service.save_user_message(
            db=db,
            conversation_id=conversation_id,
            content=content,
        )
    except Exception as db_err:
        logger.exception("Failed to persist user message: %s", type(db_err).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record user message.",
        )

    # 4. Call RAG service with authoritative user_id and recent conversation history
    prior_msgs = conversation_service.get_messages_by_conversation(
        db=db,
        conversation_id=conversation_id,
        limit=10,
    )
    conv_history = [
        {"role": m.role, "content": m.content}
        for m in prior_msgs
        if m.id != user_msg.id
    ]

    rag_request = ChatQueryRequest(
        question=content,
        conversation_id=conversation_id,
    )
    try:
        rag_response = await rag_service.query(
            rag_request,
            user_id=current_user.id,
            conversation_history=conv_history,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (e.g. 503 LLM unavailable)
        # Note: user_msg is preserved, but no fake assistant message is created
        raise
    except Exception as rag_err:
        logger.exception("Unhandled error during RAG query: %s", type(rag_err).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during RAG generation.",
        )

    # 5. Persist ASSISTANT message only upon successful generation
    try:
        assistant_msg = conversation_service.save_assistant_message_and_update(
            db=db,
            conversation_id=conversation_id,
            content=rag_response.answer,
            user_prompt=content,
        )
    except Exception as save_err:
        logger.exception("Failed to persist assistant message: %s", type(save_err).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record assistant response.",
        )

    return ConversationExchangeResponse(
        user_message=MessageResponse.model_validate(user_msg),
        assistant_message=MessageResponse.model_validate(assistant_msg),
        sources=rag_response.sources,
    )
