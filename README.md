# llm-web

Agente web local basado en LLM. Un bucle agente en Python (solo biblioteca
estándar, sin dependencias) que consulta un modelo local servido por
[llama.cpp](https://github.com/ggml-org/llama.cpp) y puede buscar en internet
a través de una instancia local de [SearXNG](https://docs.searxng.org/).

## Arquitectura

| Componente | Descripción |
| --- | --- |
| `scripts/start_llm_server_qwen14b.sh` | Arranca `llama-server` con Qwen3-14B en `http://127.0.0.1:8080`. |
| `scripts/start_llm_server_qwen30b.sh` | Arranca `llama-server` con Qwen3-30B-A3B-Q4_K_M y offload automático de capas a GPU/RAM. |
| `searxng/` | SearXNG en Docker Compose, en `http://127.0.0.1:8081` (puerto configurable en `searxng/.env`). |
| `agent/agent.py` | Bucle principal: envía la pregunta al LLM con dos herramientas (`web_search` y `fetch_url`), ejecuta las llamadas y devuelve la respuesta final. |
| `agent/web_search.py` | CLI que busca en SearXNG y devuelve los resultados en JSON. |
| `agent/fetch_url.py` | CLI que descarga una página, la convierte a texto (máx. 12000 caracteres por defecto, configurable con la variable de entorno `MAX_CONTENT_LENGTH`) y devuelve JSON. |

El agente detecta automáticamente el modelo cargado consultando
`/v1/models` del servidor, así que **no hay que editar ningún nombre de
modelo al cambiar de perfil**: cada script selecciona su propio GGUF.

## Requisitos

- Python 3 (solo biblioteca estándar; no hay que instalar nada).
- Docker Compose (para SearXNG).
- llama.cpp compilado y los modelos GGUF en `~/Proyectos/llama/models/`
  (ver las rutas dentro de los scripts de `scripts/`).

## Puesta en marcha

### 1. Servidor LLM

```bash
./scripts/start_llm_server_qwen14b.sh    # [capas_gpu] [contexto], por defecto 99 y 16384
./scripts/start_llm_server_qwen30b.sh    # [capas_gpu] [contexto] [batch], por defecto auto, 8192 y 256
```

### 2. Inicio SearXNG

`cd ~/Proyectos/llm-web/searxng`

`docker compose up -d` (primera vez; para reiniciar: `docker compose restart core`)

`docker compose ps`

`docker compose logs --tail=30 core`

`curl -i http://127.0.0.1:8081/`

`curl -s 'http://127.0.0.1:8081/search?q=Python&format=json' | python3 -m json.tool`

El resultado debería ser JSON con resultados de búsqueda.

### 3. Usar el agente

Con ambos servicios en marcha:

```bash
python3 agent/agent.py "¿Cuál es la última versión estable de Python?"
python3 agent/agent.py --debug "pregunta"   # traza detallada en stderr
```

Las herramientas también funcionan por separado:

```bash
python3 agent/web_search.py "consulta"
python3 agent/fetch_url.py "https://ejemplo.com"
```

## Notas

- La configuración de SearXNG vive en `searxng/core-config/settings.yml`
  (montado en `/etc/searxng/` del contenedor). El formato de respuesta `json`
  debe estar habilitado ahí o las búsquedas del agente fallarán con 403.
  Tras editar el archivo: `docker compose restart core`.
- `Clave.txt` contiene el `secret_key` de SearXNG (el mismo valor aparece en
  `settings.yml`). Es un secreto: si se rota, hay que actualizar ambos sitios.
