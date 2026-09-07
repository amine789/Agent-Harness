"""Web search tool, backed by Firecrawl (api.firecrawl.dev).

Kept as its own dedicated tool rather than routed through `bash` — the
sandbox's `bash` tool runs with `--network none`, so this is the only
tool in the harness with network access, scoped to exactly one API.
"""

import os
import requests
from harness.tools.registry import tool

FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
REQUEST_TIMEOUT = 10  # seconds
MAX_RESULTS = 5
MAX_DESCRIPTION_CHARS = 500


@tool
def search_web(query: str) -> str:
    """Search the web for a query. Returns the title, url, and description
    of the top results. Use this for current information, documentation,
    or research not covered by existing project files."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return "[error] FIRECRAWL_API_KEY is not set."

    try:
        response = requests.post(
            FIRECRAWL_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query, "limit": MAX_RESULTS},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        return f"[error] web search request failed: {type(e).__name__}: {e}"

    if response.status_code != 200:
        return f"[error] web search failed: HTTP {response.status_code} — {response.text}"

    body = response.json()
    if not body.get("success"):
        return f"[error] web search failed: {body}"

    results = body.get("data", {}).get("web", [])
    if not results:
        return f"no results found for: {query}"

    lines = []
    for r in results[:MAX_RESULTS]:
        description = r.get("description", "")[:MAX_DESCRIPTION_CHARS]
        lines.append(f"{r.get('title', '(no title)')}\n{r.get('url', '')}\n{description}")
    return "\n\n".join(lines)
