"""
tools/tavily_tool.py

Thin wrapper around the Tavily Search API.
Returns clean, snippet-truncated results as a formatted string.
"""

import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))

_SNIPPET_LIMIT = 300   # characters per result snippet


def tavily_search(query: str, max_results: int = 5) -> str:
    """
    Search the web via Tavily and return a formatted string of results.

    Args:
        query:       Natural-language search query.
        max_results: How many results to return (default 5).

    Returns:
        Numbered list of  Title / URL / snippet  blocks, or an error string.
    """
    try:
        response = _client.search(query=query, max_results=max_results)
    except Exception as e:
        return f"Tavily search unavailable: {e}"

    results = response.get("results", [])
    if not results:
        return f"No results found for: {query}"

    lines: list[str] = []
    for i, r in enumerate(results, 1):
        title   = r.get("title", "Unknown")
        url     = r.get("url", "")
        snippet = (r.get("content") or "").strip()

        # Trim long snippets cleanly at a word boundary
        if len(snippet) > _SNIPPET_LIMIT:
            snippet = snippet[:_SNIPPET_LIMIT].rsplit(" ", 1)[0] + "…"

        lines.append(f"{i}. **{title}**\n   {url}\n   {snippet}")

    return "\n\n".join(lines)