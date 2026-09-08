#!/usr/bin/env python3

import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


LLAMA_URL = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "qwen2.5-coder-7b-instruct"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current or external information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


def ask_llm(user_message: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un asistente útil y preciso. "
                    "Responde en español salvo que el usuario indique "
                    "lo contrario."
                ),
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    data = json.dumps(payload).encode("utf-8")

    request = Request(
        LLAMA_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=300) as response:
            return json.load(response)

    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"llama-server respondió HTTP {e.code}: {error_body}"
        ) from e

    except URLError as e:
        raise RuntimeError(
            f"No se pudo conectar con llama-server: {e.reason}"
        ) from e


def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} \"pregunta\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:]).strip()

    try:
        response = ask_llm(query)

        print(
            json.dumps(
                response,
                ensure_ascii=False,
                indent=2,
            )
        )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()