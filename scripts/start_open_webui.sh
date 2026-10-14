#!/usr/bin/env bash
# Arranca Open WebUI apuntando a la API del agente.
# La API debe estar en marcha y escuchando en 0.0.0.0:8090 para que el
# contenedor Docker pueda contactarla vía host.docker.internal.

set -euo pipefail

cd "$(dirname "$0")/../open-webui"

export OPEN_WEBUI_PORT="${OPEN_WEBUI_PORT:-3000}"

echo "Arrancando Open WebUI en http://127.0.0.1:${OPEN_WEBUI_PORT} ..."
echo "Asegúrate de tener la API ejecutándose con: API_HOST=0.0.0.0 ./scripts/start_agent_api.sh"

docker compose up -d
