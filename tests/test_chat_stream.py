from collections.abc import AsyncIterator
from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.requests import ClientDisconnect

from src.api.chat import chat_stream
from src.llm.types import LLMResponse, Message
from src.services.chat_service import ChatService
from src.types.chat import ChatRequest


class RepoFinto:
    def __init__(self) -> None:
        self.messages: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def add_message(self, *args: object, **kwargs: object) -> None:
        self.messages.append((args, kwargs))


class SessionFinta:
    committed = False

    async def commit(self) -> None:
        self.committed = True


class LLMFinto:
    async def stream(self, _messages: list[Message]) -> AsyncIterator[str | LLMResponse]:
        yield "Risposta "
        yield "completa"
        yield LLMResponse(
            content="Risposta completa",
            tokens_used=12,
            cost_eur=Decimal("0.00125"),
            model="gpt-4o-mini",
        )


class ServiceFinto:
    def __init__(self, service: ChatService) -> None:
        self.service = service

    async def chat_stream(self, _req: ChatRequest, user_id: str) -> AsyncIterator[str]:
        assert user_id == "mbianchi"
        return self.service._pezzi(
            SimpleNamespace(id="sessione"), "domanda", [Message(role="user", content="domanda")]
        )


async def test_disconnect_smette_di_inviare_ma_salva_risposta_e_costo() -> None:
    session = SessionFinta()
    repo = RepoFinto()
    service = object.__new__(ChatService)
    service.session = session
    service.repo = repo
    service.llm = LLMFinto()

    class RequestFinta:
        async def is_disconnected(self) -> bool:
            return True

    response = await chat_stream(
        ChatRequest(session_id="new", message="domanda"),
        RequestFinta(),  # type: ignore[arg-type]
        ServiceFinto(service),  # type: ignore[arg-type]
    )
    eventi = [evento async for evento in response.body_iterator]

    assert len(eventi) == 1
    assert '"text": "Risposta "' in eventi[0]
    assert session.committed
    assert repo.messages[0][0][:3] == ("sessione", "user", "domanda")
    assert repo.messages[1][0][:3] == ("sessione", "assistant", "Risposta completa")
    assert repo.messages[1][1]["tokens"] == 12
    assert repo.messages[1][1]["cost_eur"] == Decimal("0.00125")


async def test_chiusura_dello_stream_attende_il_salvataggio() -> None:
    session = SessionFinta()
    repo = RepoFinto()
    service = object.__new__(ChatService)
    service.session = session
    service.repo = repo
    service.llm = LLMFinto()

    class RequestConnessa:
        async def is_disconnected(self) -> bool:
            return False

    response = await chat_stream(
        ChatRequest(session_id="new", message="domanda"),
        RequestConnessa(),  # type: ignore[arg-type]
        ServiceFinto(service),  # type: ignore[arg-type]
    )
    messaggi_inviati: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        messaggi_inviati.append(message)
        if message["type"] == "http.response.body" and message["body"]:
            raise OSError("client disconnected")

    with pytest.raises(ClientDisconnect):
        await response(
            {"type": "http", "asgi": {"spec_version": "2.4"}},
            receive,
            send,  # type: ignore[arg-type]
        )

    assert b'"text": "Risposta "' in messaggi_inviati[1]["body"]
    assert session.committed
    assert repo.messages[1][1]["cost_eur"] == Decimal("0.00125")
