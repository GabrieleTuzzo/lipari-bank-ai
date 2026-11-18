import hashlib
import logging
from dataclasses import dataclass
from decimal import Decimal

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.llm.client import LLMProvider
from src.llm.types import LLMResponse, Message

log = logging.getLogger(__name__)
TTL_S = 3600


@dataclass
class Riscrittura:
    testo: str
    da_cache: bool = False
    tokens: int = 0
    cost_eur: Decimal = Decimal("0")


class QueryRewriter:
    def __init__(
        self,
        llm: LLMProvider,
        prompt: str,
        enabled: bool = True,
        cache: Redis | None = None,
    ) -> None:
        self.llm = llm
        self.prompt = prompt
        self.enabled = enabled
        self._redis = cache
        self._locale: dict[str, str] = {}
        self._versione = hashlib.sha256(prompt.encode()).hexdigest()[:8]

    async def _riscrivi(
        self,
        question: str,
        history: list[str] | None,
    ) -> tuple[str | None, LLMResponse | None]:
        coda = "\n".join(history[-3:]) if history else ""
        try:
            risposta = await self.llm.complete(
                [
                    Message(role="system", content=self.prompt),
                    Message(role="user", content=f"{coda}\n\nDomanda: {question}".strip()),
                ],
                max_tokens=80,
            )
        except Exception:
            log.warning("rewriter.fallito", extra={"domanda": question})
            return None, None

        riscritta = risposta.content.strip().strip('"')
        if not riscritta or len(riscritta) > 4 * len(question) + 80:
            log.warning("rewriter.scartata", extra={"uscita": riscritta[:120]})
            return None, risposta
        return riscritta, risposta

    async def rewrite(self, question: str, history: list[str] | None = None) -> str:
        if not self.enabled:
            return question
        riscritta, _ = await self._riscrivi(question, history)
        return riscritta or question

    def chiave(self, question: str) -> str:
        return f"rewrite:{self._versione}:{hashlib.sha256(question.encode()).hexdigest()}"

    async def _leggi(self, chiave: str) -> str | None:
        if self._redis is None:
            return self._locale.get(chiave)
        try:
            valore = await self._redis.get(chiave)
        except RedisError:
            log.warning("cache.non_disponibile", extra={"cache": "rewrite"})
            return None
        return valore.decode() if isinstance(valore, bytes) else valore

    async def _scrivi(self, chiave: str, valore: str) -> None:
        if self._redis is None:
            self._locale[chiave] = valore
            return
        try:
            await self._redis.set(chiave, valore, ex=TTL_S)
        except RedisError:
            log.warning("cache.non_disponibile", extra={"cache": "rewrite"})

    async def riscrivi_per_ricerca(self, question: str) -> Riscrittura:
        if not self.enabled:
            return Riscrittura(question)
        chiave = self.chiave(question)
        if (cached := await self._leggi(chiave)) is not None:
            return Riscrittura(cached, da_cache=True)
        riscritta, risposta = await self._riscrivi(question, None)
        pagata = Riscrittura(
            riscritta or question,
            tokens=risposta.tokens_used if risposta else 0,
            cost_eur=risposta.cost_eur if risposta else Decimal("0"),
        )
        if riscritta is not None:
            await self._scrivi(chiave, riscritta)
        return pagata

    async def rewrite_cached(self, question: str) -> str:
        return (await self.riscrivi_per_ricerca(question)).testo
