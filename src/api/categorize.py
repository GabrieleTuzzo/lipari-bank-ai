# src/api/categorize.py — la categorizzazione di un movimento
from fastapi import APIRouter

from src.services.categorize_rules import categorizza
from src.types.categorize import CategorizeRequest, CategorizeResponse

router = APIRouter(prefix="/api/ai", tags=["Categorize"])


@router.post(
    "/categorize",
    response_model=CategorizeResponse,
    summary="Classifica un movimento",
    description="Oggi con regole a parole chiave; dal Giorno 4 con un modello, stesso contratto.",
)
async def categorize(req: CategorizeRequest) -> CategorizeResponse:
    return categorizza(req)
