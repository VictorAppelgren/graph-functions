"""OpenAI embeddings. Simple."""
import os
from typing import List
from openai import OpenAI
from utils.app_logging import get_logger

logger = get_logger(__name__)

MODEL = "text-embedding-3-small"
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=api_key)
    return _client


def embed(text: str) -> List[float]:
    """Embed single text."""
    response = _get_client().embeddings.create(input=text, model=MODEL)
    return response.data[0].embedding


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed batch (max 2048)."""
    response = _get_client().embeddings.create(input=texts, model=MODEL)
    return [item.embedding for item in response.data]
