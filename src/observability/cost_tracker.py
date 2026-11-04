# src/observability/cost_tracker.py — il tetto di spesa del giorno, controllato prima di spendere
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from src.db.repos import ChatRepository
from src.exceptions import RateLimitError


class CostTracker:
    def __init__(self, repo: ChatRepository, tetto_eur: Decimal) -> None:
        self.repo = repo
        self.tetto_eur = tetto_eur

    async def speso(self, giorno: date | None = None) -> Decimal:
        # None, e il giorno calcolato qui dentro: un default date.today() nella firma si
        # valuterebbe una volta sola, all'import, e il processo conterebbe per sempre quel giorno
        giorno = giorno or datetime.now(UTC).date()
        inizio = datetime.combine(giorno, time.min, tzinfo=UTC)
        return await self.repo.cost_between(inizio, inizio + timedelta(days=1))

    async def verifica(self) -> None:
        """Da chiamare PRIMA del modello: dopo, la spesa è già fatta."""
        if await self.speso() >= self.tetto_eur:
            adesso = datetime.now(UTC)
            mezzanotte = datetime.combine(adesso.date() + timedelta(days=1), time.min, tzinfo=UTC)
            raise RateLimitError(int((mezzanotte - adesso).total_seconds()) + 1)
