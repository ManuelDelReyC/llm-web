# AGENTS.md

Local LLM "web agent": a Python agent loop that talks to a self-hosted
`llama.cpp` server and uses a SearXNG instance for web search plus a URL
fetcher. Everything is a personal, single-machine setup. No CI, no tests, no
lint, no dependency manifests.

## Runtime prerequisites

El script `./llm` gestiona todos los servicios. Dependen de un proyecto
hermano *fuera de este repo*:
`~/Proyectos/llama/src/llama.cpp/build/bin/llama-server` y un modelo GGUF en
`~/Proyectos/llama/models/*.gguf`. Si esas rutas no existen, `./llm` saldrá
con un error.

- **llama.cpp server → `127.0.0.1:8080`** gestionado por `./llm`.
- **SearXNG → `127.0.0.1:8081`** gestionado por `./llm` (Docker Compose en
  `searxng/`).
- **API del agente → `127.0.0.1:8090`** gestionada por `./llm api` / `./llm web`.
- **Open WebUI → `http://localhost:3000`** gestionado por `./llm web` (Docker
  Compose en `open-webui/`).
- **OpenCode** (opcional) lee `opencode.json` del repo y se conecta a la API
  local como proveedor personalizado. También existe un plan B con MCP
  documentado más abajo.

## Commands

### Modos de uso con `./llm`

```bash
./llm cli      # Terminal interactiva (llama-server + SearXNG + agente)
./llm api      # Solo API en http://127.0.0.1:8090
./llm web      # Navegador con Open WebUI (todo el stack)
./llm status   # Ver qué servicios están corriendo
./llm stop     # Detener todo
```

### Comandos individuales (legacy / depuración)

```bash
# Iniciar SearXNG manualmente (primera vez / después de reiniciar).
cd searxng && docker compose up -d
curl -s 'http://127.0.0.1:8081/search?q=Python&format=json' | python3 -m json.tool

# Ejecutar el agente (llama-server y SearXNG deben estar en marcha).
python3 agent/agent.py "tu pregunta"
python3 agent/agent.py --debug "tu pregunta"   # traza detallada en stderr

# Usar OpenCode (la API debe estar en marcha vía ./llm api).
opencode run "¿Cuál es la última versión estable de Python?"
opencode tui
```

### Parada

```bash
./llm stop
```

No hay suite de tests ni verificación automática. La única comprobación real
es ejecutar `agent/agent.py` o `./llm cli` contra los servicios activos.

## Architecture gotchas

- **Pure Python stdlib only for the agent tools.** No `requirements.txt`, no
  venv, no packages to install for `agent/*.py` (uses `urllib`, `subprocess`,
  `json`, `re`, `gzip`). The API (`server/main.py`) is the exception: it runs
  inside `.venv/` with `fastapi` + `uvicorn`. Do not add third-party
  dependencies to the agent without confirming — the zero-install design is
  intentional. `fetch_url.py` deliberately refuses Brotli (`br`) rather than
  pull in a dep.
- **The three Python files are importable modules AND standalone CLIs.**
  `agent.py` imports `search()` from `web_search.py` and `fetch()` from
  `fetch_url.py` and calls them in-process (no subprocesses). Both tools are
  still runnable standalone (`python3 agent/web_search.py "query"`,
  `python3 agent/fetch_url.py URL`) and print JSON to stdout. The future API
  (see `PLAN.md`) will import the same functions — keep them import-safe
  (no side effects at import time).
