# src/services/rag_service.py — recupera, genera, e cita solo ciò che la risposta usa
import re

from src.llm.client import LLMProvider
from src.llm.embedding_client import EmbeddingClient
from src.llm.types import Message
from src.services.reranking_service import RerankingService
from src.services.retrieval_service import RetrievalResult, RetrievalService
from src.types.advice import AdviceRequest, AdviceResponse, Citation

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
            continue  # un marcatore inventato non diventa una fonte
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
    """Recupera e riordina i passaggi, genera la risposta, e cita le fonti usate."""

    def __init__(
        self,
        retrieval: RetrievalService,
        embedder: EmbeddingClient,
        llm: LLMProvider,
        prompt: str,
    ) -> None:
        self.retrieval = retrieval
        self.embedder = embedder
        self.llm = llm
        self.prompt = prompt
        self.reranking = RerankingService(llm)

    async def advise(self, req: AdviceRequest) -> AdviceResponse:
        """Recupera, riordina e genera la risposta con le fonti che usa.

        Se il recupero non porta niente sopra la soglia, ritorna il rifiuto e nessuna
        citazione, senza chiamare il modello.
        """
        vettore = await self.embedder.embed_one(req.question)
        candidati = await self.retrieval.search(vettore, top_k=20)
        if not candidati:
            return AdviceResponse(answer=RIFIUTO, citations=[], tokens_used=0, cost_eur=0.0)

        riordino = await self.reranking.rerank(req.question, candidati, top_k=5)
        passaggi = riordino.passages

        risposta = await self.llm.complete(
            [
                Message(role="system", content=self.prompt),
                Message(
                    role="user",
                    content=f"CONTESTO\n{contesto(passaggi)}\n\nDOMANDA\n{req.question}",
                ),
            ]
        )
        rifiuto = RIFIUTO in risposta.content  # il modello ha detto che non c'è: niente fonti
        return AdviceResponse(
            answer=risposta.content,
            citations=[] if rifiuto else citazioni(risposta.content, passaggi),
            tokens_used=risposta.tokens_used + riordino.tokens_used,
            cost_eur=float(risposta.cost_eur) + riordino.cost_eur,
            rerank_tokens_used=riordino.tokens_used,
            rerank_cost_eur=riordino.cost_eur,
            rerank_latency_ms=riordino.latency_ms,
            retrieved_chunks=len(candidati),
        )
