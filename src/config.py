# src/config.py — la configurazione: se manca qualcosa, il progetto non parte e dice cosa
import sys
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """La configurazione del progetto, letta dall'ambiente e dal file `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LipariBank AI"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    # obbligatorie, e non vuote: una riga «DATABASE_URL=» nel .env non basta a far partire.
    # La description è quella che legge chi avvia, quando la variabile manca.
    database_url: str = Field(
        min_length=1,
        description="la stringa di connessione, postgresql+asyncpg://utente:password@host:5432/nome",
    )
    jwt_secret: str = Field(
        min_length=32,  # HS256 vuole una chiave di almeno 256 bit
        description="un segreto di almeno 32 caratteri: "
        'uv run python -c "import secrets; print(secrets.token_urlsafe(48))"',
    )

    # facoltative all'avvio: servono dal Giorno 4, e la sonda dice se ci sono
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    default_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    max_tokens_per_request: int = 2000


def spiega(errore: ValidationError) -> str:
    """Da un errore di validazione al messaggio per chi avvia: quale variabile, cosa ci va, dove."""
    righe = ["Configurazione non valida: il progetto non parte."]
    for e in errore.errors():
        campo = str(e["loc"][0])
        info = Settings.model_fields.get(campo)
        stato = "manca" if e["type"] == "missing" else f"valore non valido ({e['msg']})"
        cosa = f" Ci va {info.description}." if info and info.description else ""
        righe.append(f"  - {campo.upper()}: {stato}.{cosa}")
    righe.append("Si scrive nel file .env (l'elenco completo sta in .env.example) o nell'ambiente.")
    return "\n".join(righe)


def carica() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        # SystemExit con un testo: il messaggio va su stderr e il processo esce con codice 1,
        # senza un traceback che parla d'altro
        sys.exit(spiega(e))


settings = carica()  # qui, in avvio: se manca qualcosa, il processo si ferma e dice cosa
