import hashlib
import json
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.llm.embedding_client import EmbeddingClient

log = logging.getLogger(__name__)


class CachedEmbedder(EmbeddingClient):
    TTL_S = 7 * 24 * 3600

    def __init__(self, inner: EmbeddingClient, cache: Redis) -> None:
        super().__init__(inner.client, inner.model)
        self._cache = cache
        self.hit = 0
        self.miss = 0

    def chiave(self, text: str) -> str:
        digest = hashlib.sha256(text.encode()).hexdigest()
        return f"emb:{self.model}:{digest}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        chiavi = [self.chiave(text) for text in texts]
        try:
            letti = await self._cache.mget(chiavi)
        except RedisError:
            log.warning("cache.non_disponibile", extra={"cache": "embedding"})
            self.miss += len(texts)
            return await super().embed(texts)

        vettori: list[list[float] | None] = [
            None if letto is None else json.loads(letto) for letto in letti
        ]
        mancanti = [i for i, vettore in enumerate(vettori) if vettore is None]
        if mancanti:
            nuovi = await super().embed([texts[i] for i in mancanti])
            pipe = self._cache.pipeline(transaction=False)
            for i, vettore in zip(mancanti, nuovi, strict=True):
                vettori[i] = vettore
                pipe.set(chiavi[i], json.dumps(vettore), ex=self.TTL_S)
            try:
                await pipe.execute()
            except RedisError:
                log.warning("cache.non_disponibile", extra={"cache": "embedding"})
        self.hit += len(texts) - len(mancanti)
        self.miss += len(mancanti)
        return [vettore for vettore in vettori if vettore is not None]
