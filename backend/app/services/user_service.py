import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate


class UserService:
    """Service handling user entity management and queries."""

    @staticmethod
    def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]:
        """Fetch user by primary key UUID."""
        stmt = select(User).where(User.id == user_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Fetch user by unique email."""
        stmt = select(User).where(User.email == email)
        return db.scalars(stmt).first()

    @staticmethod
    def create_user(db: Session, user_in: UserCreate, password_hash: str) -> User:
        """
        Create a new user record.
        Actual authentication hashing will be hooked into this in future auth phase.
        """
        user = User(
            email=user_in.email,
            password_hash=password_hash,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


user_service = UserService()
