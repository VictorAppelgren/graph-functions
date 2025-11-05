"""
Loads an article from Backend API by its unique ID.
"""

from utils.app_logging import get_logger
from typing import Dict, Any, cast
from src.api.backend_client import get_article as get_article_from_api

logger = get_logger(__name__)


def load_article(article_id: str, max_days: int = 90) -> Dict[str, str] | None:
    """
    Loads a single article from Backend API by its unique ID.

    Args:
        article_id: Unique article ID
        max_days: Unused (kept for backward compatibility)
    Returns:
        Article data as a dictionary
    Raises:
        FileNotFoundError: If the article cannot be found
    """
    article = get_article_from_api(article_id)
    if article:
        logger.debug("Loaded article %s from Backend API", article_id)
        # Handle legacy wrapper
        inner = article.get("data")
        if isinstance(inner, dict):
            return cast(Dict[str, str], inner)
        return article
    
    logger.error("Article %s not found in Backend API", article_id)
    raise FileNotFoundError(f"Article {article_id} not found")
