# llm-web

## Inicio SearXNG

`cd ~/Proyectos/llm-web/searxng`

`docker compose restart core`

`docker compose ps`

`docker compose logs --tail=30 core`

`curl -i http://127.0.0.1:8081/`

`curl -s 'http://127.0.0.1:8081/search?q=Python&format=json' | python3 -m json.tool`

El resultado debería ser JSON con resultados de búsqueda.