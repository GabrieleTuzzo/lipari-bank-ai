# src/api/chat.py — la chat, con il modello, intera o in streaming
import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import Receive, Scope, Send

from src.config import settings
from src.db.session import get_db
from src.llm.client import LLMProvider
from src.llm.factory import get_llm_provider
from src.llm.prompt import load_prompt
from src.services.chat_service import ChatService
from src.types.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/ai", tags=["Chat"])

SYSTEM_PROMPT = load_prompt("chat_system_v1")
OPERATORE = "mbianchi"  # finto fino al Giorno 6: l'operatore del seed. Poi arriva dal token


def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> ChatService:
    return ChatService(session, llm, SYSTEM_PROMPT, settings.daily_budget_eur)


class PersistedStreamingResponse(StreamingResponse):
    def __init__(self, content: AsyncGenerator[str, None]) -> None:
        self._content = content
        super().__init__(content, media_type="text/event-stream")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self._content.aclose()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest, service: Annotated[ChatService, Depends(get_chat_service)]
) -> ChatResponse:
    return await service.chat(req, user_id=OPERATORE)


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    pezzi = await service.chat_stream(req, user_id=OPERATORE)  # un 404 esce qui, prima dello stream

    async def eventi() -> AsyncGenerator[str, None]:
        coda: asyncio.Queue[str | Exception | None] = asyncio.Queue()

        async def consuma_stream() -> None:
            try:
                async for pezzo in pezzi:
                    await coda.put(pezzo)
            except Exception as exc:
                await coda.put(exc)
            finally:
                await coda.put(None)

        produttore = asyncio.create_task(consuma_stream())
        try:
            while True:
                try:
                    pezzo = await asyncio.wait_for(coda.get(), timeout=0.1)
                except TimeoutError:
                    if await request.is_disconnected():
                        await asyncio.shield(produttore)
                        return
                    continue
                if pezzo is None:
                    break
                if isinstance(pezzo, Exception):
                    raise pezzo
                # Ogni evento è JSON: un a capo dentro il testo non rompe il formato.
                yield f"data: {json.dumps({'text': pezzo}, ensure_ascii=False)}\n\n"
                if await request.is_disconnected():
                    # Non interrompere il provider: la risposta finale contiene il costo reale.
                    await asyncio.shield(produttore)
                    return
            await produttore
        except asyncio.CancelledError:
            # Starlette può cancellare lo stream appena rileva il disconnect; il produttore
            # indipendente finisce comunque la risposta e il salvataggio prima della chiusura DB.
            await asyncio.shield(produttore)
            raise
        finally:
            if not produttore.done():
                await asyncio.shield(produttore)
        yield "data: [DONE]\n\n"

    return PersistedStreamingResponse(eventi())
