# src/agents/deps.py — i servizi che i tool usano, costruiti per ogni richiesta
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.repos import AccountRepository, MovementRepository
from src.db.session import get_db
from src.llm.embedding_client import EmbeddingClient
from src.llm.factory import get_embedder, get_openai
from src.services.alerts import AlertService
from src.services.retrieval_service import RetrievalService


@dataclass(frozen=True)
class Deps:
    accounts: AccountRepository
    movements: MovementRepository
    alerts: AlertService
    retrieval: RetrievalService
    embedder: EmbeddingClient
    openai: AsyncOpenAI          # l'SDK, direttamente: il ciclo è scritto a mano, campo per campo
    model: str


async def get_deps(db: Annotated[AsyncSession, Depends(get_db)]) -> Deps:
    return Deps(
        accounts=AccountRepository(db),
        movements=MovementRepository(db),
        alerts=AlertService(db),
        retrieval=RetrievalService(db),
        embedder=get_embedder(),  # dalla factory del Giorno 4: un client per processo,
        openai=get_openai(),      # e senza chiave un 503 che dice quale manca
        model=settings.default_model,
    )
