#!/usr/bin/env python3
"""API OpenAI-compatible para el agente llm-web."""

import json
import os
import re
import sys
import time
import uuid
from typing import List, Optional
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool


# ---------------------------------------------------------------------------
# Configuración del backend de llama.cpp.
# La API lee LLAMA_URL; agent.py lee LLAMA_BASE_URL, así que sincronizamos
# la variable de entorno antes de importar el módulo del agente.
# ---------------------------------------------------------------------------
LLAMA_URL = os.environ.get(
    "LLAMA_URL",
    "http://127.0.0.1:8080",
)
os.environ["LLAMA_BASE_URL"] = LLAMA_URL

# Añadir agent/ a sys.path para poder importar agent.py como módulo.
AGENT_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "agent",
)
sys.path.insert(0, os.path.abspath(AGENT_DIR))

import agent  # noqa: E402


app = FastAPI(title="llm-web API")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Message]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


def build_messages(incoming: List[Message]) -> List[dict]:
    """Construye la lista de mensajes para el agente.

    Mantiene SYSTEM_PROMPT como base e inyecta al final cualquier mensaje
    system que envíe el cliente, para no perder las reglas de fuentes.
    """

    user_system = [
        m for m in incoming if m.role == "system"
    ]
    others = [
        m for m in incoming if m.role != "system"
    ]

    system_content = agent.SYSTEM_PROMPT

    if user_system:
        system_content += "\n\n" + "\n\n".join(
            m.content for m in user_system
        )

    return [
        {
            "role": "system",
            "content": system_content,
        },
    ] + [
        {
            "role": m.role,
            "content": m.content,
        }
        for m in others
    ]


def openai_response(answer: str, model: Optional[str] = None) -> dict:
    """Formatea la respuesta del agente como chat.completion de OpenAI."""

    if model is None:
        model = agent.MODEL

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": answer,
                },
                "finish_reason": "stop",
            }
        ],
    }


async def stream_answer(messages: List[dict]):
    """Genera eventos SSE con la respuesta del agente."""

    answer = await run_in_threadpool(
        agent.run_agent_conversation,
        messages,
    )

    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    model = agent.MODEL

    # Primer chunk: rol del asistente.
    yield (
        "data: "
        + json.dumps(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant"},
                        "finish_reason": None,
                    }
                ],
            }
        )
        + "\n\n"
    )

    # Contenido palabra a palabra (preservando espacios).
    tokens = re.findall(r"\S+|\s+", answer)
    for token in tokens:
        yield (
            "data: "
            + json.dumps(
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": token},
                            "finish_reason": None,
                        }
                    ],
                }
            )
            + "\n\n"
        )

    yield "data: [DONE]\n\n"


@app.get("/v1/models")
def list_models():
    """Proxy de la lista de modelos de llama-server."""

    try:
        request = Request(
            f"{LLAMA_URL}/v1/models",
            headers={"Accept": "application/json"},
        )

        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        return data

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo contactar con llama-server: {exc}",
        )


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """Endpoint compatible con OpenAI Chat Completions."""

    messages = build_messages(request.messages)

    if request.stream:
        return StreamingResponse(
            stream_answer(messages),
            media_type="text/event-stream",
        )

    answer = await run_in_threadpool(
        agent.run_agent_conversation,
        messages,
    )

    return JSONResponse(openai_response(answer))


if __name__ == "__main__":
    import uvicorn

    API_HOST = os.environ.get("API_HOST", "127.0.0.1")
    API_PORT = int(os.environ.get("API_PORT", "8090"))

    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
    )
