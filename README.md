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
