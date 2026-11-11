import asyncio
import logging
import re
from time import perf_counter

from src.auth.deps import UserContext
from src.exceptions import LLMProviderError
from src.llm.client import LLMProvider
from src.llm.embedding_client import EmbeddingClient
from src.llm.rewriter import QueryRewriter
from src.llm.types import Message
from src.services.reranking_service import RerankingError, RerankingService
from src.services.retrieval_service import RetrievalResult, RetrievalService
from src.types.advice import AdviceResponse, Citation

logger = logging.getLogger(__name__)

RIFIUTO = "Non ho trovato informazioni sufficienti nei documenti disponibili."
MARCATORE = re.compile(r"\[fonte-(\d+)\]")


def contesto(passaggi: list[RetrievalResult]) -> str:
    """I passaggi etichettati: senza etichette, il modello non sa quale citare."""
    return "\n\n".join(
        f"[fonte-{i}] (documento: {p.document_id})\n{p.content}"
        for i, p in enumerate(passaggi, start=1)
    )


def citazioni(risposta: str, passaggi: list[RetrievalResult]) -> list[Citation]:
    """Le fonti che la risposta cita davvero, una volta ciascuna, nell'ordine in cui compaiono."""
    usati: list[Citation] = []
    visti: set[tuple[str, str]] = set()
    for numero in MARCATORE.findall(risposta):
        indice = int(numero) - 1
        if not 0 <= indice < len(passaggi):
            continue
        p = passaggi[indice]
        if (p.document_id, p.content) in visti:
            continue
        visti.add((p.document_id, p.content))
        usati.append(
            Citation(
                document_id=p.document_id,
                chunk_id=p.chunk_id,
                excerpt=p.content[:200],
                similarity=p.similarity,
            )
        )
    return usati


class RAGService:
    """Recupera, riordina e genera risposte limitate ai documenti visibili all'utente."""

    TIMEOUT_GENERAZIONE_S = 20.0

    def __init__(
        self,
        retrieval: RetrievalService,
        embedder: EmbeddingClient,
        llm: LLMProvider,
        rewriter: QueryRewriter,
        prompt: str,
    ) -> None:
        self.retrieval = retrieval
        self.embedder = embedder
        self.llm = llm
        self.rewriter = rewriter
        self.prompt = prompt
        self.reranking = RerankingService(llm)

    async def advise(self, question: str, user: UserContext) -> AdviceResponse:
        """Cerca con la query riscritta, ma genera sempre sulla domanda originale."""
        phases: dict[str, float] = {}
        started = perf_counter()
        rewritten_query = await self.rewriter.rewrite_cached(question)
        phases["rewrite_ms"] = (perf_counter() - started) * 1000

        started = perf_counter()
        vector = await self.embedder.embed_one(rewritten_query)
        phases["embedding_ms"] = (perf_counter() - started) * 1000

        started = perf_counter()
        candidates = await self.retrieval.search_for_user(vector, user.role, top_k=20)
        phases["retrieval_ms"] = (perf_counter() - started) * 1000
        if not candidates:
            logger.info(
                "advice_completata",
                extra={"used_fallback": False, "role": user.role, **phases},
            )
            return AdviceResponse(
                answer=RIFIUTO,
                citations=[],
                rewritten_query=rewritten_query,
                tokens_used=0,
                cost_eur=0.0,
                retrieved_chunks=0,
            )

        used_fallback = False
        started = perf_counter()
        try:
            ranked = await self.reranking.rerank(rewritten_query, candidates, top_k=5)
            passages = ranked.passages
            rerank_tokens = ranked.tokens_used
            rerank_cost = ranked.cost_eur
            rerank_latency = ranked.latency_ms
        except (LLMProviderError, RerankingError, TimeoutError):
            logger.warning("advice_reranking_fallback", extra={"role": user.role})
            passages = candidates[:5]
            rerank_tokens = 0
            rerank_cost = 0.0
            rerank_latency = 0.0
            used_fallback = True
        phases["rerank_ms"] = (perf_counter() - started) * 1000

        started = perf_counter()
        messages = [
            Message(role="system", content=self.prompt),
            Message(
                role="user",
                content=(
                    f"CONTESTO\n{contesto(passages)}\n\nDOMANDA\n{question}"
                ),
            ),
        ]
        phases["prompt_ms"] = (perf_counter() - started) * 1000
        started = perf_counter()
        try:
            response = await asyncio.wait_for(
                self.llm.complete(messages),
                timeout=self.TIMEOUT_GENERAZIONE_S,
            )
        except (LLMProviderError, TimeoutError):
            phases["generation_ms"] = (perf_counter() - started) * 1000
            logger.warning("advice_generation_fallback", extra={"role": user.role})
            used_fallback = True
            answer = (
                "⚠️ Risposta parziale: il modello non è disponibile. "
                "Ecco i passaggi recuperati:\n\n"
                f"{contesto(passages)}"
            )
            citations = citazioni(answer, passages)
            logger.info(
                "advice_completata",
                extra={"used_fallback": True, "role": user.role, **phases},
            )
            return AdviceResponse(
                answer=answer,
                citations=citations,
                rewritten_query=rewritten_query,
                tokens_used=rerank_tokens,
                cost_eur=rerank_cost,
                rerank_tokens_used=rerank_tokens,
                rerank_cost_eur=rerank_cost,
                rerank_latency_ms=rerank_latency,
                retrieved_chunks=len(candidates),
            )

        phases["generation_ms"] = (perf_counter() - started) * 1000
        refused = RIFIUTO in response.content
        logger.info(
            "advice_completata",
            extra={"used_fallback": used_fallback, "role": user.role, **phases},
        )
        return AdviceResponse(
            answer=response.content,
            citations=[] if refused else citazioni(response.content, passages),
            rewritten_query=rewritten_query,
            tokens_used=response.tokens_used + rerank_tokens,
            cost_eur=float(response.cost_eur) + rerank_cost,
            rerank_tokens_used=rerank_tokens,
            rerank_cost_eur=rerank_cost,
            rerank_latency_ms=rerank_latency,
            retrieved_chunks=len(candidates),
        )
