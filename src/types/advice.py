# src/types/advice.py — il contratto dell'advisor e dell'ingestione
from typing import Literal

from pydantic import BaseModel, Field


# src/types/advice.py — estratto: il livello, fra quelli che esistono
class IngestRequest(BaseModel):
    document_id: str = Field(..., max_length=100)
    content: str = Field(..., min_length=10)
    metadata: dict[str, str] | None = None
    visibility: Literal["public", "internal", "risk_only", "compliance_only"] = "public"


class IngestResponse(BaseModel):
    chunk_count: int
    embedding_dim: int


class AdviceRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    excerpt: str
    similarity: float


class AdviceResponse(BaseModel):
    answer: str
    citations: list[Citation]
    rewritten_query: str
    tokens_used: int
    cost_eur: float
    rerank_tokens_used: int = 0
    rerank_cost_eur: float = 0.0
    rerank_latency_ms: float = 0.0
    retrieved_chunks: int = 0
