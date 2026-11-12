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

## Autenticazione e documenti riservati

Le API di chat, conti e advisor richiedono un bearer token ottenuto da
`POST /api/auth/login`; l'ingestione è riservata ai ruoli `compliance_lead` e `admin`.
Prima di usare questi endpoint, applica le migration e crea gli utenti di sviluppo:

```powershell
uv run alembic upgrade head
uv run python -m scripts.seed_users
```

I documenti possono avere visibilità `public`, `internal`, `risk_only` o
`compliance_only`. Il livello viene assegnato durante l'ingestione e il filtro per ruolo
viene applicato direttamente nella query di recupero.

## Ricerca documentale

L'endpoint `POST /api/ai/advice` recupera fino a 20 passaggi, li riordina con il modello
configurato e usa al massimo i primi 5 per generare la risposta. La risposta include
`rewritten_query`, `retrieved_chunks`, `rerank_tokens_used`, `rerank_cost_eur` e `rerank_latency_ms`;
`tokens_used` e `cost_eur` comprendono sia il riordino sia la generazione. Se c'è un solo
passaggio, il riordino viene saltato.

Per misurare il miglioramento del recupero serve confrontare top-5 e top-20 riordinato su
domande con passaggi rilevanti etichettati: i test sintetici verificano il flusso e il calcolo
del costo, non stimano la qualità sul corpus reale.

## Tool dell'agente

L'agente di filiale espone sette tool: ricerca dei conti di un cliente, saldo, movimenti recenti,
ricerca nei documenti, apertura di una segnalazione Compliance, disponibilità della carta e stato
del bonifico. Le descrizioni distinguono i casi d'uso per aiutare il modello a scegliere:
`check_card_availability` verifica la carta registrata e il plafond, non il residuo spendibile;
`get_transfer_status` trova solo bonifici già contabilizzati nei movimenti, non quelli in attesa.
Più tool non garantiscono una scelta migliore: le descrizioni delimitano esplicitamente cosa
ciascun tool può verificare.

## Modello dati

I beneficiari appartengono a un cliente; i mandati collegano un conto al beneficiario;
le carte appartengono a un conto e registrano il plafond.

- Un mandato è un'autorizzazione di pagamento e deve restare associato al beneficiario con cui è stato conferito.
- La cascata cancellerebbe la traccia del mandato; `SET NULL` lo lascerebbe senza controparte.
- `ON DELETE RESTRICT` rifiuta quindi la cancellazione del beneficiario finché esistono mandati collegati.
