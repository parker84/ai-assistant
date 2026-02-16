"""Web search and URL fetching tools using pure.md API."""
import asyncio
from typing import List, Dict, Tuple
from urllib.parse import quote

import httpx
from agno.tools import tool

from src.config import PUREMD_API_KEY
from src.logging_utils import get_logger

logger = get_logger(__name__)

# ---------- Constants ----------
PUREMD_API_URL = "https://pure.md"
MAX_PARALLEL = 5
MAX_QUERIES = 5
MAX_CHARS_PER_RESULT = 4000
TIMEOUT = 10.0
MAX_CONNECTIONS = 20
MAX_KEEPALIVE_CONNECTIONS = 20
HEADERS = {"x-puremd-api-token": PUREMD_API_KEY} if PUREMD_API_KEY else {}

# ---------- Shared HTTP client ----------
_http_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    """Create (once) and reuse a single HTTP/2 AsyncClient."""
    global _http_client
    if _http_client is None:
        async with _client_lock:
            if _http_client is None:
                _http_client = httpx.AsyncClient(
                    http2=True,
                    timeout=httpx.Timeout(TIMEOUT),
                    limits=httpx.Limits(
                        max_connections=MAX_CONNECTIONS,
                        max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
                    ),
                    headers=HEADERS,
                )
    return _http_client


_semaphore = asyncio.Semaphore(MAX_PARALLEL)


# =========================
# Single-item tools
# =========================

@tool
async def fetch_url_contents(url: str = "") -> str:
    """
    Fetch the contents of a single URL as clean markdown text.

    WHEN TO USE:
    - You need to read ONE specific page (product page, article, restaurant listing)
    - You already have the exact URL to fetch
    - If you need MULTIPLE pages, use fetch_urls instead to save time

    ARGS:
    - url (str): The URL to fetch (e.g. "https://example.com/product/123")

    RETURNS:
    - The page content as clean text/markdown, or empty string on error
    """
    logger.info(f"=== FETCH URL: {url} ===")
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        client = await _get_client()
        r = await client.get(f"{PUREMD_API_URL}/{url}")
        if r.status_code == 200:
            return r.text
        logger.warning(f"Fetch failed with status {r.status_code}: {url}")
        return ""
    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        return ""


@tool
async def search_web(query: str = "") -> str:
    """
    Run a single web search query.

    WHEN TO USE:
    - You need to search for ONE thing (a product, restaurant, topic)
    - If you need multiple related queries, use search_web_multi instead

    ARGS:
    - query (str): A clear, specific search term or question

    RETURNS:
    - Search results as text, or empty string on error
    """
    logger.info(f"=== SEARCH WEB: {query} ===")
    if not isinstance(query, str) or not query.strip():
        return ""
    try:
        client = await _get_client()
        r = await client.get(f"{PUREMD_API_URL}/search?q={quote(query)}")
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}")
        return ""


# =========================
# Batch tools
# =========================

@tool
async def fetch_urls(urls: List[str]) -> Dict[str, str]:
    """
    Fetch multiple URLs in parallel. Prefer this over repeated fetch_url_contents calls.

    WHEN TO USE:
    - You need to read several pages (product pages, restaurant listings, reviews)
    - You have a list of candidate URLs from search results
    - Combine with search_web_multi: search first, then fetch the best URLs

    ARGS:
    - urls (List[str]): List of URLs to fetch (max 5 recommended)

    RETURNS:
    - Dict mapping each URL to its page content (empty string if failed)
    """
    logger.info(f"=== FETCH URLS: {len(urls or [])} URLs ===")
    dedup = list(dict.fromkeys(urls or []))[:MAX_QUERIES]
    client = await _get_client()

    async def _fetch_one(u: str) -> Tuple[str, str]:
        if not isinstance(u, str) or not u.strip():
            return (u, "")
        try:
            async with _semaphore:
                r = await client.get(f"{PUREMD_API_URL}/{u}")
            return (u, r.text[:MAX_CHARS_PER_RESULT] if r.status_code == 200 else "")
        except Exception:
            return (u, "")

    results = await asyncio.gather(*[_fetch_one(u) for u in dedup])
    logger.info(f"Fetched {len(dedup)} URLs")
    return {u: text for (u, text) in results}


@tool
async def search_web_multi(queries: List[str]) -> Dict[str, str]:
    """
    Run multiple web search queries in parallel. Prefer this over repeated search_web calls.

    WHEN TO USE:
    - You need several related searches (e.g. product options, restaurant comparisons)
    - You're compiling options and want broad coverage quickly
    - After getting results, use fetch_urls to pull details from the best pages

    ARGS:
    - queries (List[str]): List of search queries (max 5)

    RETURNS:
    - Dict mapping each query to its search results (empty string if failed)
    """
    logger.info(f"=== SEARCH WEB MULTI: {len(queries or [])} queries ===")
    dedup = list(dict.fromkeys(queries or []))[:MAX_QUERIES]
    client = await _get_client()

    async def _search_one(q: str) -> Tuple[str, str]:
        if not isinstance(q, str) or not q.strip():
            return (q, "")
        try:
            async with _semaphore:
                r = await client.get(f"{PUREMD_API_URL}/search?q={quote(q)}")
            r.raise_for_status()
            return (q, r.text[:MAX_CHARS_PER_RESULT])
        except Exception:
            return (q, "")

    results = await asyncio.gather(*[_search_one(q) for q in dedup])
    logger.info(f"Searched {len(dedup)} queries")
    return {q: text for (q, text) in results}
