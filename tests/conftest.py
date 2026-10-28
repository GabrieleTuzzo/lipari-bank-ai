# conftest.py — nella radice: i valori minimi per importare l'applicazione nei test
import os

# prima di qualunque import di src: la configurazione si valida all'import, e senza questi due
# valori i test non partirebbero nemmeno. setdefault: se l'ambiente ne ha già uno, vince quello
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "segreto-dei-test-lungo-almeno-trentadue-caratteri")
