import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Service abstraction for conversation sessions and message history.
    Enforces user ownership for multi-user isolation.
    """

    @staticmethod
    def ensure_user_exists(db: Session, current_user: AuthenticatedUser) -> User:
        """
        Ensures a user record exists in the public users table for foreign keys.
        """
        user_record = db.get(User, current_user.id)
        if not user_record:
            user_record = User(
                id=current_user.id,
                email=str(current_user.email) if current_user.email else f"user_{current_user.id.hex[:12]}@local.test",
                password_hash="supabase_auth_managed",
            )
            db.add(user_record)
            db.commit()
            db.refresh(user_record)
        return user_record

    @staticmethod
    def get_conversations_by_user(
        db: Session,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Conversation]:
        """Fetch all conversations owned by a user, ordered by updated_at DESC."""
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_conversation_by_id(
        db: Session,
        conversation_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[Conversation]:
        """Fetch a specific conversation, optionally enforcing user ownership."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)
        return db.scalars(stmt).first()

    @staticmethod
    def create_conversation(
        db: Session,
        user_id: uuid.UUID,
        title: Optional[str] = "New Conversation",
    ) -> Conversation:
        """Create a new chat conversation for a user."""
        clean_title = (title or "").strip() or "New Conversation"
        if len(clean_title) > 500:
            clean_title = clean_title[:500]

        conv = Conversation(
            user_id=user_id,
            title=clean_title,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        logger.info("Created conversation %s for user %s with title '%s'", conv.id, user_id, clean_title)
        return conv

    @staticmethod
    def delete_conversation(
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Deletes a conversation and cascades message deletion, strictly enforcing ownership.
        Returns True if deleted, False if conversation not found or not owned.
        """
        conv = ConversationService.get_conversation_by_id(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        if not conv:
            return False

        db.delete(conv)
        db.commit()
        logger.info("Deleted conversation %s and associated messages for user %s", conversation_id, user_id)
        return True

    @staticmethod
    def get_messages_by_conversation(
        db: Session,
        conversation_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Message]:
        """Fetch messages within a conversation ordered chronologically (created_at ASC)."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def save_user_message(
        db: Session,
        conversation_id: uuid.UUID,
        content: str,
    ) -> Message:
        """
        Persists a user message in the conversation.
        """
        msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def save_assistant_message_and_update(
        db: Session,
        conversation_id: uuid.UUID,
        content: str,
        user_prompt: Optional[str] = None,
    ) -> Message:
        """
        Persists an assistant answer, updates conversation.updated_at,
        and deterministically updates title if it is still the default.
        """
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        db.add(msg)

        conv = db.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            # Deterministic title update if title is still default
            if conv.title in (None, "New Conversation", "") and user_prompt:
                trimmed = user_prompt.strip()
                if trimmed:
                    # Use first line or first 80 chars
                    first_line = trimmed.split("\n")[0].strip()
                    new_title = first_line[:80]
                    conv.title = new_title
                    logger.info("Auto-updated conversation %s title to '%s'", conversation_id, new_title)

        db.commit()
        db.refresh(msg)
        return msg


conversation_service = ConversationService()
