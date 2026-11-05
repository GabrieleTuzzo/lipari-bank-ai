import hashlib
import json
import re
import math

import httpx2
from src.llm.types import LLMResponse, Message, ToolSpec
from src.llm.embedding_client import EmbeddingClient

# tests/finti.py — in fondo: gli embedding finti, e un modello che risponde come gli si dice
def vettore(testo: str) -> list[float]:
    """Un embedding finto ma coerente: le parole in comune avvicinano i testi."""
    v = [0.0] * 1536
    for parola in re.findall(r"\w{3,}", testo.lower()):
        v[int(hashlib.md5(parola.encode()).hexdigest(), 16) % 1536] += 1.0
    norma = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norma for x in v]


def gestore_embedding(r: httpx2.Request) -> httpx2.Response:
    """L'API degli embedding, finta: un vettore per ogni testo, nell'ordine in cui arrivano."""
    testi: list[str] = json.loads(r.content)["input"]
    return httpx2.Response(
        200,
        json={
            "object": "list",
            "model": "text-embedding-3-small",
            "data": [
                {"object": "embedding", "index": i, "embedding": vettore(t)}
                for i, t in enumerate(testi)
            ],
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        },
    )


def embedder_finto() -> EmbeddingClient:
    return EmbeddingClient(openai_finto(gestore_embedding), "text-embedding-3-small")


class ModelloFisso:
    """Risponde con un testo scelto dal test, e ricorda cosa ha ricevuto."""

    def __init__(self, risposta: str) -> None:
        self.risposta = risposta
        self.ricevuti: list[list[Message]] = []

    async def complete(
        self, messages: list[Message], max_tokens: int = 500, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        self.ricevuti.append(messages)
        return LLMResponse(
            content=self.risposta, tokens_used=100, cost_eur=Decimal("0.0001"), model="finto"
        )

    async def stream(
        self, messages: list[Message], max_tokens: int = 500
    ) -> AsyncIterator[str | LLMResponse]:
        yield await self.complete(messages, max_tokens)