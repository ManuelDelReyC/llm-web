#!/usr/bin/env python3
"""Servidor MCP que expone la herramienta web_search."""

import json
import os
import sys


# Añadir la raíz del repo a sys.path para poder importar agent.web_search.
REPO_ROOT = os.path.join(
    os.path.dirname(__file__),
    "..",
)
sys.path.insert(0, os.path.abspath(REPO_ROOT))

from agent.web_search import search  # noqa: E402
from mcp.server import MCPServer, MCPTool  # noqa: E402


def handle_web_search(arguments: dict) -> list[dict]:
    """Ejecuta una búsqueda web y devuelve los resultados."""

    query = arguments.get("query", "").strip()

    if not query:
        raise ValueError("El parámetro 'query' es obligatorio.")

    return search(query)


def main():
    server = MCPServer(
        "llm-web-web-search",
        [
            MCPTool(
                name="web_search",
                description=(
                    "Busca información actual o externa en la web usando "
                    "SearXNG. Devuelve una lista de resultados con título, "
                    "URL y resumen."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Consulta de búsqueda",
                        }
                    },
                    "required": ["query"],
                },
                handler=handle_web_search,
            )
        ],
    )

    server.run()


if __name__ == "__main__":
    main()
