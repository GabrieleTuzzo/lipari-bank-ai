import openai
from openai import AsyncOpenAI

from src.exceptions import LLMProviderError


class EmbeddingClient:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = await self.client.embeddings.create(model=self.model, input=texts)
        except openai.APIError as exc:
            raise LLMProviderError("openai", str(exc)) from exc
        return [
            list(item.embedding)
            for item in sorted(response.data, key=lambda embedding: embedding.index)
        ]

    async def embed_one(self, text: str) -> list[float]:
        embeddings = await self.embed([text])
        return embeddings[0]
