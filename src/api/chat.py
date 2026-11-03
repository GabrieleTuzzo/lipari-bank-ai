# src/api/chat.py — la chat, con la conversazione salvata nel database
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.services.chat_service import ChatService
from src.types.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/ai", tags=["Chat"])


@router.post(
    "/chat",  # relativo al prefix: l'URL è /api/ai/chat
    response_model=ChatResponse,
    summary="Manda un messaggio all'assistente",
    description='Conversazione a più turni: con session_id "new" se ne apre una nuova.',
)
async def chat(
    req: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    service = ChatService(session)
    # user_id finto: l'autenticazione vera arriva al Giorno 6, e allora questa riga cambia
    return await service.chat(req, user_id="dummy-user")
