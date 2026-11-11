import json
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest

from src.auth.deps import UserContext
from src.llm.embedding_client import EmbeddingClient
from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message, ToolSpec
from src.services.rag_service import RAGService
from src.services.reranking_service import RerankingError, RerankingService
from src.services.retrieval_service import RetrievalResult, RetrievalService


class ModelloDiTest:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.requests: list[list[Message]] = []

    async def complete(
        self, messages: list[Message], max_tokens: int = 500, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        self.requests.append(messages)
        ranker = len(self.requests) == 1
        return LLMResponse(
            content=next(self.responses),
            tokens_used=40 if ranker else 80,
            cost_eur=Decimal("0.0002") if ranker else Decimal("0.001"),
            model="test",
        )

    async def stream(
        self, messages: list[Message], max_tokens: int = 500
    ) -> AsyncIterator[str | LLMResponse]:
        yield await self.complete(messages, max_tokens)


class EmbedderDiTest(EmbeddingClient):
    def __init__(self) -> None:
        pass

    async def embed_one(self, text: str) -> list[float]:
        return [0.0]


class RecuperoDiTest(RetrievalService):
    def __init__(self, passages: list[RetrievalResult]) -> None:
        self.passages = passages
        self.top_k: int | None = None

    async def search_for_user(
        self, query_vec: list[float], role: str, top_k: int = 5
    ) -> list[RetrievalResult]:
        self.top_k = top_k
        return self.passages[:top_k]


def passaggi_test() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id=str(index),
            document_id="benchmark",
            content=f"Contenuto del passaggio {index}",
            similarity=1.0 - index / 100,
        )
        for index in range(20)
    ]


async def test_rag_reranks_20_candidates_and_reports_per_question_cost() -> None:
    passages = passaggi_test()
    relevant = {str(index) for index in range(15, 20)}
    ranked_ids = [str(index) for index in range(19, -1, -1)]
    llm = ModelloDiTest([json.dumps(ranked_ids), "Risposta [fonte-1]."])
    retrieval = RecuperoDiTest(passages)
    service = RAGService(
        retrieval,
        EmbedderDiTest(),
        llm,
        QueryRewriter(llm, "", enabled=False),
        "Prompt",
    )

    response = await service.advise(
        "Qual è la risposta corretta?",
        UserContext(username="test", role="operator"),
    )

    baseline_recall = len({p.chunk_id for p in passages[:5]} & relevant) / len(relevant)
    reranked_recall = len(set(ranked_ids[:5]) & relevant) / len(relevant)
    assert retrieval.top_k == 20
    assert baseline_recall == 0.0 and reranked_recall == 1.0
    assert response.retrieved_chunks == 20
    assert response.tokens_used == 120
    assert response.cost_eur == pytest.approx(0.0012)
    assert response.rerank_tokens_used == 40
    assert response.rerank_cost_eur == pytest.approx(0.0002)
    assert response.rerank_latency_ms >= 0
    assert response.citations[0].chunk_id == "19"
    assert len(llm.requests) == 2


async def test_reranker_rifiuta_una_risposta_non_valida() -> None:
    service = RerankingService(ModelloDiTest(["not json"]))

    with pytest.raises(RerankingError):
        await service.rerank("domanda", passaggi_test())


async def test_reranker_salta_la_chiamata_se_c_e_un_solo_passaggio() -> None:
    llm = ModelloDiTest([])
    passages = passaggi_test()[:1]

    result = await RerankingService(llm).rerank("domanda", passages)

    assert result.passages == passages
    assert result.tokens_used == 0 and result.cost_eur == 0 and result.latency_ms == 0
    assert llm.requests == []
