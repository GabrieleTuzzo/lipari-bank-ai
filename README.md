# LipariBank AI

## Avvio locale

Installa le dipendenze definite nel progetto:

```powershell
uv sync
```

Il file `.env` deve contenere almeno `DATABASE_URL` e un `JWT_SECRET` di almeno
32 caratteri. Per generare un segreto, esegui:

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia il valore stampato in `JWT_SECRET` nel file `.env`, poi avvia l'app:

```powershell
uv run uvicorn src.main:app --reload
```

Per eseguire i test:

```powershell
uv run pytest
```

## Ricerca documentale

L'endpoint `POST /api/ai/advice` recupera fino a 20 passaggi, li riordina con il modello
configurato e usa al massimo i primi 5 per generare la risposta. La risposta include
`retrieved_chunks`, `rerank_tokens_used`, `rerank_cost_eur` e `rerank_latency_ms`;
`tokens_used` e `cost_eur` comprendono sia il riordino sia la generazione. Se c'è un solo
passaggio, il riordino viene saltato.

Per misurare il miglioramento del recupero serve confrontare top-5 e top-20 riordinato su
domande con passaggi rilevanti etichettati: i test sintetici verificano il flusso e il calcolo
del costo, non stimano la qualità sul corpus reale.

## Modello dati

I beneficiari appartengono a un cliente; i mandati collegano un conto al beneficiario;
le carte appartengono a un conto e registrano il plafond.

- Un mandato è un'autorizzazione di pagamento e deve restare associato al beneficiario con cui è stato conferito.
- La cascata cancellerebbe la traccia del mandato; `SET NULL` lo lascerebbe senza controparte.
- `ON DELETE RESTRICT` rifiuta quindi la cancellazione del beneficiario finché esistono mandati collegati.
