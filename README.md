# llm-web

Agente web local basado en LLM. Un bucle agente en Python (solo biblioteca
estándar, sin dependencias) que consulta un modelo local servido por
[llama.cpp](https://github.com/ggml-org/llama.cpp) y puede buscar en internet
a través de una instancia local de [SearXNG](https://docs.searxng.org/).

Todo se gestiona con un único script: **`./llm`**.

## Arquitectura

| Componente | Descripción |
| --- | --- |
| `./llm` | Script único para arrancar/parar el stack en los tres modos de uso. |
| `agent/agent.py` | Bucle principal: envía la pregunta al LLM con dos herramientas (`web_search` y `fetch_url`), ejecuta las llamadas y devuelve la respuesta final. |
| `agent/web_search.py` | CLI que busca en SearXNG y devuelve los resultados en JSON. |
| `agent/fetch_url.py` | CLI que descarga una página, la convierte a texto (máx. 12000 caracteres por defecto, configurable con `MAX_CONTENT_LENGTH`) y devuelve JSON. |
| `searxng/` | SearXNG en Docker Compose, en `http://127.0.0.1:8081` (puerto configurable en `searxng/.env`). |
| `server/main.py` | API compatible con OpenAI (`/v1/chat/completions` y `/v1/models`) que expone el agente. |
| `open-webui/` | Open WebUI en Docker, preconfigurado contra la API propia. |
| `opencode.json` | Configuración de OpenCode para usar llama-server directamente y la búsqueda web local como MCP. |
| `mcp/web_search.py` | Servidor MCP con la herramienta `web_search` (plan B). |
| `mcp/fetch_url.py` | Servidor MCP con la herramienta `fetch_url` (plan B). |

El agente detecta automáticamente el modelo cargado consultando
`/v1/models` del servidor, así que **no hay que editar ningún nombre de
modelo**. El perfil por defecto es `Qwen3-Coder-30B-A3B-Instruct.Q4_K_M`
para que OpenCode pueda programar con él. El modelo de chat general sigue
disponible mediante la variable `MODEL`.

## Requisitos

- Python 3 (solo biblioteca estándar para el agente; `.venv` con `fastapi` + `uvicorn` para la API).
- Docker Compose (para SearXNG y Open WebUI).
- llama.cpp compilado y el modelo GGUF en `~/Proyectos/llama/models/`
  (ver las rutas dentro de `./llm`).

## Uso rápido

```bash
./llm cli     # Terminal interactiva
./llm api     # Solo API (para otras apps)
./llm web     # Navegador con Open WebUI
./llm status  # Ver qué está corriendo
./llm stop    # Parar todo
```

Cada comando arranca solo los servicios que necesita, espera a que estén
listos y reutiliza los que ya estén corriendo. Los modos `api` y `web` se
quedan en primer plano; presiona `Ctrl+C` para detener todo.

| Modo | Servicios levantados |
| --- | --- |
| `cli` | llama-server + SearXNG + agente interactivo |
| `api` | llama-server + SearXNG + API en `http://127.0.0.1:8090` |
| `web` | llama-server + SearXNG + API (`0.0.0.0:8090`) + Open WebUI |

## Puesta en marcha

### 1. Terminal interactiva

```bash
./llm cli
```

Aparecerá un prompt `>`. Escribe tu pregunta y el agente responderá,
usando búsqueda web cuando sea necesario. Mantiene el historial de la
conversación hasta que salgas o uses `/clear`.

Ejemplo de sesión:

```text
> ¿Cuál es la última versión estable de Python?
La última versión estable de Python es...

> /clear
Historial borrado.

> /quit
```

Comandos disponibles dentro del chat:

- `/quit` o `/salir`: cerrar.
- `/debug`: alternar traza detallada.
- `/clear`: borrar el historial de la conversación.

También puedes seguir usando el agente en modo "una sola pregunta":

```bash
python3 agent/agent.py "¿Cuál es la última versión estable de Python?"
python3 agent/agent.py --debug "pregunta"   # traza detallada en stderr
```

### 2. API OpenAI-compatible

```bash
./llm api
```

La API escuchará en `http://127.0.0.1:8090`. Prueba rápida:

```bash
curl -s http://127.0.0.1:8090/v1/models | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8090/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"¿Qué hora es?"}]}' | python3 -m json.tool
```

Presiona `Ctrl+C` en el terminal de `./llm api` para detener todo.

### 3. Interfaz web con Open WebUI

```bash
./llm web
```

Abre `http://localhost:3000`, crea la cuenta de administrador la primera vez y
empieza a chatear. Para forzar una búsqueda web, pregunta algo con fecha
actual; el agente usará `web_search` automáticamente.

> **Nota:** la primera vez que arrancas Open WebUI descarga un modelo de
> embeddings desde Hugging Face, lo que puede tardar varios minutos. Hasta
> entonces la interfaz puede no responder.

#### Recuperar el acceso a Open WebUI

Si olvidas la contraseña del administrador, no hace falta borrar el volumen ni
perder los chats:

```bash
./llm webui-reset
```

El comando pide una contraseña nueva, la guarda en la base de datos SQLite de
Open WebUI y conserva usuarios, conversaciones y ajustes. Si Open WebUI está
corriendo, lo detiene temporalmente, actualiza el hash bcrypt del usuario
administrador y lo vuelve a arrancar. Entra con el email que imprime el
comando (en esta instalación, `admin@localhost`) y la contraseña que acabas
de escribir en el terminal, no con la que recuerde el navegador.

### 4. OpenCode

El archivo `opencode.json` configura OpenCode para que hable directamente con
llama-server (`http://127.0.0.1:8080/v1`) y use la búsqueda web local a través
de un servidor MCP (`mcp/web_search.py`). OpenCode es el que decide cuándo
buscar, leer archivos o ejecutar comandos.

```bash
# Desde la raíz del repo, donde está opencode.json.
# El comando arranca llama-server con el modelo Coder y SearXNG.
./llm cli

# En otra terminal, con los servicios en marcha:
opencode run "¿Cuál es la última versión estable de Python?"
```

La primera vez selecciona el modelo:

```bash
opencode models   # o /models dentro del TUI
```

Elige `llama/qwen3-coder`.

Si quieres que OpenCode busque información actual, indícalo en el prompt
(por ejemplo, "busca en la web primero"). De lo contrario puede no invocar
`web_search`.

### 5. Parar los servicios

```bash
./llm stop
```

También puedes consultar el estado en cualquier momento:

```bash
./llm status
```

## Personalización

Puedes cambiar puertos, rutas y parámetros del modelo mediante variables de
entorno:

```bash
# Cambiar puertos
LLAMA_PORT=8080 SEARXNG_PORT=8081 API_PORT=8090 WEBUI_PORT=3000 ./llm web

# Reducir carga de VRAM (mueve capas a RAM)
NGL=20 CTX=4096 ./llm cli

# Rutas alternativas
MODEL=/ruta/al/modelo.gguf LLAMA_SERVER=/ruta/a/llama-server ./llm api
```

Variables disponibles:

- `LLAMA_PORT`, `SEARXNG_PORT`, `API_PORT`, `WEBUI_PORT`: puertos de cada
  servicio.
- `NGL`: capas offload a GPU (`auto` por defecto; baja el número si te quedas
  sin VRAM).
- `CTX`: tamaño de contexto (por defecto 8192).
- `BATCH`: batch size (por defecto 256).
- `MODEL`: ruta al GGUF (por defecto `~/Proyectos/llama/models/Qwen3-30B-A3B-Q4_K_M.gguf`).
- `LLAMA_SERVER`: ruta al binario `llama-server`.

Si cambias `SEARXNG_PORT`, recuerda actualizar también `searxng/.env` y
`agent/web_search.py`.

## Herramientas por separado

Las herramientas siguen funcionando como CLIs independientes:

```bash
python3 agent/web_search.py "consulta"
python3 agent/fetch_url.py "https://ejemplo.com"
```

## Notas

- La configuración de SearXNG vive en `searxng/core-config/settings.yml`
  (montado en `/etc/searxng/` del contenedor). El formato de respuesta `json`
  debe estar habilitado ahí o las búsquedas del agente fallarán con 403.
  Tras editar el archivo: `cd searxng && docker compose restart core`.
- `Clave.txt` contiene el `secret_key` de SearXNG (el mismo valor aparece en
  `settings.yml`). Es un secreto: si se rota, hay que actualizar ambos sitios.
- Los logs de los servicios en background se guardan en
  `/tmp/opencode/llm-web/logs/`:
  - `llama.log` para `llama-server`.
  - `api.log` para la API.
- Los archivos PID se guardan en `/tmp/opencode/llm-web/pids/`; sirven a
  `./llm stop` para detener `llama-server` y la API.
