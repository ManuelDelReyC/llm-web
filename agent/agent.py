#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from urllib.request import Request, urlopen


LLAMA_URL = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "qwen2.5-coder-7b-instruct"

MAX_ITERATIONS = 3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WEB_SEARCH_SCRIPT = os.path.join(
    BASE_DIR,
    "web_search.py",
)

FETCH_URL_SCRIPT = os.path.join(
    BASE_DIR,
    "fetch_url.py",
)


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
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Fetch and read the text content of a web page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The HTTP or HTTPS URL to fetch",
                    }
                },
                "required": ["url"],
            },
        },
    },
]


SYSTEM_PROMPT = (
    "Eres un asistente útil y preciso. "
    "Responde en español salvo que el usuario indique lo contrario.\n\n"

    "Cuando necesites información actual o externa, utiliza la herramienta "
    "web_search.\n"

    "Cuando necesites comprobar información o leer una página web " 
    "concreta, utiliza fetch_url.\n\n"    

    "REGLAS SOBRE FUENTES:\n" 
    "1. Los resultados de web_search son pistas y no deben tratarse " 
    "como una fuente primaria completa.\n" 
    "2. Cuando una respuesta dependa de información concreta de una " 
    "página, utiliza fetch_url para leer esa página.\n" 
    "3. Da prioridad a fuentes oficiales, documentación técnica y " 
    "fuentes primarias cuando estén disponibles.\n" 
    "4. No inventes datos que no aparezcan en la información " 
    "proporcionada por las herramientas.\n" 
    "5. Si la información encontrada es contradictoria o insuficiente, " 
    "indícalo en lugar de inventar una respuesta.\n" 
    "6. Distingue entre información obtenida de un snippet de búsqueda " 
    "y contenido leído directamente de una página.\n\n"

    "LLAMADAS DE HERRAMIENTA:\n" 
    "Las llamadas deben ser un objeto JSON con esta estructura:\n" 
    '{"name":"web_search","arguments":{"query":"texto"}}\n' 
    "o:\n" 
    '{"name":"fetch_url","arguments":{"url":"https://ejemplo.com"}}\n\n'

    "No escribas Markdown alrededor de la llamada de herramienta. "
    "No escribas explicaciones junto a la llamada."
)


DEBUG = False


def debug(message: str):
    """Muestra mensajes de depuración si DEBUG está activado."""

    if DEBUG:
        print(
            f"[DEBUG] {message}",
            file=sys.stderr,
        )


def call_llm(messages: list[dict]) -> dict:
    """Envía los mensajes al servidor llama.cpp."""

    debug(
        f"→ llama-server | mensajes={len(messages)}"
    )

    payload = {
        "model": MODEL,
        "messages": messages,
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

    with urlopen(request, timeout=300) as response:
        result = json.load(response)

    debug("← llama-server")

    return result


def extract_tool_call(content: str):
    """
    Detecta una llamada de herramienta generada por el modelo.

    Acepta JSON puro y JSON dentro de un bloque Markdown.
    """

    if not content:
        return None

    text = content.strip()

    debug(
        "Contenido recibido del modelo:"
    )
    debug(
        repr(text)
    )

    candidates = [text]

    # JSON dentro de ```json ... ```
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()

        if len(lines) >= 3:
            candidates.append(
                "\n".join(lines[1:-1]).strip()
            )

    for candidate in candidates:

        try:
            data = json.loads(candidate)

        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict):
            continue

        name = data.get("name")
        arguments = data.get("arguments")

        debug(
            f"JSON detectado | name={name} | arguments={arguments}"
        )

        if name not in (
            "web_search",
            "fetch_url",
        ):
            continue

        if not isinstance(arguments, dict):
            continue

        if name == "web_search":

            query = arguments.get("query")

            if not isinstance(query, str):
                continue

            query = query.strip()

            if not query:
                continue

            return name, {
                "query": query,
            }

        if name == "fetch_url":

            url = arguments.get("url")

            if not isinstance(url, str):
                continue

            url = url.strip()

            if not url:
                continue

            return name, {
                "url": url,
            }

    debug(
        "No se detectó ninguna llamada de herramienta."
    )

    return None


