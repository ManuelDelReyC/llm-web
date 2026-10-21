#!/usr/bin/env python3

import json
import os
import sys
from urllib.request import Request, urlopen

from fetch_url import fetch
from web_search import search


LLAMA_BASE_URL = os.environ.get(
    "LLAMA_BASE_URL",
    "http://127.0.0.1:8080",
)
LLAMA_URL = f"{LLAMA_BASE_URL}/v1/chat/completions"
LLAMA_MODELS_URL = f"{LLAMA_BASE_URL}/v1/models"

# Respaldo por si el servidor no informa ningún modelo.
# llama-server sirve siempre el GGUF que tenga cargado
# e ignora este campo, así que es solo cosmético.
DEFAULT_MODEL = "local-model"

# Se rellena en tiempo de ejecución con el modelo que
# llama-server tiene cargado (ver get_model_name).
MODEL = DEFAULT_MODEL

MAX_ITERATIONS = 3


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
    "7. Cuando el usuario pregunte por información actual, reciente, "
    "última o vigente, no elijas automáticamente una página histórica "
    "de una versión anterior. Busca y verifica una fuente que indique "
    "explícitamente el estado actual o la versión más reciente.\n"

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


def get_model_name() -> str:
    """Pregunta a llama-server qué modelo tiene cargado."""

    debug("→ llama-server | consultando modelo cargado")

    try:
        request = Request(LLAMA_MODELS_URL)

        with urlopen(request, timeout=10) as response:
            data = json.load(response)

        models = data.get("data", [])

        if models:

            model_id = models[0].get("id")

            if model_id:
                debug(f"Modelo cargado: {model_id}")
                return model_id

    except Exception as e:
        debug(f"No se pudo consultar el modelo: {e}")

    debug(f"Usando modelo por defecto: {DEFAULT_MODEL}")

    return DEFAULT_MODEL


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
    """Extrae una llamada de herramienta desde la respuesta del modelo."""

    if not content:
        return None

    text = content.strip()

    debug(
        "Buscando tool call en contenido:\n"
        f"{text}"
    )

    # ---------------------------------------------------------
    # 1. Intentar interpretar todo el contenido como JSON.
    # ---------------------------------------------------------
    try:
        data = json.loads(text)

        if isinstance(data, dict):
            name = data.get("name")
            arguments = data.get("arguments")

            if name in ("web_search", "fetch_url"):
                if not isinstance(arguments, dict):
                    arguments = {}

                debug(
                    "JSON detectado | "
                    f"name={name} | arguments={arguments}"
                )

                return {
                    "name": name,
                    "arguments": arguments,
                }

    except json.JSONDecodeError:
        pass

    # ---------------------------------------------------------
    # 2. Buscar un objeto JSON dentro de texto adicional.
    #
    # Ejemplo:
    #
    #   Entendido...
    #   {"name":"web_search","arguments":{"query":"Python"}}
    # ---------------------------------------------------------
    decoder = json.JSONDecoder()

    for index, char in enumerate(text):
        if char != "{":
            continue

        candidate = text[index:]

        try:
            data, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict):
            continue

        name = data.get("name")
        arguments = data.get("arguments")

        if name not in ("web_search", "fetch_url"):
            continue

        if not isinstance(arguments, dict):
            arguments = {}

        debug(
            "JSON encontrado dentro de texto | "
            f"name={name} | arguments={arguments}"
        )

        return {
            "name": name,
            "arguments": arguments,
        }

    # ---------------------------------------------------------
    # 3. No se encontró ninguna llamada.
    # ---------------------------------------------------------
    debug("No se detectó ninguna llamada de herramienta.")

    return None


def run_web_search(query: str) -> list | dict:
    """Ejecuta la búsqueda web llamando a search() directamente."""

    debug(
        f"→ web_search | query={query!r}"
    )

    try:
        data = search(query)

    except Exception as e:
        debug(
            f"← web_search | ERROR={e}"
        )

        return {
            "error": f"No se pudo ejecutar web_search: {e}"
        }

    debug(
        f"← web_search | resultados={len(data)}"
    )

    return data


