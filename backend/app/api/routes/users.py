import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.schemas.user import UserResponse
from app.services.user_service import user_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> UserResponse:
    """
    Retrieve profile for the authenticated user.
    Never exposes password_hash, tokens, or other users' data.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    user = user_service.get_user_by_id(db, current_user.id)
    if not user:
        # If user record hasn't been flushed yet, synthesize response from verified claims
        return UserResponse(
            id=current_user.id,
            email=current_user.email or f"user_{current_user.id.hex[:12]}@local.test",
        )
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> UserResponse:
    """
    Retrieve user by ID.
    Enforces tenant isolation: callers can only retrieve their own profile.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    # Disallow viewing another user's profile
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )

    user = user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )
    return user
