import asyncio
import os

from sqlalchemy import func, select

from evals.ingest_fixtures import main as indicizza
from scripts.seed_accounts import main as seed_accounts
from scripts.seed_users import main as seed_users
from src.config import settings
from src.db.models import DocumentChunk
from src.db.session import AsyncSessionLocal, engine


async def _passaggi_indicizzati() -> int:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(func.count()).select_from(DocumentChunk)) or 0


def chiave_utilizzabile(chiave: str) -> bool:
    return bool(chiave) and "..." not in chiave and not chiave.startswith("sk-...")


async def main() -> None:
    await seed_users()
    await seed_accounts()
    if await _passaggi_indicizzati() and os.environ.get("SEED_REINDEX") != "1":
        print("Indice già popolato: niente da fare (SEED_REINDEX=1 per reindicizzare).")
    elif not chiave_utilizzabile(settings.openai_api_key):
        print(
            "Indice NON costruito: OPENAI_API_KEY è vuota o è il segnaposto di .env.example. "
            "Mettila nel .env e lancia `docker compose run --rm seed`."
        )
    else:
        await indicizza()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
