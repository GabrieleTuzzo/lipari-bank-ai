"""Valutazione manuale dell'advisor e controllo del self-bias.

Il file JSON dei casi deve contenere una lista con almeno 20 elementi.
Ogni elemento richiede: domanda, risposta, passaggi, giudizio_umano.

Esempio:
    uv run python -m scripts.eval_giudice --casi eval/giudizi_20.json
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from src.config import settings
from src.evaluation.judge import (
    CasoGiudicato,
    ValutazioneGiudice,
    confronta_con_giudizio_umano,
    eval_giudice,
)
from src.llm.factory import get_llm_provider

__all__ = ["eval_giudice", "carica_casi", "main"]


def carica_casi(percorso: str) -> list[CasoGiudicato]:
    dati: Any = json.loads(Path(percorso).read_text(encoding="utf-8"))
    if not isinstance(dati, list):
        raise ValueError("Il file dei casi deve essere una lista JSON")
    return [
        CasoGiudicato(
            domanda=item["domanda"],
            risposta=item["risposta"],
            passaggi=item.get("passaggi", ""),
            giudizio_umano=ValutazioneGiudice.model_validate(item["giudizio_umano"]),
        )
        for item in dati
    ]


async def main(
    percorso: str,
    modello_giudice: str | None = None,
    modello_generatore: str | None = None,
) -> None:
    casi = carica_casi(percorso)
    giudice = get_llm_provider()
    giudice_effettivo = modello_giudice or getattr(giudice, "_model", settings.default_model)
    generatore_effettivo = modello_generatore or settings.default_model
    confronto = await confronta_con_giudizio_umano(
        giudice,
        casi,
        modello_generatore=str(generatore_effettivo),
        modello_giudice=str(giudice_effettivo),
    )
    print(confronto.model_dump_json(indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--casi", required=True, help="JSON con almeno 20 casi manuali")
    parser.add_argument("--modello-giudice", default=None)
    parser.add_argument("--modello-generatore", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.casi, args.modello_giudice, args.modello_generatore))
