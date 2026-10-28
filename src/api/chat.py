# src/api/chat.py — endpoint minimo per verificare il contratto della chat
from datetime import UTC, datetime

from fastapi import APIRouter

from src.config import settings
from src.types.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/ai", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse, summary="Invia un messaggio")
async def chat(req: ChatRequest) -> ChatResponse:
    return ChatResponse(
        session_id=req.session_id,
        reply=f"Echo: {req.message}",
        tokens_used=0,
        cost_eur=0.0,
        model_used=settings.default_model,
        created_at=datetime.now(UTC),
    )
