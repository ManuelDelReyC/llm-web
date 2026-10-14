# AGENTS.md

Local LLM "web agent": a Python agent loop that talks to a self-hosted
`llama.cpp` server and uses a SearXNG instance for web search plus a URL
fetcher. Everything is a personal, single-machine setup. No CI, no tests, no
lint, no dependency manifests.

## Runtime prerequisites (not auto-started)

The agent needs two external services running before it works. Neither is part
of `python3 agent/agent.py`; you must start them yourself.

- **llama.cpp server → `127.0.0.1:8080`** via one of the model-specific
  scripts in `scripts/` (`start_llm_server_qwen14b.sh` or
  `start_llm_server_qwen30b.sh`).
  It depends on a sibling project *outside this repo*:
  `~/Proyectos/llama/src/llama.cpp/build/bin/llama-server` and a GGUF model at
  `~/Proyectos/llama/models/*.gguf`. If those paths don't exist, the script
  exits early.
- **SearXNG → `127.0.0.1:8081`** via Docker Compose in `searxng/`.
- **Open WebUI → `http://localhost:3000`** (optional) via Docker Compose in
  `open-webui/`. It talks to the agent API, not directly to llama-server.

## Commands

```bash
# Start SearXNG (first time / after reboot). README.md only shows the routine
# `docker compose restart core` + logs, which assumes it's already created.
cd searxng && docker compose up -d          # starts `core` + `valkey` (cache)
curl -s 'http://127.0.0.1:8081/search?q=Python&format=json' | python3 -m json.tool

# Start one model-specific LLM server profile.
./scripts/start_llm_server_qwen14b.sh        # [ngl] [ctx], defaults 99 and 16384
./scripts/start_llm_server_qwen30b.sh        # [ngl] [ctx] [batch], defaults auto/8192/256

# Run the agent (both services must be up).
python3 agent/agent.py "tu pregunta"
python3 agent/agent.py --debug "tu pregunta"   # verbose trace to stderr

# Start the OpenAI-compatible API (needs .venv).
./scripts/start_agent_api.sh                  # listens on 127.0.0.1:8090

# Start Open WebUI (optional; needs the API running with API_HOST=0.0.0.0).
API_HOST=0.0.0.0 ./scripts/start_agent_api.sh  # expose the API to Docker
./scripts/start_open_webui.sh                  # http://localhost:3000
```

There is no test suite or verification step. The only real check is running
`agent/agent.py` end-to-end against the live services.

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
  ignores the request's model field anyway). To change models, edit
  `start_llm_server_qwen14b.sh` or
  `start_llm_server_qwen30b.sh` — don't reintroduce a hardcoded model constant.
- **The Qwen3-30B profile is intentionally conservative.** `-ngl auto` puts as
  many layers as fit in VRAM and leaves the rest in CPU/RAM; context 8192 and
  batch 256 limit additional memory use. If startup still runs out of VRAM,
  pass an explicit lower layer count, e.g. `./scripts/start_llm_server_qwen30b.sh 20`.
  Lowering `ngl` makes it slower but moves more layers to RAM.
- **SearXNG must have the `json` format enabled**, or `web_search.py` gets a
  403. It is enabled in `searxng/core-config/settings.yml`
  (`search.formats: [html, json]`). That dir is bind-mounted to
  `/etc/searxng/`, so after editing `settings.yml` run
  `docker compose restart core` to apply.
- **Ports are configurable in `searxng/.env`** (`SEARXNG_PORT=8081`,
  `SEARXNG_HOST=127.0.0.1`). If you change them, also update the hardcoded
  `SEARXNG_URL` in `web_search.py` and `LLAMA_BASE_URL`/port in `agent.py` /
  `start_llm_server_qwen14b.sh` / `start_llm_server_qwen30b.sh` — these are not
  wired to `.env`. The API listens on `API_HOST:API_PORT` (default
  `127.0.0.1:8090`) and uses `LLAMA_URL` (default `http://127.0.0.1:8080`) to
  reach llama-server; edit `scripts/start_agent_api.sh` or pass env vars to
  change them.
- **`fetch_url.py` truncates page text to `MAX_CONTENT_LENGTH` chars**
  (env var, default 12000; invalid values fall back to 12000) and only
  accepts `text/html`, `application/xhtml+xml`, or `text/plain`.
- **Open WebUI needs the API to listen on `0.0.0.0`.** Docker containers on
  Linux cannot reach `127.0.0.1` of the host. Start the API with
  `API_HOST=0.0.0.0 ./scripts/start_agent_api.sh`; the Open WebUI compose
  uses `host.docker.internal:8090` plus `extra_hosts` to reach it. If your
  Docker setup does not support `host.docker.internal`, switch the API to
  `0.0.0.0` and set `OPENAI_API_BASE_URL` to the host's LAN IP or use
  `network_mode: host` for Open WebUI.
- **Open WebUI downloads an embedding model on first start.** It fetches
  `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face, so the UI may
  be unresponsive for a few minutes until the download finishes.

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
