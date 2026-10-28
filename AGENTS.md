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
./llm cli          # Terminal interactiva (llama-server + SearXNG + agente)
./llm api          # Solo API en http://127.0.0.1:8090
./llm web          # Navegador con Open WebUI (todo el stack)
./llm status       # Ver qué servicios están corriendo
./llm stop         # Detener todo
./llm webui-reset  # Restablecer la contraseña de admin de Open WebUI
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

La configuración de `opencode.json` apunta OpenCode directamente a
llama-server (`http://127.0.0.1:8080/v1`) y le da acceso a la búsqueda web
local a través del servidor MCP `mcp/web_search.py`. OpenCode orquesta el
bucle de herramientas: decide cuándo buscar, cuándo leer archivos, cuándo
ejecutar un comando, etc.

Para que esto funcione, `./llm` arranca llama-server con
`Qwen3-Coder-30B-A3B-Instruct.Q4_K_M` y una ventana de contexto de 32768
tokens. El modelo Coder sigue los esquemas de tool calls mucho mejor que el
modelo de chat general y es el que la comunidad usa con agentes locales.

```bash
# Desde la raíz del repo, donde se encuentra opencode.json.
opencode run "¿Qué novedades hay hoy sobre inteligencia artificial?"
```

La primera vez puede ser necesario seleccionar el modelo:

```bash
opencode models   # o /models dentro del TUI
```

Elige `llama/qwen3-coder`. Si quieres que busque información actual,
indícalo explícitamente en el prompt (por ejemplo, "busca en la web
primero"); de lo contrario OpenCode puede no invocar `web_search`.

### Volver al modelo de chat general

Si prefieres usar el Qwen3-30B general para CLI/Open WebUI, arranca con:

```bash
MODEL="$HOME/Proyectos/llama/models/Qwen3-30B-A3B-Q4_K_M.gguf" ./llm cli
```

OpenCode seguirá conectándose a llama-server, así que elige el modelo Coder
cuando vayas a programar con OpenCode.

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
