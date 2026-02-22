import logging
import time
import uuid
from pathlib import Path

import httpx

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings
from chronocanvas.security import is_safe_url, validate_image_magic

logger = logging.getLogger(__name__)

SEARCH_QUERY_TEMPLATE = "{figure_name} historical portrait photograph"

# Hard cap on downloaded image size (5 MB) to prevent zip-bomb / memory exhaustion
_MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024


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
    if not is_safe_url(url):
        logger.debug(f"Blocked unsafe URL: {url}")
        return None
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
            # Enforce size cap — read up to limit + 1 byte to detect oversize
            data = resp.content
            if len(data) > _MAX_DOWNLOAD_BYTES:
                logger.debug(f"Image too large ({len(data)} bytes) from {url}")
                return None
            if not validate_image_magic(data):
                logger.debug(f"Invalid image magic bytes from {url}")
                return None
            ext = "jpg" if "jpeg" in content_type or "jpg" in content_type else "png"
            filename = f"face_search_{uuid.uuid4().hex}.{ext}"
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / filename
            filepath.write_bytes(data)
            return str(filepath)
    except Exception as e:
        logger.debug(f"Failed to download image from {url}: {e}")
        return None


async def face_search_node(state: AgentState) -> AgentState:
    figure_name = state.get("figure_name", "")
    request_id = state.get("request_id", "unknown")
    trace = list(state.get("agent_trace", []))

    if not figure_name:
        trace.append({
            "agent": "face_search", "timestamp": time.time(),
            "skipped": True, "reason": "no_figure_name",
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    if not settings.serpapi_key:
        logger.info("Face search: SERPAPI_KEY not set, skipping [request_id=%s]", request_id)
        trace.append({
            "agent": "face_search", "timestamp": time.time(),
            "skipped": True, "reason": "no_api_key",
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    # Don't overwrite a manually uploaded face
    if state.get("source_face_path"):
        logger.info(
            "Face search: source_face_path already set, skipping web search [request_id=%s]",
            request_id,
        )
        trace.append({
            "agent": "face_search", "timestamp": time.time(),
            "skipped": True, "reason": "already_set",
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    # Build query list: primary name first, then alternative names as fallbacks
    queries = [SEARCH_QUERY_TEMPLATE.format(figure_name=figure_name)]
    for alt_name in state.get("alternative_names", []):
        alt_query = SEARCH_QUERY_TEMPLATE.format(figure_name=alt_name)
        if alt_query not in queries:
            queries.append(alt_query)

    results = []
    used_query = queries[0]
    for query in queries:
        logger.info("Face search: querying SerpAPI for %r [request_id=%s]", query, request_id)
        try:
            results = await _search_serpapi(query)
        except Exception as e:
            logger.warning("Face search: SerpAPI error [request_id=%s]: %s", request_id, e)
            continue
        if results:
            used_query = query
            break

    if not results:
        logger.info("Face search: no results for any query [request_id=%s]", request_id)
        trace.append({
            "agent": "face_search",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "no_results",
            "queries_tried": queries,
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    query = used_query

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
        logger.info("Face search: could not download any result images [request_id=%s]", request_id)
        trace.append({
            "agent": "face_search",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "download_failed",
            "query": query,
            "candidates": [r.get("url") for r in results],
        })
        return {**state, "current_agent": "face_search", "agent_trace": trace}

    logger.info(
        "Face search: downloaded face image %s -> %s [request_id=%s]",
        used_url, downloaded_path, request_id,
    )
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