def run_web_search(query: str) -> dict:
    """Ejecuta web_search.py."""

    debug(
        f"→ web_search | query={query!r}"
    )

    try:
        result = subprocess.run(
            [
                sys.executable,
                WEB_SEARCH_SCRIPT,
                query,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

    except subprocess.TimeoutExpired:
        debug("← web_search | TIMEOUT")

        return {
            "error": "La búsqueda web superó el tiempo límite."
        }

    except Exception as e:
        debug(
            f"← web_search | ERROR={e}"
        )

        return {
            "error": f"No se pudo ejecutar web_search: {e}"
        }

    if result.returncode != 0:

        error = result.stderr.strip()

        debug(
            f"← web_search | returncode={result.returncode}"
        )

        return {
            "error": (
                "web_search terminó con error."
                + (f" {error}" if error else "")
            )
        }

    try:
        data = json.loads(result.stdout)

    except json.JSONDecodeError as e:

        debug(
            f"← web_search | JSON inválido: {e}"
        )

        return {
            "error": (
                "web_search no devolvió JSON válido: "
                f"{e}"
            )
        }

    if isinstance(data, list):
        debug(
            f"← web_search | resultados={len(data)}"
        )
    else:
        debug(
            "← web_search | resultado recibido"
        )

    return data


def run_fetch_url(url: str) -> dict:
    """Ejecuta fetch_url.py."""

    debug(
        f"→ fetch_url | url={url!r}"
    )

    try:
        result = subprocess.run(
            [
                sys.executable,
                FETCH_URL_SCRIPT,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

    except subprocess.TimeoutExpired:
        debug("← fetch_url | TIMEOUT")

        return {
            "error": "La descarga de la página superó el tiempo límite."
        }

    except Exception as e:
        debug(
            f"← fetch_url | ERROR={e}"
        )

        return {
            "error": f"No se pudo ejecutar fetch_url: {e}"
        }

    if result.returncode != 0:

        debug(
            f"← fetch_url | returncode={result.returncode}"
        )

        # fetch_url.py puede devolver el error como JSON
        # en stdout.
        if result.stdout.strip():

            try:
                data = json.loads(
                    result.stdout
                )

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                pass

        error = result.stderr.strip()

        return {
            "error": (
                "fetch_url terminó con error."
                + (f" {error}" if error else "")
            )
        }

    try:
        data = json.loads(
            result.stdout
        )

    except json.JSONDecodeError as e:

        debug(
            f"← fetch_url | JSON inválido: {e}"
        )

        return {
            "error": (
                "fetch_url no devolvió JSON válido: "
                f"{e}"
            )
        }

    content = ""

    if isinstance(data, dict):
        content = data.get(
            "content",
            "",
        )

    debug(
        "← fetch_url | "
        f"OK | contenido={len(content)} caracteres"
    )

    return data


def format_search_results(results: dict) -> str:
    """Convierte resultados de búsqueda en texto."""

    if isinstance(results, dict) and results.get("error"):

        return (
            "Se produjo un error durante la búsqueda web:\n"
            f"{results['error']}"
        )

    if not isinstance(results, list):

        return (
            "La búsqueda web devolvió un formato inesperado:\n"
            f"{json.dumps(results, ensure_ascii=False)}"
        )

    if not results:
        return "La búsqueda web no encontró resultados."

    lines = [
        "Resultados de búsqueda web:",
        "",
    ]

    for index, result in enumerate(
        results,
        start=1,
    ):

        title = result.get(
            "title",
            "",
        ).strip()

        url = result.get(
            "url",
            "",
        ).strip()

        snippet = result.get(
            "snippet",
            "",
        ).strip()

        lines.append(
            f"[{index}] {title}"
        )

        lines.append(
            f"URL: {url}"
        )

        lines.append(
            f"Resumen: {snippet}"
        )

        lines.append("")

    return "\n".join(lines).strip()


def format_fetched_page(page: dict) -> str:
    """Convierte el resultado de fetch_url en texto."""

    if not isinstance(page, dict):

        return (
            "fetch_url devolvió un formato inesperado:\n"
            f"{json.dumps(page, ensure_ascii=False)}"
        )

    if page.get("error"):

        return (
            "Se produjo un error al leer la página:\n"
            f"{page['error']}"
        )

    url = page.get(
        "url",
        "",
    )

    content_type = page.get(
        "content_type",
        "",
    )

    content = page.get(
        "content",
        "",
    )

    if not content:

        return (
            "La página se descargó correctamente, "
            "pero no contiene texto legible."
        )

    return (
        "Contenido de la página web:\n\n"
        f"URL: {url}\n"
        f"Tipo: {content_type}\n\n"
        f"{content}"
    )


def handle_tool_call(
    name: str,
    arguments: dict,
) -> str:
    """Ejecuta una herramienta."""

    debug(
        f"Ejecutando herramienta: {name}"
    )

    if name == "web_search":

        return format_search_results(
            run_web_search(
                arguments["query"]
            )
        )

    if name == "fetch_url":

        return format_fetched_page(
            run_fetch_url(
                arguments["url"]
            )
        )

    return (
        f"Herramienta desconocida: {name}"
    )


def ask_agent(user_query: str) -> str:
    """Ejecuta el bucle agente → herramienta → agente."""

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_query,
        },
    ]

    debug(
        f"Pregunta: {user_query!r}"
    )

    for iteration in range(
        1,
        MAX_ITERATIONS + 1,
    ):

        debug(
            f"========== ITERACIÓN {iteration}/{MAX_ITERATIONS} =========="
        )

        try:
            response = call_llm(
                messages
            )

        except Exception as e:

            debug(
                f"ERROR llama-server: {e}"
            )

            return (
                "Error al comunicarse con llama-server:\n"
                f"{e}"
            )

        choices = response.get(
            "choices",
            [],
        )

        if not choices:

            debug(
                "llama-server no devolvió choices."
            )

            return (
                "El modelo no devolvió ninguna respuesta."
            )

        message = choices[0].get(
            "message",
            {},
        )

        content = message.get(
            "content"
        ) or ""

        # ---------------------------------------------------------
        # Caso 1: tool_calls estructurados.
        # ---------------------------------------------------------

        tool_calls = message.get(
            "tool_calls"
        )

        if tool_calls:

            debug(
                f"Tool calls estructurados detectados: "
                f"{len(tool_calls)}"
            )

            messages.append(
                message
            )

            for tool_call in tool_calls:

                function = tool_call.get(
                    "function",
                    {},
                )

                name = function.get(
                    "name"
                )

                raw_arguments = function.get(
                    "arguments",
                    "{}",
                )

                debug(
                    f"Tool call estructurado: "
                    f"{name} {raw_arguments}"
                )

                try:
                    arguments = json.loads(
                        raw_arguments
                    )

                except (
                    TypeError,
                    json.JSONDecodeError,
                ):

                    return (
                        "La herramienta recibió argumentos "
                        "JSON inválidos."
                    )

                if name not in (
                    "web_search",
                    "fetch_url",
                ):

                    return (
                        f"El modelo solicitó una herramienta "
                        f"desconocida: {name}"
                    )

                result_text = handle_tool_call(
                    name,
                    arguments,
                )

                tool_message = {
                    "role": "tool",
                    "content": result_text,
                }

                tool_call_id = tool_call.get(
                    "id"
                )

                if tool_call_id:
                    tool_message[
                        "tool_call_id"
                    ] = tool_call_id

                messages.append(
                    tool_message
                )

            continue

        # ---------------------------------------------------------
        # Caso 2: JSON de herramienta dentro de content.
        # ---------------------------------------------------------

        tool_call = extract_tool_call(
            content
        )

        if tool_call:

            name, arguments = tool_call

            debug(
                f"Tool call JSON detectado: "
                f"{name} {arguments}"
            )

            result_text = handle_tool_call(
                name,
                arguments,
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )

            if name == "web_search":

                instruction = (
                    f"{result_text}\n\n"
                    "Utiliza estos resultados para responder "
                    "a la pregunta original. "
                    "Si necesitas verificar o leer una página "
                    "concreta, DEBES utilizar fetch_url con "
                    "una de las URLs encontradas. "
                    "No vuelvas a usar web_search para la "
                    "misma pregunta."
                )

            else:

                instruction = (
                    f"{result_text}\n\n"
                    "Utiliza el contenido de esta página para "
                    "responder a la pregunta original. "
                    "No vuelvas a solicitar fetch_url para "
                    "esta misma URL."
                )

            messages.append(
                {
                    "role": "user",
                    "content": instruction,
                }
            )

            debug(
                f"Resultado de {name} añadido al contexto."
            )

            continue

        # ---------------------------------------------------------
        # Caso 3: respuesta normal.
        # ---------------------------------------------------------

        debug(
            "Respuesta final recibida."
        )

        return content.strip()

    debug(
        "Se alcanzó MAX_ITERATIONS."
    )

    return (
        "El agente alcanzó el número máximo de iteraciones "
        "sin producir una respuesta final."
    )


def main():

    global DEBUG

    args = sys.argv[1:]

    if "--debug" in args:

        DEBUG = True

        args.remove(
            "--debug"
        )

    if not args:

        print(
            f'Uso: {sys.argv[0]} [--debug] "pregunta"',
            file=sys.stderr,
        )

        sys.exit(1)

    user_query = " ".join(
        args
    ).strip()

    if not user_query:

        print(
            "La pregunta no puede estar vacía.",
            file=sys.stderr,
        )

        sys.exit(1)

    answer = ask_agent(
        user_query
    )

    print(answer)


if __name__ == "__main__":
    main()