"""Conversation route — chat with Gemini about a storyboard for refinement."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.config import settings
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.services.conversational_storytelling import (
    clear_session,
    get_or_create_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])


class ConversationMessage(BaseModel):
    message: str


@router.post("/{request_id}/chat")
async def chat(
    request_id: uuid.UUID,
    data: ConversationMessage,
    session: AsyncSession = Depends(get_session),
):
    if not settings.conversation_mode_enabled:
        raise HTTPException(status_code=503, detail="Conversation mode is disabled")

    if not data.message.strip():
        raise HTTPException(status_code=422, detail="Message is required")

    repo = RequestRepository(session)
    gen_request = await repo.get(request_id)
    if not gen_request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    if not gen_request.storyboard_data:
        raise HTTPException(status_code=422, detail="No storyboard data available")

    conv_session = get_or_create_session(
        str(request_id),
        gen_request.storyboard_data,
    )

    try:
        result = await conv_session.send_message(data.message)
        return result
    except Exception as e:
        logger.error("Conversation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Conversation failed: {e}")


@router.delete("/{request_id}")
async def end_conversation(request_id: uuid.UUID):
    clear_session(str(request_id))
    return {"status": "ended"}
