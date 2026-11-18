import argparse
import asyncio
import json
import os
import random
import shlex
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

DATASET = Path("evals/datasets/advice.jsonl")
PARTENZA = Path("docs/tetti_partenza.json")
UTENTI = {"operator": "mbianchi", "compliance_lead": "grossi", "risk_lead": "lverdi"}
PAUSA_PER_UTENTE_S = 60 / 15 + 0.2
TETTI = {"p95_s": 0.75, "costo_medio_eur": 0.70}


def p95(valori: list[float]) -> float:
    return statistics.quantiles(valori, n=20, method="inclusive")[-1]


def verdetto(partenza: dict[str, float], ora: dict[str, float]) -> tuple[bool, str]:
    tempo = ora["p95_s"] <= partenza["p95_s"] * TETTI["p95_s"]
    costo = ora["costo_medio_eur"] <= partenza["costo_medio_eur"] * TETTI["costo_medio_eur"]
    regge_tempo = ora["p95_s"] <= partenza["p95_s"]
    regge_costo = ora["costo_medio_eur"] <= partenza["costo_medio_eur"]
    if (tempo and regge_costo) or (costo and regge_tempo):
        return True, "tetti rispettati"
    if tempo or costo:
        return False, "un tetto è rispettato, ma l'altro numero è peggiorato"
    return False, "nessuno dei due tetti è rispettato"


def carico(seme: int) -> list[dict[str, str]]:
    casi = [json.loads(r) for r in DATASET.read_text(encoding="utf-8").splitlines() if r.strip()]
    domande: list[dict[str, str]] = [c["input"] if "input" in c else c for c in casi] * 2
    random.Random(seme).shuffle(domande)
    return domande


def svuota_cache(base: str) -> None:
    comando = shlex.split(os.environ.get("COMPOSE", "docker compose")) + ["restart", "cache"]
    subprocess.run(comando, check=True, capture_output=True)
    for _ in range(30):
        pronto = httpx.get(f"{base}/ready", timeout=5).json()
        if pronto["checks"].get("cache") == "ok":
            return
        time.sleep(1)
    raise SystemExit("Redis non è tornato pronto: la misura partirebbe in uno stato diverso.")


async def misura(base: str, carico: list[dict[str, str]]) -> dict[str, float]:
    tempi: list[float] = []
    costi: list[float] = []
    async with httpx.AsyncClient(base_url=base, timeout=60.0) as client:
        token: dict[str, str] = {}
        ultima: dict[str, float] = {}
        for ruolo, utente in UTENTI.items():
            r = await client.post(
                "/api/auth/login", data={"username": utente, "password": "bootcamp"}
            )
            r.raise_for_status()
            token[ruolo] = r.json()["access_token"]
        for i, caso in enumerate(carico, start=1):
            ruolo = caso["role"]
            attesa = ultima.get(ruolo, 0.0) + PAUSA_PER_UTENTE_S - time.monotonic()
            if attesa > 0:
                await asyncio.sleep(attesa)
            ultima[ruolo] = time.monotonic()
            inizio = time.perf_counter()
            r = await client.post(
                "/api/ai/advice",
                json={"question": caso["question"]},
                headers={"Authorization": f"Bearer {token[ruolo]}"},
            )
            tempi.append(time.perf_counter() - inizio)
            r.raise_for_status()
            corpo: dict[str, Any] = r.json()
            costi.append(float(corpo["cost_eur"]))
            print(f"  {i:3}/{len(carico)}  {tempi[-1]:5.2f}s  EUR {costi[-1]:.6f}", flush=True)
    return {"n": len(carico), "p95_s": p95(tempi), "costo_medio_eur": statistics.fmean(costi)}


def main() -> None:
    argomenti = argparse.ArgumentParser()
    argomenti.add_argument("--base", default="http://localhost:8000")
    argomenti.add_argument("--salva", action="store_true")
    argomenti.add_argument("--seme", type=int, default=9)
    args = argomenti.parse_args()
    svuota_cache(args.base)
    ora = asyncio.run(misura(args.base, carico(args.seme)))
    print(
        f"p95 {ora['p95_s']:.2f}s   "
        f"costo medio EUR {ora['costo_medio_eur']:.6f}   ({int(ora['n'])} risposte)"
    )
    if args.salva:
        PARTENZA.parent.mkdir(exist_ok=True)
        PARTENZA.write_text(json.dumps(ora, indent=2), encoding="utf-8")
        print(f"partenza salvata in {PARTENZA}")
        return
    if not PARTENZA.exists():
        raise SystemExit(f"Manca {PARTENZA}: prima si misura la partenza, con --salva.")
    partenza = json.loads(PARTENZA.read_text(encoding="utf-8"))
    ok, perche = verdetto(partenza, ora)
    print(
        f"tetti: p95 <= {partenza['p95_s'] * TETTI['p95_s']:.2f}s oppure "
        f"costo medio <= EUR {partenza['costo_medio_eur'] * TETTI['costo_medio_eur']:.6f} "
        f"-> {perche}"
    )
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
