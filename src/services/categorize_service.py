# src/services/categorize_service.py — lo schema imposto al modello, e validato
import instructor
import openai
from instructor.core import InstructorRetryException

from src.exceptions import LLMProviderError
from src.observability.cost_tracker import CostTracker
from src.types.categorize import CategorizeRequest, CategorizeResponse


class CategorizeService:
    def __init__(
        self,
        client: instructor.AsyncInstructor,
        model: str,
        system_prompt: str,
        costi: CostTracker | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.costi = costi  # il tetto della chat: l'endpoint lo passa sempre

    async def categorize(self, req: CategorizeRequest) -> CategorizeResponse:
        if self.costi is not None:
            await self.costi.verifica()  # prima di spendere: ogni chiamata al modello spende
        try:
            return await self.client.chat.completions.create(
                model=self.model,
                response_model=CategorizeResponse,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": f"Descrizione: {req.description}\n"
                        f"Importo: {req.amount} {req.currency}",
                    },
                ],
                max_retries=2,  # ogni nuovo tentativo è una chiamata pagata
                max_tokens=300,
                temperature=0.0,  # la variabilità più bassa: non vuol dire deterministico
            )
        except InstructorRetryException as e:
            # lo schema non rispettato nemmeno dopo i tentativi, già pagati: è un guasto del
            # fornitore, non un bug nostro, e il client riceve il 502 della chat
            raise LLMProviderError("openai", f"risposta fuori schema: {e}") from e
        except openai.APIError as e:  # fornitore giù, modello sconosciuto, chiave rifiutata
            raise LLMProviderError("openai", str(e)) from e