import json
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest

from src.evaluation.judge import (
    ValutazioneGiudice,
    confronto_quattro_casi,
)
from src.llm.prompt import load_prompt
from src.llm.types import LLMResponse, Message, ToolSpec


class GiudiceFinto:
    def __init__(self, contenuto: str) -> None:
        self.contenuto = contenuto
        self.richieste: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 500,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        self.richieste.append(messages)
        return LLMResponse(
            content=self.contenuto,
            tokens_used=20,
            cost_eur=Decimal("0"),
            model="giudice-test",
        )

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 500,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        yield await self.complete(messages, max_tokens, tools)


@pytest.mark.asyncio
async def test_eval_giudice_separa_i_quattro_criteri() -> None:
    from src.evaluation.judge import eval_giudice

    giudice = GiudiceFinto(
        json.dumps(
            {
                "correttezza": 2,
                "completezza": 1,
                "citazioni": 0,
                "sicurezza": 2,
                "motivazione": "La fonte non sostiene il numero.",
            }
        )
    )

    esito = await eval_giudice(
        giudice,
        "Quanto costa il bonifico?",
        "Costa 1 euro.",
        "[fonte-1] Bonifico: 2 euro.",
    )

    assert esito.per_criterio() == {
        "correttezza": 2,
        "completezza": 1,
        "citazioni": 0,
        "sicurezza": 2,
    }
    assert "PASSAGGI" in giudice.richieste[0][0].content


def test_eval_giudice_prompt_esiste_e_invoca_tutti_i_criteri() -> None:
    prompt = load_prompt("judge_system_v1")
    assert all(nome in prompt for nome in ("correttezza", "completezza", "citazioni", "sicurezza"))


def test_confronto_calcola_disaccordi_e_self_bias() -> None:
    umano = ValutazioneGiudice(correttezza=2, completezza=2, citazioni=1, sicurezza=2)
    modello = ValutazioneGiudice(correttezza=2, completezza=1, citazioni=1, sicurezza=2)

    confronto = confronto_quattro_casi([modello], [umano], self_bias=True)

    assert confronto.numero_casi == 1
    assert confronto.accordo_completo == 0
    assert confronto.accordo_per_criterio["completezza"] == 0
    assert confronto.disaccordi_per_criterio["completezza"] == 1
    assert confronto.self_bias is True


@pytest.mark.asyncio
async def test_confronto_richiede_almeno_venti_casi() -> None:
    from src.evaluation.judge import CasoGiudicato, confronta_con_giudizio_umano

    giudice = GiudiceFinto(
        json.dumps(
            {
                "correttezza": 2,
                "completezza": 2,
                "citazioni": 2,
                "sicurezza": 2,
            }
        )
    )
    voto = ValutazioneGiudice(correttezza=2, completezza=2, citazioni=2, sicurezza=2)
    casi = [
        CasoGiudicato(domanda="Domanda", risposta="Risposta", giudizio_umano=voto)
        for _ in range(19)
    ]

    with pytest.raises(ValueError, match="20"):
        await confronta_con_giudizio_umano(giudice, casi)
