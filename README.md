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

## Modello dati

I beneficiari appartengono a un cliente; i mandati collegano un conto al beneficiario;
le carte appartengono a un conto e registrano il plafond.

- Un mandato è un'autorizzazione di pagamento e deve restare associato al beneficiario con cui è stato conferito.
- La cascata cancellerebbe la traccia del mandato; `SET NULL` lo lascerebbe senza controparte.
- `ON DELETE RESTRICT` rifiuta quindi la cancellazione del beneficiario finché esistono mandati collegati.
