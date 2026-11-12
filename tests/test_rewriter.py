import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.auth.acl import visible_to
from src.auth.deps import UserContext
from src.exceptions import LLMProviderError
from src.llm.client import LLMProvider
from src.llm.embedding_client import EmbeddingClient
from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message, ToolSpec
from src.services.rag_service import RAGService
from src.services.retrieval_service import RetrievalResult, RetrievalService
from src.types.advice import IngestRequest


class ModelloCheRiscrive:
    def __init__(self, outputs: list[str | Exception]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def complete(
        self, messages: list[Message], max_tokens: int = 500, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        self.calls += 1
        output = self.outputs[min(self.calls - 1, len(self.outputs) - 1)]
        if isinstance(output, Exception):
            raise output
        return LLMResponse(
            content=output,
            tokens_used=1,
            cost_eur=Decimal("0"),
            model="test",
        )

    async def stream(
        self, messages: list[Message], max_tokens: int = 500
    ) -> AsyncIterator[str | LLMResponse]:
        yield await self.complete(messages, max_tokens)


class EmbedderDiTest(EmbeddingClient):
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def embed_one(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.0]


class RetrievalDiTest(RetrievalService):
    def __init__(self) -> None:
        self.roles: list[str] = []

    async def search_for_user(
        self, query_vec: list[float], role: str, top_k: int = 5, soglia: float = 0.35
    ) -> list[RetrievalResult]:
        self.roles.append(role)
        return [
            RetrievalResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="Evidenza disponibile.",
                similarity=0.9,
            )
        ]


class ModelloDiRisposta(LLMProvider):
    def __init__(self) -> None:
        self.messages: list[Message] = []

    async def complete(
        self, messages: list[Message], max_tokens: int = 500, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        self.messages = messages
        return LLMResponse(
            content="Risposta [fonte-1].",
            tokens_used=2,
            cost_eur=Decimal("0"),
            model="test",
        )

    async def stream(
        self, messages: list[Message], max_tokens: int = 500
    ) -> AsyncIterator[str | LLMResponse]:
        yield await self.complete(messages, max_tokens)


class ModelloLento(LLMProvider):
    async def complete(
        self, messages: list[Message], max_tokens: int = 500, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        await asyncio.sleep(10)
        return LLMResponse(content="", tokens_used=0, cost_eur=Decimal("0"), model="test")

    async def stream(
        self, messages: list[Message], max_tokens: int = 500
    ) -> AsyncIterator[str | LLMResponse]:
        yield await self.complete(messages, max_tokens)


class ModelloLentoAlPrimoGiro(ModelloDiRisposta):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def complete(
        self, messages: list[Message], max_tokens: int = 500, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            await asyncio.sleep(10)
        return await super().complete(messages, max_tokens, tools)


class EmbedderLento(EmbedderDiTest):
    async def embed_one(self, text: str) -> list[float]:
        await asyncio.sleep(10)
        return [0.0]


class RetrievalLento(RetrievalDiTest):
    async def search_for_user(
        self, query_vec: list[float], role: str, top_k: int = 5, soglia: float = 0.35
    ) -> list[RetrievalResult]:
        await asyncio.sleep(10)
        return []


class RetrievalConDueRisultati(RetrievalDiTest):
    async def search_for_user(
        self, query_vec: list[float], role: str, top_k: int = 5, soglia: float = 0.35
    ) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                chunk_id=f"chunk-{index}",
                document_id=f"doc-{index}",
                content=f"Evidenza {index}.",
                similarity=0.9 - index / 10,
            )
            for index in range(2)
        ]


async def test_cached_rewrite_retries_fallback_and_caches_success() -> None:
    llm = ModelloCheRiscrive(
        [LLMProviderError("test", "temporarily unavailable"), "query estesa", "ignored"]
    )
    rewriter = QueryRewriter(llm, "prompt")

    assert await rewriter.rewrite_cached("ven ok?") == "ven ok?"
    assert await rewriter.rewrite_cached("ven ok?") == "query estesa"
    assert await rewriter.rewrite_cached("ven ok?") == "query estesa"
    assert llm.calls == 2


async def test_disabled_or_unreasonably_long_rewrite_uses_original() -> None:
    llm = ModelloCheRiscrive(["x" * 500])

    assert await QueryRewriter(llm, "prompt").rewrite("ven ok?") == "ven ok?"
    assert await QueryRewriter(llm, "prompt", enabled=False).rewrite("ven ok?") == "ven ok?"


async def test_rag_cerca_con_la_riscrittura_ma_risponde_alla_domanda_originale() -> None:
    embedder = EmbedderDiTest()
    retrieval = RetrievalDiTest()
    response_model = ModelloDiRisposta()
    service = RAGService(
        retrieval,
        embedder,
        response_model,
        QueryRewriter(ModelloCheRiscrive(["query riscritta"]), "prompt"),
        "system prompt",
    )

    result = await service.advise(
        "domanda originale",
        UserContext(username="user", role="compliance_lead"),
    )

    assert embedder.queries == ["query riscritta"]
    assert retrieval.roles == ["compliance_lead"]
    assert response_model.messages[-1].content.endswith("DOMANDA\ndomanda originale")
    assert "query riscritta" not in response_model.messages[-1].content
    assert result.rewritten_query == "query riscritta"


async def test_timeout_riscrittura_avverte_e_usa_la_domanda_originale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RAGService, "TIMEOUT_FASE_S", 0.01)
    embedder = EmbedderDiTest()
    service = RAGService(
        RetrievalDiTest(),
        embedder,
        ModelloDiRisposta(),
        QueryRewriter(ModelloLento(), "prompt"),
        "system prompt",
    )

    result = await service.advise(
        "domanda originale",
        UserContext(username="user", role="compliance_lead"),
    )

    assert result.rewritten_query == "domanda originale"
    assert embedder.queries == ["domanda originale"]
    assert "riscrittura" in result.answer.lower()


async def test_timeout_embedding_avverte_e_interrompe_il_recupero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RAGService, "TIMEOUT_FASE_S", 0.01)
    retrieval = RetrievalDiTest()
    service = RAGService(
        retrieval,
        EmbedderLento(),
        ModelloDiRisposta(),
        QueryRewriter(ModelloCheRiscrive(["query riscritta"]), "prompt"),
        "system prompt",
    )

    result = await service.advise(
        "domanda originale",
        UserContext(username="user", role="compliance_lead"),
    )

    assert "embedding" in result.answer.lower()
    assert retrieval.roles == []


