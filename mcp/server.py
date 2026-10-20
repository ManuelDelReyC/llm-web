#!/usr/bin/env python3
"""Esqueleto mínimo de servidor MCP sobre stdio (solo biblioteca estándar).

Soporta el handshake clásico de MCP (initialize / notifications/initialized)
y el intercambio posterior de tools/list y tools/call. Acepta mensajes
newline-delimited (NDJSON) y con encabezado Content-Length para maximizar la
compatibilidad con clientes que usen cualquiera de los dos formatos.
"""

import json
import sys
from typing import Callable


PROTOCOL_VERSION = "2024-11-05"


def send_message(message: dict) -> None:
    """Envía un mensaje JSON-RPC por stdout y hace flush."""

    line = json.dumps(
        message,
        ensure_ascii=False,
    )

    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def read_message() -> dict | None:
    """Lee un mensaje JSON-RPC desde stdin.

    Detecta automáticamente si el cliente usa NDJSON o Content-Length.
    Devuelve None cuando se cierra la entrada.
    """

    raw_header = sys.stdin.readline()

    if not raw_header:
        return None

    header = raw_header.strip()

    # ---------------------------------------------------------
    # Framing tipo LSP: Content-Length + cuerpo JSON.
    # ---------------------------------------------------------
    if header.startswith("Content-Length:"):

        try:
            length = int(
                header.split(":", 1)[1].strip()
            )
        except ValueError:
            return None

        # Consumir la línea en blanco que separa cabecera y cuerpo.
        while True:
            blank = sys.stdin.readline()

            if blank is None:
                return None

            if blank.strip() == "":
                break

        body = sys.stdin.read(length)

        return json.loads(body)

    # ---------------------------------------------------------
    # NDJSON: cada línea es un objeto JSON.
    # ---------------------------------------------------------
    if header:
        return json.loads(header)

    return None


class MCPTool:
    """Descripción y manejador de una herramienta MCP."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable[[dict], object],
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler


class MCPServer:
    """Servidor MCP mínimo sobre stdio."""

    def __init__(self, name: str, tools: list[MCPTool]):
        self.name = name
        self.tools = {tool.name: tool for tool in tools}
        self.initialized = False

    def run(self) -> None:
        """Bucle principal de lectura/respuesta."""

        while True:
            message = read_message()

            if message is None:
                break

            self._handle(message)

    def _handle(self, message: dict) -> None:
        """Dispacha un mensaje JSON-RPC al manejador adecuado."""

        method = message.get("method")
        msg_id = message.get("id")

        if method == "initialize":
            self.initialized = True
            self._send_result(
                msg_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": self.name,
                        "version": "1.0.0",
                    },
                },
            )
            return

        if method == "notifications/initialized":
            # No requiere respuesta.
            return

        if method == "tools/list":
            self._send_result(
                msg_id,
                {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in self.tools.values()
                    ],
                },
            )
            return

        if method == "tools/call":
            self._handle_tool_call(
                msg_id,
                message.get("params", {}),
            )
            return

        self._send_error(
            msg_id,
            -32601,
            f"Método no soportado: {method}",
        )

    def _handle_tool_call(
        self,
        msg_id: str | int | None,
        params: dict,
    ) -> None:
        """Ejecuta la herramienta solicitada y devuelve el resultado."""

        name = params.get("name")
        arguments = params.get("arguments", {})

        tool = self.tools.get(name)

        if tool is None:
            self._send_error(
                msg_id,
                -32602,
                f"Herramienta desconocida: {name}",
            )
            return

        try:
            result = tool.handler(arguments)

        except Exception as exc:
            self._send_result(
                msg_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error ejecutando {name}: {exc}",
                        }
                    ],
                    "isError": True,
                },
            )
            return

        self._send_result(
            msg_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            result,
                            ensure_ascii=False,
                        ),
                    }
                ],
                "isError": False,
            },
        )

    def _send_result(
        self,
        msg_id: str | int | None,
        result: dict,
    ) -> None:
        """Envía una respuesta JSON-RPC con resultado."""

        send_message(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
            }
        )

    def _send_error(
        self,
        msg_id: str | int | None,
        code: int,
        message: str,
    ) -> None:
        """Envía una respuesta JSON-RPC con error."""

        send_message(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": code,
                    "message": message,
                },
        }
        )
