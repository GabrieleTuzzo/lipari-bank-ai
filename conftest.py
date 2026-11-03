# conftest.py — nella radice: l'ambiente dei test, prima che qualcosa importi src
import os
from collections.abc import Iterator

import pytest
from alembic.config import Config

from alembic import command

# Dal Giorno 3 i test parlano con un database vero: quello di test, mai quello di sviluppo.
# Qui non c'è setdefault: un DATABASE_URL rimasto nell'ambiente porterebbe i test a svuotare
# il database su cui lavori.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://lipari:lipari@localhost:5432/lipari_ai_test"
)
os.environ.setdefault("JWT_SECRET", "segreto-dei-test-lungo-almeno-trentadue-caratteri")


@pytest.fixture(scope="session", autouse=True)
def schema() -> Iterator[None]:
    """Lo schema del database di test, dalle migration e da zero: come lo avrà chi clona."""
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
