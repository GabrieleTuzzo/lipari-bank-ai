import asyncio
from pathlib import Path

from src.db.session import AsyncSessionLocal
from src.llm.factory import get_embedder
from src.services.ingest_service import IngestService


async def main() -> None:
    docs_dir = Path("data/docs")
    async with AsyncSessionLocal() as session:
        service = IngestService(session, get_embedder())
        percorsi = await asyncio.to_thread(lambda: sorted(docs_dir.rglob("*.md")))
        for path in percorsi:
            visibility = path.parent.name if path.parent != docs_dir else "public"
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            count = await service.ingest(
                path.stem,
                content,
                {"source": str(path), "title": path.stem.replace("_", " ")},
                visibility,
            )
            print(f"{path.stem} [{visibility}]: {count} passaggi")
