#!/usr/bin/env bash
# Arranca la API del agente en 127.0.0.1:8090.
# Requiere el venv creado en la raíz del repo.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo "Error: no existe .venv. Crea el entorno virtual primero." >&2
    exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

# El backend de llama.cpp se configura con LLAMA_URL (defecto 127.0.0.1:8080).
export LLAMA_URL="${LLAMA_URL:-http://127.0.0.1:8080}"

# Host/puerto donde escucha la API. Por defecto 127.0.0.1:8090.
# Para usar Open WebUI en Docker, poner API_HOST=0.0.0.0 y acceder desde
# http://host.docker.internal:8090/v1.
export API_HOST="${API_HOST:-127.0.0.1}"
export API_PORT="${API_PORT:-8090}"

exec uvicorn server.main:app --host "$API_HOST" --port "$API_PORT"
