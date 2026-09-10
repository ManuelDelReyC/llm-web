#!/usr/bin/env python3

import gzip
import json
import re
import sys
from html import unescape
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


MAX_CONTENT_LENGTH = 12000


def html_to_text(html: str) -> str:
    """Convierte HTML básico en texto legible."""

    # Eliminar scripts, estilos y contenido no visible.
    html = re.sub(
        r"<(script|style|noscript).*?>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Saltos de línea para elementos de bloque.
    html = re.sub(
        r"</(p|div|section|article|main|li|h[1-6]|tr|br)>",
        "\n",
        html,
        flags=re.IGNORECASE,
    )

    # Eliminar etiquetas HTML.
    text = re.sub(r"<[^>]+>", " ", html)

    # Decodificar entidades HTML.
    text = unescape(text)

    # Normalizar espacios.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def decompress_content(raw: bytes, content_encoding: str) -> bytes:
    """Descomprime contenido HTTP si el servidor lo devuelve comprimido."""

    encoding = content_encoding.lower().strip()

    if encoding == "gzip":
        return gzip.decompress(raw)

    # De momento no añadimos Brotli como dependencia externa.
    if encoding == "br":
        raise ValueError(
            "La página utiliza Brotli (br). "
            "Esta primera versión no tiene soporte Brotli."
        )

    return raw


def fetch(url: str) -> dict:
    """Descarga una URL y devuelve texto limpio."""

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            "Solo se permiten URLs http:// o https://"
        )

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5"
            ),
            "Accept-Encoding": "gzip",
        },
    )

    with urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "")
        content_encoding = response.headers.get(
            "Content-Encoding", ""
        )
        charset = response.headers.get_content_charset() or "utf-8"

        raw = response.read()

        final_url = response.geturl()

    # Descomprimir si procede.
    raw = decompress_content(raw, content_encoding)

    # Comprobar el tipo de contenido.
    if not (
        "text/html" in content_type
        or "application/xhtml+xml" in content_type
        or "text/plain" in content_type
    ):
        raise ValueError(
            f"Tipo de contenido no compatible: {content_type}"
        )

    text = raw.decode(charset, errors="replace")

    if (
        "text/html" in content_type
        or "application/xhtml+xml" in content_type
    ):
        text = html_to_text(text)
    else:
        text = text.strip()

    # Limitar el contenido para proteger el contexto del LLM.
    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH]
        text += "\n\n[Contenido truncado]"

    return {
        "url": final_url,
        "content_type": content_type,
        "content": text,
    }


def main():
    if len(sys.argv) != 2:
        print(
            f'Uso: {sys.argv[0]} "https://ejemplo.com"',
            file=sys.stderr,
        )
        sys.exit(1)

    url = sys.argv[1]

    try:
        result = fetch(url)

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

    except HTTPError as e:
        print(
            json.dumps(
                {
                    "error": f"HTTP {e.code}: {e.reason}",
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    except URLError as e:
        print(
            json.dumps(
                {
                    "error": f"No se pudo acceder a la URL: {e.reason}",
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    except Exception as e:
        print(
            json.dumps(
                {
                    "error": str(e),
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()