- **The model name is auto-detected at runtime.** `agent.py` queries
  `llama-server`'s `/v1/models` and uses the loaded GGUF's id, falling back to
  `DEFAULT_MODEL = "local-model"` when the server is unreachable (llama-server
  ignores the request's model field anyway). El único perfil soportado es
  Qwen3-30B-A3B-Q4_K_M, lanzado por `./llm`. Para ajustar capas/contexto usa
  las variables `NGL`, `CTX` y `BATCH` (p. ej. `NGL=20 ./llm cli`).
- **The Qwen3-30B profile is intentionally conservative.** `-ngl auto` puts as
  many layers as fit in VRAM and leaves the rest in CPU/RAM; context 8192 and
  batch 256 limit additional memory use. If startup still runs out of VRAM,
  pass an explicit lower layer count, e.g. `NGL=20 ./llm cli`.
  Lowering `ngl` makes it slower but moves more layers to RAM.
- **SearXNG must have the `json` format enabled**, or `web_search.py` gets a
  403. It is enabled in `searxng/core-config/settings.yml`
  (`search.formats: [html, json]`). That dir is bind-mounted to
  `/etc/searxng/`, so after editing `settings.yml` run
  `docker compose restart core` to apply.
- **Ports are configurable in `searxng/.env`** (`SEARXNG_PORT=8081`,
  `SEARXNG_HOST=127.0.0.1`). If you change them, also update the hardcoded
  `SEARXNG_URL` in `web_search.py` and `LLAMA_BASE_URL`/port in `agent.py`.
  Los puertos también se pueden cambiar con variables de entorno al invocar
  `./llm`: `LLAMA_PORT`, `SEARXNG_PORT`, `API_PORT`, `WEBUI_PORT`. La API usa
  `LLAMA_URL` (default `http://127.0.0.1:8080`) para hablar con llama-server.
- **`fetch_url.py` truncates page text to `MAX_CONTENT_LENGTH` chars**
  (env var, default 12000; invalid values fall back to 12000) and only
  accepts `text/html`, `application/xhtml+xml`, or `text/plain`.
- **Open WebUI needs the API to listen on `0.0.0.0`.** Docker containers on
  Linux cannot reach `127.0.0.1` of the host. `./llm web` arranca la API en
  `0.0.0.0:8090` automáticamente; el compose de Open WebUI usa
  `host.docker.internal:8090` más `extra_hosts` para alcanzarla. Si tu
  instalación de Docker no soporta `host.docker.internal`, cambia la API a
  `0.0.0.0` y ajusta `OPENAI_API_BASE_URL` a la IP LAN del host o usa
  `network_mode: host` para Open WebUI.
- **Open WebUI downloads an embedding model on first start.** It fetches
  `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face, so the UI may
  be unresponsive for a few minutes until the download finishes.
- **OpenCode usa `opencode.json` del repo.** El proveedor `llm-web` apunta a
  `http://127.0.0.1:8090/v1` y el modelo seleccionado es `llm-web/local-model`.
  La API ignora el campo `model` (lo hace también llama-server), así que el
  valor sirve solo para que OpenCode pueda dirigir las peticiones. La primera
  vez selecciona el modelo con `/models` o `opencode models`.
- **Plan B con MCP disponible.** Si el proveedor personalizado no funciona
  bien (por ejemplo, problemas de tool calling con el modelo local), existe
  un fallback en `mcp/web_search.py` y `mcp/fetch_url.py` que expone las
  herramientas como servidores MCP. Ver sección "OpenCode" más abajo.

## OpenCode

La Fase 3 añade soporte para usar este proyecto como backend de OpenCode.
Hay dos opciones; la recomendada es la **opción A** porque reutiliza la
misma lógica de agente probada en CLI, API y Open WebUI.

### Opción A — proveedor personalizado contra la API (recomendada)

Con la API arrancada (`./llm api`), el archivo
`opencode.json` del repo registra automáticamente el proveedor `llm-web`
con `baseURL` `http://127.0.0.1:8090/v1`.

```bash
# Desde la raíz del repo, donde se encuentra opencode.json.
opencode run "¿Qué novedades hay hoy sobre inteligencia artificial?"
```

La primera vez puede ser necesario seleccionar el modelo:

```bash
opencode models   # o /models dentro del TUI
```

Elige `llm-web/local-model`. Como la API ejecuta el bucle agente completo
(incluyendo `web_search` y `fetch_url`), OpenCode recibe directamente la
respuesta final sin necesidad de herramientas adicionales.

### Opción B — llama-server directo + herramientas MCP (fallback)

Si la opción A no da buenos resultados (por ejemplo, el modelo local no
responde bien al formato de tool calls que espera OpenCode), se puede
apuntar OpenCode directamente a llama-server y darle las herramientas web
como servidores MCP.

Sustituye la sección `provider` y añade `mcp` en `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "llama.cpp": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama-server (directo)",
      "options": {
        "baseURL": "http://127.0.0.1:8080/v1"
      },
      "models": {
        "local-model": {
          "name": "Qwen3 local (directo)",
          "limit": {
            "context": 32768,
            "output": 4096
          }
        }
      }
    }
  },
  "model": "llama.cpp/local-model",
  "small_model": "llama.cpp/local-model",
  "mcp": {
    "llm-web-search": {
      "type": "local",
      "command": ["python3", "mcp/web_search.py"],
      "enabled": true
    },
    "llm-web-fetch": {
      "type": "local",
      "command": ["python3", "mcp/fetch_url.py"],
      "enabled": true
    }
  }
}
```

En este modo OpenCode es el que orquesta el bucle de herramientas, así que
es conveniente añadir en los prompts algo como "usa web_search" cuando se
necesite información actual.

### Decisión

Por defecto se usa la **opción A**: es la más sencilla, mantiene un solo
punto de lógica (la API) y ha funcionado en CLI y Open WebUI. La opción B
se mantiene como alternativa documentada por si el modelo local muestra
problemas de tool calling a través del proveedor OpenAI-compatible.

## Files to ignore / handle with care

- **`scripts/alacritty/` is an unrelated nested git repository, not tracked by
  this repo** (`git ls-files scripts/alacritty` is empty) and referenced
  nowhere. Ignore it — don't search, build, or edit it. It will otherwise
  dominate repo-wide greps with thousands of Rust files.
- **`Clave.txt` is the SearXNG `secret_key`**, duplicated verbatim as
  `server.secret_key` in `searxng/core-config/settings.yml`. It is a committed
  secret: don't paste it into logs/output, and if you rotate it, update both
  places.
- `.gitignore` now ignores `.venv/` and Python cache files. Only
  `agent/__pycache__/*.pyc` was committed historically; avoid adding more
  build artifacts to git.

## Conventions

- **`PLAN.md` is the project roadmap.** It lists phases 0-4 with concrete
  steps and which are done; each phase is meant to run in its own session.
  Check it before starting feature work and update its status after
  completing a phase.
- Single `main` branch with an `origin` remote; commit directly, no PR flow.
- Comments, prompts, and CLI messages are written in Spanish — match that when
  editing this code.
