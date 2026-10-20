#!/usr/bin/env python3
"""Servidor MCP que expone la herramienta fetch_url."""

import os
import sys


# Añadir la raíz del repo a sys.path para poder importar agent.fetch_url.
REPO_ROOT = os.path.join(
    os.path.dirname(__file__),
    "..",
)
sys.path.insert(0, os.path.abspath(REPO_ROOT))

from agent.fetch_url import fetch  # noqa: E402
from mcp.server import MCPServer, MCPTool  # noqa: E402


def handle_fetch_url(arguments: dict) -> dict:
    """Descarga una página y devuelve su contenido en texto plano."""

    url = arguments.get("url", "").strip()

    if not url:
        raise ValueError("El parámetro 'url' es obligatorio.")

    return fetch(url)


def main():
    server = MCPServer(
        "llm-web-fetch-url",
        [
            MCPTool(
                name="fetch_url",
                description=(
                    "Descarga una página web y devuelve su contenido textual. "
                    "Útil para leer fuentes concretas una vez conocida la URL."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL http:// o https:// a descargar",
                        }
                    },
                    "required": ["url"],
                },
                handler=handle_fetch_url,
            )
        ],
    )

    server.run()


if __name__ == "__main__":
    main()
