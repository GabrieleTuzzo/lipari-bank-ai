#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE:-http://localhost:8000}
ok() { printf '  ok  %s\n' "$1"; }
no() { printf '  NO  %s\n' "$1"; exit 1; }
campo() { python -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
token() {
  curl -sf -X POST "$BASE/api/auth/login" -d "username=$1&password=bootcamp" | campo "d['access_token']"
}

[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health")" = 200 ] && ok "vivo" || no "vivo"
[ "$(curl -s "$BASE/ready" | campo "d['status']")" = ready ] && ok "pronto" || no "pronto"

TOK_M=$(token mbianchi)
TOK_G=$(token grossi)
TOK_L=$(token lverdi)
ok "login di tre ruoli"

ADV_M=$(curl -sf -X POST "$BASE/api/ai/advice" -H "Authorization: Bearer $TOK_M" \
  -H "Content-Type: application/json" -d '{"question":"ven ok?"}')
[ "$(echo "$ADV_M" | campo "len(d['citations']) > 0 and bool(d['rewritten_query'])")" = True ] \
  && ok "advice di Marco: citazione e riscrittura" || no "advice di Marco"

RISERVATA='{"question":"Cosa non si comunica al cliente sulle istruttorie in corso?"}'
citati() {
  curl -sf -X POST "$BASE/api/ai/advice" -H "Authorization: Bearer $1" \
    -H "Content-Type: application/json" -d "$RISERVATA" | campo "sorted({c['document_id'] for c in d['citations']})"
}
DOC_G=$(citati "$TOK_G")
DOC_M=$(citati "$TOK_M")
case "$DOC_G" in *aml_controparti_venezuela*) ok "Giulia vede l'istruttoria" ;; *) no "Giulia: $DOC_G" ;; esac
case "$DOC_M" in *aml_controparti_venezuela*) no "Marco vede l'istruttoria" ;; *) ok "Marco no" ;; esac

RUN=$(curl -sf -X POST "$BASE/api/ai/agent" -H "Authorization: Bearer $TOK_M" \
  -H "Content-Type: application/json" \
  -d '{"message":"il cliente C-10234 vuole fare un bonifico di 25.000 verso il Venezuela dal conto principale: posso procedere?"}')
[ "$(echo "$RUN" | campo "d['steps'] >= 3 and {'find_customer_accounts','get_account_balance'} <= set(d['tool_calls']) and d['stopped_by'] == 'model'")" = True ] \
  && ok "agente: $(echo "$RUN" | campo "','.join(d['tool_calls'])")" || no "agente: $RUN"

curl -sf -X POST "$BASE/api/ai/advice" -H "Authorization: Bearer $TOK_M" \
  -H "Content-Type: application/json" -d '{"question":"ven ok?"}' >/dev/null
${COMPOSE:-docker compose} logs api --since 1m 2>/dev/null | grep -q '"cache_hit": true' \
  && ok "riscrittura dalla cache" || no "nessun cache_hit nei log"

DAL=$(date -u +%Y-%m-%d)
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/admin/cost-report?dal=$DAL" \
  -H "Authorization: Bearer $TOK_M")" = 403 ] && ok "Marco non vede i costi" || no "Marco vede i costi"
[ "$(curl -sf "$BASE/api/admin/cost-report?dal=$DAL" -H "Authorization: Bearer $TOK_L" \
  | campo "float(d['totale_eur']) > 0")" = True ] && ok "Lucia vede i costi" || no "rapporto di Lucia"

echo "smoke: tutto a posto"
