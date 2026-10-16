import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthenticatedUser, get_current_user
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=ChatQueryResponse)
async def query_chat(
    request: ChatQueryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ChatQueryResponse:
    """
    Protected RAG Question-Answering endpoint.
    Scoping is strictly bound to the authenticated user's verified token identity.
    Client-provided user_id in JSON payload is ignored for security.
    """
    try:
        response = await rag_service.query(request, user_id=current_user.id)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled error processing RAG chat query: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while processing the question.",
        )
