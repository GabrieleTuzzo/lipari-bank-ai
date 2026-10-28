# src/main.py — l'applicazione, e la sonda che dice se è viva e se è configurata
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from src.config import settings


class Credentials(BaseModel):
    """Quali chiavi ci sono. Un sì o un no: mai il valore, e mai un pezzo del valore."""

    openai: bool
    anthropic: bool


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    app_name: str
    version: str
    environment: str
    credentials: Credentials


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="LipariBank AI Assistant — Bootcamp Python AI Powered, Lipari Consulting",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="UP",
        timestamp=datetime.now(UTC).isoformat(),
        app_name=settings.app_name,
        version="1.0.0",
        environment=settings.environment,
        credentials=Credentials(
            openai=bool(settings.openai_api_key),
            anthropic=bool(settings.anthropic_api_key),
        ),
    )