def run_fetch_url(url: str) -> dict:
    """Descarga una página llamando a fetch() directamente."""

    debug(
        f"→ fetch_url | url={url!r}"
    )

    try:
        data = fetch(url)

    except Exception as e:
        debug(
            f"← fetch_url | ERROR={e}"
        )

        return {
            "error": (
                "No se pudo ejecutar fetch_url: "
                f"{e}"
            ),
            "url": url,
        }

    debug(
        "← fetch_url | "
        f"OK | contenido={len(data.get('content', ''))} caracteres"
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

    url = page.get("url", "")
    content_type = page.get("content_type", "")
    content = page.get("content", "")

    if not content:
        return (
            "La página se descargó correctamente, "
            "pero no contiene texto legible."
        )

    return (
        "=== CONTENIDO LEÍDO DIRECTAMENTE DE LA PÁGINA ===\n\n"
        f"URL: {url}\n"
        f"Tipo: {content_type}\n\n"
        f"{content}\n\n"
        "=== FIN DEL CONTENIDO DE LA PÁGINA ==="
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


def run_agent_conversation(messages: list[dict]) -> str:
    """Ejecuta el bucle agente sobre una lista de mensajes ya formada."""

    global MODEL

    MODEL = get_model_name()

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
                    "=== RESULTADOS DE BÚSQUEDA ===\n\n"
                    f"{result_text}\n\n"
                    "=== FIN DE RESULTADOS DE BÚSQUEDA ===\n\n"

                    "Los resultados anteriores son pistas de búsqueda. "
                    "No los trates como contenido completo de las páginas.\n\n"

                    "Analiza la pregunta original y selecciona la fuente "
                    "más adecuada para responder.\n\n"

                    "Si necesitas datos concretos, actuales o verificables, "
                    "utiliza fetch_url para leer una página relevante, "
                    "preferentemente una fuente oficial o primaria.\n\n"

                    "Cuando el usuario pregunte por una versión concreta "
                    "de un programa, prefiere una página oficial específica "
                    "de esa versión cuando esté disponible.\n\n"

                    "Distingue entre la versión de la documentación y la "
                    "versión del programa descrito. Una ruta genérica de "
                    "documentación no implica que la página describa la "
                    "versión más reciente del programa.\n\n"

                    "Si la pregunta pide información actual, comprueba "
                    "que la fuente permite determinar el estado actual. "
                    "No elijas automáticamente una página histórica "
                    "cuando se pregunta por la versión vigente.\n\n"

                    "Si los resultados contienen varias versiones, "
                    "selecciona la fuente que permita identificar "
                    "claramente la versión pertinente.\n\n"

                    "No inventes datos ni deduzcas que una fuente oficial "
                    "contiene errores sin evidencias concretas.\n\n"

                    "No vuelvas a utilizar web_search para la misma "
                    "pregunta. Si necesitas verificar información "
                    "concreta, utiliza fetch_url."
                )

            else:

                instruction = (
                    f"{result_text}\n\n"

                    "Has leído directamente el contenido de la página "
                    "indicada. Utiliza ese contenido como fuente principal "
                    "para responder a la pregunta original.\n\n"

                    "Distingue entre los hechos que aparecen explícitamente "
                    "en la página y tus propias inferencias.\n\n"

                    "Si el usuario pregunta por una versión concreta, "
                    "comprueba que el contenido leído se refiere a esa "
                    "versión. No deduzcas la versión del programa "
                    "únicamente a partir de la URL o de la versión general "
                    "de la documentación.\n\n"

                    "No añadas datos que no estén respaldados por la "
                    "información proporcionada. No afirmes que una página "
                    "contiene errores sin pruebas explícitas.\n\n"

                    "Si el contenido no permite responder con certeza, "
                    "indícalo explícitamente."
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

    return run_agent_conversation(messages)


def interactive_mode():
    """Bucle interactivo que mantiene el historial de conversación."""

    global DEBUG

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
    ]

    print(
        "🤖 Agente listo. Escribe tu pregunta o uno de estos comandos:"
    )
    print("  /quit, /salir  → cerrar")
    print("  /debug         → alternar traza detallada")
    print("  /clear         → borrar el historial")
    print("")

    while True:

        try:
            user_input = input("> ").strip()
        except (
            EOFError,
            KeyboardInterrupt,
        ):
            print()
            break

        if not user_input:
            continue

        command = user_input.lower()

        if command in (
            "/quit",
            "/salir",
            "/exit",
        ):
            break

        if command == "/debug":
            DEBUG = not DEBUG
            print(
                f"DEBUG={'activado' if DEBUG else 'desactivado'}"
            )
            continue

        if command == "/clear":
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
            ]
            print("Historial borrado.")
            continue

        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        answer = run_agent_conversation(messages)

        print(answer)
        print("")

        messages.append(
            {
                "role": "assistant",
                "content": answer,
            }
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
        interactive_mode()
        return

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