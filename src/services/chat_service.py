# src/services/chat_service.py — la conversazione: cosa significa, e dove finisce la transazione
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repos import ChatRepository
from src.exceptions import ChatSessionNotFoundError
from src.types.chat import ChatRequest, ChatResponse


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ChatRepository(session)

    async def chat(self, req: ChatRequest, user_id: str) -> ChatResponse:
        # la conversazione di prima, se esiste ed è di chi chiede; con "new", una nuova
        if req.session_id != "new":
            chat = await self.repo.find_session(req.session_id, user_id)
            if chat is None:
                raise ChatSessionNotFoundError(req.session_id)
        else:
            chat = await self.repo.create_session(user_id=user_id)

        await self.repo.add_message(chat.id, "user", req.message)

        # dal Giorno 4 risponde un modello; per ora un'eco
        reply = f"Echo: {req.message}"
        costo = Decimal("0.0001")
        await self.repo.add_message(
            chat.id, "assistant", reply, tokens=10, cost_eur=costo, model_used="dummy"
        )

        await self.session.commit()  # una volta sola: le due scritture valgono insieme

        return ChatResponse(
            session_id=chat.id,
            reply=reply,
            tokens_used=10,
            cost_eur=float(costo),  # nella risposta JSON il costo è un numero
            model_used="dummy",
            created_at=datetime.now(UTC),
        )
