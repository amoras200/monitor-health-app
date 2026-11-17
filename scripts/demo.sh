#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  printf 'Arquivo .env nao encontrado em %s\n' "$ROOT_DIR" >&2
  exit 1
fi

set -a
. ./.env
set +a

: "${API_KEY:?API_KEY nao carregada}"

API_URL="${API_URL:-https://localhost}"
SERVICE_NAME="${SERVICE_NAME:-Ciclo-Teste}"
FAIL_URL="${FAIL_URL:-https://httpbin.org/status/500}"
RECOVERY_URL="${RECOVERY_URL:-https://example.net/}"
POLL_SECONDS="${POLL_SECONDS:-10}"
POLL_ITERATIONS="${POLL_ITERATIONS:-36}"

AUTH=(-H "X-API-Key: $API_KEY")

api_get() {
  curl -sS -k "$API_URL$1" "${AUTH[@]}"
}

api_delete() {
  curl -sS -k -X DELETE "$API_URL$1" "${AUTH[@]}" -o /dev/null -w '%{http_code}'
}

post() {
  curl -sS -k -X POST "$API_URL/services" "${AUTH[@]}" \
    -H 'Content-Type: application/json' -d "$1"
}

poll_state() {
  local want="$1" body state

  for i in $(seq 1 "$POLL_ITERATIONS"); do
    sleep "$POLL_SECONDS"
    body=$(curl -sS -k "$API_URL/services/$CID/status" "${AUTH[@]}")

    if ! python3 -c 'import json,sys; d=json.load(sys.stdin); assert "state" in d and "last_24h" in d' <<<"$body" 2>/dev/null; then
      printf 'Resposta inesperada para %s: %s\n' "$CID" "$body" >&2
      return 1
    fi

    printf '[%s] ' "$(date +%H:%M:%S)"
    python3 -c 'import json,sys; d=json.load(sys.stdin); s=d["last_24h"]; print(d["name"], "state="+d["state"], "falhas="+str(d["consecutive_failures"]), "checks="+str(s["checks"]), "uptime="+str(s["uptime_percent"]), "url="+d["url"])' <<<"$body"

    state=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])' <<<"$body")
    if [ "$state" = "$want" ]; then
      return 0
    fi
  done

  return 1
}

ids=$(api_get /services | python3 -c 'import json,sys
for service in json.load(sys.stdin):
    if service["name"] in {"Ciclo", "Ciclo-Teste"}:
        print(service["id"])')

if [ -n "$ids" ]; then
  while IFS= read -r id; do
    [ -z "$id" ] && continue
    code=$(api_delete "/services/$id")
    printf 'DELETE %s -> HTTP %s\n' "$id" "$code"
  done <<< "$ids"
fi

if ! api_get /services | python3 -c 'import json,sys; sys.exit(0 if any(s["name"] == "Sempre OK" for s in json.load(sys.stdin)) else 1)'; then
  resp=$(post '{"name":"Sempre OK","url":"https://example.com/"}')
  printf '%s\n' "$resp" | python3 -m json.tool
fi

START_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

resp=$(post "{\"name\":\"$SERVICE_NAME\",\"url\":\"$FAIL_URL\"}")
printf '%s\n' "$resp" | python3 -m json.tool

if ! CID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$resp"); then
  printf 'Falha ao criar o servico. Resposta: %s\n' "$resp" >&2
  exit 1
fi

printf 'CID=%s\n' "$CID"
printf 'Aguardando %s ficar down (ate %s minutos)...\n' "$SERVICE_NAME" "$((POLL_ITERATIONS * POLL_SECONDS / 60))"

if ! poll_state down; then
  printf 'O servico nao chegou a down. Nada foi alterado.\n' >&2
  exit 1
fi

printf '\nQueda registrada. Confira o email [ALERTA] %s fora do ar.\n' "$SERVICE_NAME"
sleep 2
printf '%s\n' 'Alertas recentes:'
docker compose logs worker --since "$START_TS" 2>&1 | grep -E 'Alerta enviado|Falha ao enviar' || true

if [ -t 0 ]; then
  printf '\nPressione Enter para simular a correcao...'
  read -r _
fi

MONGO_SHELL_URI="mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@localhost:27017/${MONGO_DB}?authSource=${MONGO_DB}"

printf '\nAtualizando %s para %s...\n' "$CID" "$RECOVERY_URL"
if ! docker compose exec -T mongo mongosh "$MONGO_SHELL_URI" --quiet --eval \
  "db.services.updateOne({_id: ObjectId('$CID')}, {\$set: {url: '$RECOVERY_URL'}})"; then
  printf 'Falha ao atualizar a URL.\n' >&2
  exit 1
fi

printf 'Aguardando recuperacao...\n'
if ! poll_state up; then
  printf 'O servico nao voltou a up.\n' >&2
  exit 1
fi

printf '\nRecuperacao registrada. Confira o email [OK] %s voltou.\n' "$SERVICE_NAME"
sleep 5
printf '%s\n' 'Alertas recentes:'
docker compose logs worker --since "$START_TS" 2>&1 | grep -E 'Alerta enviado|Falha ao enviar' || true

printf '\nEstado final:\n'
api_get /services | python3 -m json.tool
