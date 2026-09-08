#!/usr/bin/env python3

import json
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SEARXNG_URL = "http://127.0.0.1:8081/search"

MAX_RESULTS = 5
MAX_TITLE_LENGTH = 200
MAX_SNIPPET_LENGTH = 500


def search(query: str) -> list[dict]:
    """
    Busca en SearXNG y devuelve una lista compacta de resultados.
    """

    params = urlencode({
        "q": query,
        "format": "json",
        "language": "all",
    })

    url = f"{SEARXNG_URL}?{params}"

    request = Request(
        url,
        headers={
            "User-Agent": "llm-web-agent/0.1",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        data = json.load(response)

    results = []

    for result in data.get("results", [])[:MAX_RESULTS]:
        title = result.get("title", "").strip()
        result_url = result.get("url", "").strip()
        snippet = result.get("content", "").strip()

        if not result_url:
            continue

        results.append({
            "title": title[:MAX_TITLE_LENGTH],
            "url": result_url,
            "snippet": snippet[:MAX_SNIPPET_LENGTH],
        })

    return results


def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} \"consulta\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:]).strip()

    try:
        results = search(query)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    except Exception as e:
        error = {
            "error": str(e)
        }
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()