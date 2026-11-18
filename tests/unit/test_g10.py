from decimal import Decimal

import fakeredis
import pytest

from scripts import misura_tetti
from src.config import Settings
from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message, ToolSpec


class Modello:
    def __init__(self, testo: str) -> None:
        self.testo = testo
        self.calls = 0

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 500,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content=self.testo,
            tokens_used=100,
            cost_eur=Decimal("0.0001"),
            model="test",
        )

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 500,
    ):
        yield await self.complete(messages, max_tokens)


@pytest.fixture
def server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


def redis(server: fakeredis.FakeServer) -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(server=server)


async def test_riscrittura_condivisa_e_fallback_redis(server: fakeredis.FakeServer) -> None:
    modello = Modello("operazioni verso il Venezuela")
    primo = await QueryRewriter(modello, "P", cache=redis(server)).riscrivi_per_ricerca("ven ok?")
    secondo = await QueryRewriter(modello, "P", cache=redis(server)).riscrivi_per_ricerca("ven ok?")

    assert primo.da_cache is False
    assert primo.cost_eur == Decimal("0.0001")
    assert secondo.da_cache is True
    assert secondo.cost_eur == Decimal("0")
    assert modello.calls == 1

    server.connected = False
    caduto = QueryRewriter(Modello("ritenta"), "P", cache=redis(server))
    assert await caduto.rewrite_cached("ven ok?") == "ritenta"


async def test_prompt_nuovo_non_usa_cache_vecchia(server: fakeredis.FakeServer) -> None:
    await QueryRewriter(Modello("vecchia"), "P1", cache=redis(server)).rewrite_cached("x?")
    nuova = await QueryRewriter(Modello("nuova"), "P2", cache=redis(server)).rewrite_cached("x?")
    assert nuova == "nuova"
    chiavi = await redis(server).keys("rewrite:*")
    assert len(chiavi) == 2


def test_tetti_rispettano_uno_solo_senza_peggiorare_l_altro() -> None:
    partenza = {"p95_s": 4.0, "costo_medio_eur": 0.0010}
    assert misura_tetti.verdetto(partenza, {"p95_s": 2.9, "costo_medio_eur": 0.0010})[0]
    assert misura_tetti.verdetto(partenza, {"p95_s": 4.0, "costo_medio_eur": 0.0007})[0]
    assert not misura_tetti.verdetto(partenza, {"p95_s": 2.9, "costo_medio_eur": 0.0011})[0]
    assert misura_tetti.p95([1.0] * 19 + [10.0]) < 10.0


def test_segnaposto_jwt_rifiutato() -> None:
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql+asyncpg://lipari:lipari@localhost/lipari",
            jwt_secret="cambiami-con-python-secrets-token-urlsafe-48",
        )
