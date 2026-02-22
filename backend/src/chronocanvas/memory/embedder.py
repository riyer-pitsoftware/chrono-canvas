import asyncio
import logging

logger = logging.getLogger(__name__)

_model = None
_model_lock = asyncio.Lock()


async def get_embedder(model_name: str = "all-MiniLM-L6-v2"):
    """Get or load the embedding model (lazy load)."""
    global _model
    if _model is None:
        async with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {model_name}")
                loop = asyncio.get_event_loop()
                _model = await loop.run_in_executor(
                    None, lambda: SentenceTransformer(model_name)
                )
                logger.info(f"Embedding model loaded: {model_name}")
    return _model


async def embed_text(text: str, model_name: str = "all-MiniLM-L6-v2") -> list[float]:
    """Embed text using sentence-transformers (async)."""
    model = await get_embedder(model_name)
    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None, lambda: model.encode(text, convert_to_numpy=False)
    )
    return embedding.tolist()
