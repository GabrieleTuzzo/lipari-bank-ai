# conftest.py — nella radice: i valori minimi per importare l'applicazione nei test
import os
from collections.abc import Iterator

import pytest

# prima di qualunque import di src: la configurazione si valida all'import, e senza questi due
# valori i test non partirebbero nemmeno. setdefault: se l'ambiente ne ha già uno, vince quello
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "segreto-dei-test-lungo-almeno-trentadue-caratteri")

# conftest.py — nella radice: la fixture dei modelli finti, con l'embedder
@pytest.fixture(scope="session", autouse=True)
def modelli_finti() -> Iterator[None]:
    """Dal Giorno 4 nessun test chiama un modello vero: costerebbe, e risponderebbe ogni volta
    in un modo diverso. La chat parla con un finto che ripete la domanda, la categorizzazione
    usa la regola del Giorno 2, gli embedding sono finti ma coerenti (dal Giorno 5). Un test che
    vuole un modello preciso mette il suo."""
    from src.api.categorize import get_categorize_service
    from src.llm.factory import get_embedder, get_llm_provider
    from src.main import app
    from tests.finti import CategorizzazioneARegole, ModelloEco, embedder_finto

    app.dependency_overrides[get_llm_provider] = ModelloEco
    app.dependency_overrides[get_categorize_service] = CategorizzazioneARegole
    app.dependency_overrides[get_embedder] = embedder_finto
    yield
    app.dependency_overrides.clear()
