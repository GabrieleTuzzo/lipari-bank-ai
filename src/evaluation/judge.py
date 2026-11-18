import json
import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from src.llm.client import LLMProvider
from src.llm.prompt import load_prompt
from src.llm.types import Message

CRITERI = ("correttezza", "completezza", "citazioni", "sicurezza")


class ValutazioneGiudice(BaseModel):
    """Voto separato per criterio: 0 = insufficiente, 1 = parziale, 2 = pieno."""

    correttezza: int = Field(ge=0, le=2)
    completezza: int = Field(ge=0, le=2)
    citazioni: int = Field(ge=0, le=2)
    sicurezza: int = Field(ge=0, le=2)
    motivazione: str = ""

    def per_criterio(self) -> dict[str, int]:
        return {criterio: getattr(self, criterio) for criterio in CRITERI}


class CasoGiudicato(BaseModel):
    domanda: str
    risposta: str
    passaggi: str = ""
    giudizio_umano: ValutazioneGiudice


class ConfrontoGiudici(BaseModel):
    numero_casi: int
    accordo_completo: float
    accordo_per_criterio: dict[str, float]
    disaccordi_per_criterio: dict[str, int]
    self_bias: bool


def _estrai_json(testo: str) -> dict[str, object]:
    pulito = re.sub(r"^```(?:json)?\s*|\s*```$", "", testo.strip(), flags=re.I)
    try:
        dato = json.loads(pulito)
    except json.JSONDecodeError as exc:
        raise ValueError("Il giudice non ha restituito JSON valido") from exc
    if not isinstance(dato, dict):
        raise ValueError("Il giudice deve restituire un oggetto JSON")
    return dato


async def eval_giudice(
    giudice: LLMProvider,
    domanda: str,
    risposta: str,
    passaggi: str = "",
) -> ValutazioneGiudice:
    """Valuta una risposta dell'advisor usando i quattro criteri separati della rubrica."""

    prompt = load_prompt("judge_system_v1")
    contenuto = (
        f"{prompt}\n\n"
        "Restituisci esclusivamente JSON con queste chiavi:\n"
        "{"
        '"correttezza":0|1|2,'
        '"completezza":0|1|2,'
        '"citazioni":0|1|2,'
        '"sicurezza":0|1|2,'
        '"motivazione":"..."\n'
        "}\n\n"
        f"DOMANDA\n{domanda}\n\nPASSAGGI\n{passaggi or '(nessun passaggio fornito)'}\n\n"
        f"RISPOSTA DA VALUTARE\n{risposta}"
    )
    esito = await giudice.complete([Message(role="user", content=contenuto)])
    return ValutazioneGiudice.model_validate(_estrai_json(esito.content))


def confronto_quattro_casi(
    giudizio_modello: Sequence[ValutazioneGiudice],
    giudizio_umano: Sequence[ValutazioneGiudice],
    *,
    self_bias: bool = False,
) -> ConfrontoGiudici:
    """Confronta i voti modello/uomo caso per caso."""

    if len(giudizio_modello) != len(giudizio_umano):
        raise ValueError(
            "Il giudizio automatico e quello umano devono avere lo stesso numero di casi"
        )
    if len(giudizio_modello) == 0:
        raise ValueError("Sono necessari almeno 20 casi giudicati a mano")

    numero = len(giudizio_modello)
    accordi: dict[str, int] = {criterio: 0 for criterio in CRITERI}
    completo = 0
    for modello, umano in zip(giudizio_modello, giudizio_umano, strict=True):
        modello_voti = modello.per_criterio()
        umano_voti = umano.per_criterio()
        if modello_voti == umano_voti:
            completo += 1
        for criterio in CRITERI:
            if modello_voti[criterio] == umano_voti[criterio]:
                accordi[criterio] += 1

    return ConfrontoGiudici(
        numero_casi=numero,
        accordo_completo=completo / numero,
        accordo_per_criterio={criterio: accordi[criterio] / numero for criterio in CRITERI},
        disaccordi_per_criterio={criterio: numero - accordi[criterio] for criterio in CRITERI},
        self_bias=self_bias,
    )


async def confronta_con_giudizio_umano(
    giudice: LLMProvider,
    casi: Sequence[CasoGiudicato],
    *,
    modello_generatore: str | None = None,
    modello_giudice: str | None = None,
    giustifica_self_bias: bool = False,
) -> ConfrontoGiudici:
    """Evalua fino a venti o più casi manuali e misura la concordanza con il giudice modello."""

    if len(casi) < 20:
        raise ValueError("Il confronto self-bias richiede almeno 20 casi giudicati a mano")

    voti_modello: list[ValutazioneGiudice] = []
    voti_umani: list[ValutazioneGiudice] = []
    for caso in casi:
        voti_modello.append(
            await eval_giudice(
                giudice,
                caso.domanda,
                caso.risposta,
                caso.passaggi,
            )
        )
        voti_umani.append(caso.giudizio_umano)

    same_model = (
        modello_generatore is not None
        and modello_giudice is not None
        and modello_generatore == modello_giudice
    ) or giustifica_self_bias
    return confronto_quattro_casi(voti_modello, voti_umani, self_bias=same_model)
