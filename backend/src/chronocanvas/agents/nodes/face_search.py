import logging
import time
import uuid
from pathlib import Path

import httpx

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings

logger = logging.getLogger(__name__)

SEARCH_QUERY_TEMPLATE = "{figure_name} historical portrait photograph"


async def _search_serpapi(query: str) -> list[dict]:
    """Query SerpAPI Google Images. Returns list of result dicts with 'url' and 'thumbnail'."""
    params = {
        "engine": "google_images",
        "q": query,
        "ijn": "0",
        "api_key": settings.serpapi_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get("https://serpapi.com/search.json", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("images_results", [])
    return [
        {
            "url": r.get("original", ""),
            "thumbnail": r.get("thumbnail", ""),
            "title": r.get("title", ""),
        }
        for r in results
        if r.get("original") or r.get("thumbnail")
    ]


async def _download_image(url: str, output_dir: Path) -> str | None:
    """Download image from URL, save to output_dir, return local path or None on failure."""
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 ChronoCanvas/1.0"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return None
            ext = "jpg" if "jpeg" in content_type or "jpg" in content_type else "png"
            filename = f"face_search_{uuid.uuid4().hex}.{ext}"
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / filename
            filepath.write_bytes(resp.content)
            return str(filepath)
    except Exception as e:
        logger.debug(f"Failed to download image from {url}: {e}")
        return None


async def face_search_node(state: AgentState) -> AgentState:
    figure_name = state.get("figure_name", "")
    trace = list(state.get("agent_trace", []))

    if not figure_name:
        trace.append({"agent": "face_search", "timestamp": time.time(), "skipped": True, "reason": "no_figure_name"})
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    if not settings.serpapi_key:
        logger.info("Face search: SERPAPI_KEY not set, skipping")
        trace.append({"agent": "face_search", "timestamp": time.time(), "skipped": True, "reason": "no_api_key"})
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    # Don't overwrite a manually uploaded face
    if state.get("source_face_path"):
        logger.info("Face search: source_face_path already set, skipping web search")
        trace.append({"agent": "face_search", "timestamp": time.time(), "skipped": True, "reason": "already_set"})
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    query = SEARCH_QUERY_TEMPLATE.format(figure_name=figure_name)
    logger.info(f"Face search: querying SerpAPI for '{query}'")

    try:
        results = await _search_serpapi(query)
    except Exception as e:
        logger.warning(f"Face search: SerpAPI error: {e}")
        trace.append({
            "agent": "face_search",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "search_api_error",
            "error": str(e),
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    if not results:
        logger.info("Face search: no results returned")
        trace.append({
            "agent": "face_search",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "no_results",
            "query": query,
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    request_id = state.get("request_id", "unknown")
    output_dir = Path(settings.output_dir) / request_id

    # Try original URLs first, fall back to thumbnails
    downloaded_path = None
    used_url = None
    for result in results:
        for url in filter(None, [result.get("url"), result.get("thumbnail")]):
            downloaded_path = await _download_image(url, output_dir)
            if downloaded_path:
                used_url = url
                break
        if downloaded_path:
            break

    if not downloaded_path:
        logger.info("Face search: could not download any result images")
        trace.append({
            "agent": "face_search",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "download_failed",
            "query": query,
            "candidates": [r.get("url") for r in results],
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    logger.info(f"Face search: downloaded face image from {used_url} -> {downloaded_path}")
    trace.append({
        "agent": "face_search",
        "timestamp": time.time(),
        "skipped": False,
        "query": query,
        "source_url": used_url,
        "local_path": downloaded_path,
        "candidates_tried": len(results),
    })

    return {
        **state,
        "current_agent": "face_search",
        "source_face_path": downloaded_path,
        "face_search_url": used_url,
        "face_search_query": query,
        "face_search_provider": "serpapi",
        "agent_trace": trace,
    }