async def test_timeout_recupero_avverte_e_non_inventa_fonti(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RAGService, "TIMEOUT_FASE_S", 0.01)
    service = RAGService(
        RetrievalLento(),
        EmbedderDiTest(),
        ModelloDiRisposta(),
        QueryRewriter(ModelloCheRiscrive(["query riscritta"]), "prompt"),
        "system prompt",
    )

    result = await service.advise(
        "domanda originale",
        UserContext(username="user", role="compliance_lead"),
    )

    assert "ricerca nei documenti" in result.answer.lower()
    assert result.citations == []
    assert result.retrieved_chunks == 0


async def test_timeout_reranking_avverte_e_prosegue_senza_riordino(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RAGService, "TIMEOUT_FASE_S", 0.01)
    service = RAGService(
        RetrievalConDueRisultati(),
        EmbedderDiTest(),
        ModelloLentoAlPrimoGiro(),
        QueryRewriter(ModelloCheRiscrive(["query riscritta"]), "prompt"),
        "system prompt",
    )

    result = await service.advise(
        "domanda originale",
        UserContext(username="user", role="compliance_lead"),
    )

    assert "riordino dei documenti" in result.answer.lower()
    assert "Risposta [fonte-1]." in result.answer
    assert result.retrieved_chunks == 2


async def test_timeout_generazione_avverte_e_restituisce_i_passaggi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RAGService, "TIMEOUT_FASE_S", 0.01)
    service = RAGService(
        RetrievalDiTest(),
        EmbedderDiTest(),
        ModelloLento(),
        QueryRewriter(ModelloCheRiscrive(["query riscritta"]), "prompt"),
        "system prompt",
    )

    result = await service.advise(
        "domanda originale",
        UserContext(username="user", role="compliance_lead"),
    )

    assert "generazione non completata" in result.answer.lower()
    assert "Evidenza disponibile." in result.answer
    assert result.citations[0].document_id == "doc-1"


def test_role_visibility_is_allowlisted_and_unknown_roles_are_public_only() -> None:
    assert visible_to("operator") == ["public", "internal"]
    assert visible_to("compliance_lead") == ["public", "internal", "compliance_only"]
    assert visible_to("risk_lead") == ["public", "internal", "risk_only"]
    assert visible_to("unrecognized") == ["public"]


def test_ingestion_rejects_visibility_outside_the_allowlist() -> None:
    with pytest.raises(ValidationError):
        IngestRequest(
            document_id="doc",
            content="contenuto sufficientemente lungo",
            visibility="compliance-only",
        )
