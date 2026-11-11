import hashlib
import json
import math
import re
from collections.abc import AsyncIterator, Callable
from decimal import Decimal

import httpx
from openai import AsyncOpenAI

from src.auth.deps import UserContext
from src.llm.embedding_client import EmbeddingClient
from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message, ToolSpec
from src.types.categorize import CategorizeRequest, CategorizeResponse


def openai_finto(
    handler: Callable[[httpx.Request], httpx.Response], max_retries: int = 1
) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=max_retries,
    )

# tests/finti.py — in fondo: gli embedding finti, e un modello che risponde come gli si dice
def vettore(testo: str) -> list[float]:
    """Un embedding finto ma coerente: le parole in comune avvicinano i testi."""
    v = [0.0] * 1536
    for parola in re.findall(r"\w{3,}", testo.lower()):
        v[int(hashlib.md5(parola.encode()).hexdigest(), 16) % 1536] += 1.0
    norma = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norma for x in v]


def gestore_embedding(r: httpx.Request) -> httpx.Response:
    """L'API degli embedding, finta: un vettore per ogni testo, nell'ordine in cui arrivano."""
    testi: list[str] = json.loads(r.content)["input"]
    return httpx.Response(
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


class ModelloEco:
    async def complete(
        self, messages: list[Message], max_tokens: int = 500, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        content = f"Echo: {messages[-1].content}"
        return LLMResponse(
            content=content, tokens_used=2, cost_eur=Decimal("0"), model="finto"
        )

    async def stream(
        self, messages: list[Message], max_tokens: int = 500
    ) -> AsyncIterator[str | LLMResponse]:
        response = await self.complete(messages, max_tokens)
        yield response.content
        yield response


class CategorizzazioneARegole:
    async def categorize(self, req: CategorizeRequest) -> CategorizeResponse:
        description = req.description.casefold()
        has_utility = bool(re.search(r"\b(enel|energia)\b", description))
        has_entertainment = bool(re.search(r"\b(netflix|spotify)\b", description))
        if has_utility and has_entertainment:
            return CategorizeResponse(
                category="UTILITIES",
                subcategory="ENERGY",
                confidence=0.5,
                reasoning="Il movimento combina più categorie, inclusa un'altra categoria.",
            )
        if has_utility:
            return CategorizeResponse(
                category="UTILITIES",
                subcategory="ENERGY",
                confidence=0.8,
                reasoning="Pagamento di una bolletta energetica.",
            )
        return CategorizeResponse(
            category="OTHER",
            subcategory="GENERAL",
            confidence=0.5,
            reasoning="Non è possibile ricondurre il movimento a una categoria specifica.",
        )


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


MARCO = UserContext(username="mbianchi", role="operator")
GIULIA = UserContext(username="grossi", role="compliance_lead")


def riscrittore_spento() -> QueryRewriter:
    return QueryRewriter(ModelloEco(), "", enabled=False)
