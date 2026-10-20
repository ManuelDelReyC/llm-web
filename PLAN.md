# PLAN.md — Hoja de ruta de llm-web

Objetivo final: complementar el LLM local con búsqueda web y exponerlo de tres
formas: (1) API consumible por otras aplicaciones, (2) modelo local usable en
OpenCode, (3) chat tipo ChatGPT desde el navegador.

Cada fase es independiente y verificable. Están pensadas para ejecutarse en
conversaciones separadas: lee `AGENTS.md` + este archivo y empieza por la
primera fase no marcada como hecha.

## Contexto

- Hardware: i7-8700, 16 GB VRAM, 32 GB RAM (~23 GB libres con el 30B cargado).
- Servicios: llama-server en `127.0.0.1:8080` (perfiles en `scripts/`), SearXNG
  en `127.0.0.1:8081` (Docker, ver `README.md`).
- El agente CLI (`agent/agent.py`) ya funciona: bucle con tools `web_search` y
  `fetch_url`, auto-detección del modelo vía `/v1/models`.

## Decisiones ya tomadas (no rediscutir salvo motivo)

- **API compatible con OpenAI** (`POST /v1/chat/completions`) como pieza
  central: desbloquea los tres objetivos con una sola pieza.
- **FastAPI + venv**: se aceptan dependencias para la API (en `.venv/`), el
  resto del proyecto sigue siendo stdlib puro.
- **Navegador: Open WebUI** en Docker (opción sin código propio).
- **OpenCode**: primero probar la API como proveedor personalizado (solo
  config); plan B: llama-server directo + tools web vía MCP.
- **Sin API key** mientras todo escuche en `127.0.0.1`. Se añade en la Fase 4,
  al exponer el servidor a la red local.
- **Sin llama-swap de momento**: el usuario elige el perfil de modelo al
  arrancar. La API tendrá el backend configurable (`LLAMA_URL`) para no
  bloquear esa opción en el futuro.
- **`MAX_CONTENT_LENGTH` por variable de entorno** con defecto razonable en
  código; no se ata al perfil de modelo (las variables de entorno no viajan
  entre terminales).

## Fase 0 — Consolidar el agente ✅ HECHA (2026-10-15)

1. Contextos por defecto: 14B → 16384, 30B → 8192 (en `scripts/`).
2. `MAX_CONTENT_LENGTH` en `fetch_url.py` configurable por entorno,
   defecto 12000.
3. `agent.py` importa `search()`/`fetch()` directamente en vez de lanzar
   subprocesos; los CLIs de las tools se mantienen.
4. Verificación: agente CLI end-to-end con el 30B activo.

## Fase 1 — API FastAPI ✅ HECHA (2026-10-15)

1. Crear `.venv` en la raíz del repo e instalar `fastapi` + `uvicorn`
   (únicas dependencias nuevas del proyecto). Añadir `.venv/` a un
   `.gitignore` nuevo (hoy no existe `.gitignore`).
2. `server/main.py`:
   - `POST /v1/chat/completions`: ejecuta el bucle agente actual (mismo
     system prompt, mismas tools, misma auto-detección de modelo).
     Importar `agent/agent.py` como módulo (p. ej. añadiendo `agent/` a
     `sys.path`); no duplicar la lógica.
   - `GET /v1/models`: proxy de la respuesta de llama-server (los clientes
     lo necesitan para listar el modelo).
   - Backend configurable con `LLAMA_URL` (defecto `http://127.0.0.1:8080`).
   - Escuchar en `127.0.0.1:8090`.
3. `scripts/start_agent_api.sh`: activa el venv y arranca uvicorn.
4. Primero respuesta completa; **streaming (SSE) como último paso** de la
   fase (la UX "escribe en vivo" la necesitará Open WebUI).
5. Verificación: `curl` al endpoint con una pregunta que fuerce búsqueda
   web; comprobar que responde JSON OpenAI válido.

## Fase 2 — Navegador: Open WebUI ✅ HECHA (2026-10-15)

1. Servicio Open WebUI en Docker (compose nuevo en `open-webui/`).
2. Configurado contra la API de la Fase 1 por defecto
   (`http://host.docker.internal:8090/v1`).
3. Verificación: chat en el navegador (`http://localhost:3000`) que usa
   búsqueda web cuando se le pregunta algo actual.

## Fase 3 — OpenCode ✅ HECHA (2026-10-20)

1. Registrar la API como proveedor personalizado en `opencode.json`
   (baseURL `http://127.0.0.1:8090/v1`). Probar calidad real.
2. Si no va fino, plan B: OpenCode apuntando directo a llama-server +
   tools web como servidores MCP.
3. Decidir con datos; documentar la opción final en `AGENTS.md`.

Realizado:
- Creado `opencode.json` con el proveedor `llm-web` apuntando a la API local.
- Creados `mcp/web_search.py` y `mcp/fetch_url.py` como servidores MCP stdio
  (stdlib puro) para el plan B.
- Documentada la opción recomendada (A: API personalizada) y el fallback
  (B: llama-server directo + MCP) en `AGENTS.md`.
- Actualizado `README.md` con la sección de OpenCode.

## Fase 4 — Red local (solo cuando el usuario lo pida)

1. API key por header `Authorization: Bearer ...` (validación en FastAPI,
   ~15 líneas) y clave en variable de entorno.
2. Escuchar en la IP local en vez de `127.0.0.1`.
3. Verificación: acceso desde el móvil (misma WiFi) a la API / Open WebUI.
