"""Embeddings using FastEmbed (lightweight, ONNX-based, no PyTorch)."""
import warnings
warnings.filterwarnings("ignore", message=".*DefaultEmbedding.*deprecated.*")

from typing import List
from fastembed import TextEmbedding
from utils.app_logging import get_logger

logger = get_logger(__name__)

# FastEmbed supported models:
# BAAI/bge-small-en-v1.5: 384 dims, 67MB, fast - best for 2GB server
# BAAI/bge-base-en-v1.5: 768 dims, 210MB, better quality - needs 4GB+
# BAAI/bge-large-en-v1.5: 1024 dims, 1.2GB, best quality - needs 8GB+
MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384
_model = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL}")
        _model = TextEmbedding(model_name=MODEL)
    return _model


def embed(text: str) -> List[float]:
    """Embed single text."""
    embeddings = list(_get_model().embed([text]))
    return embeddings[0].tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed batch."""
    embeddings = list(_get_model().embed(texts))
    return [e.tolist() for e in embeddings]
