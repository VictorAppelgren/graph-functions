"""
Loads an article from cold storage by its unique ID.
"""
import sys
import os

# Canonical import pattern to ensure absolute imports work everywhere
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from utils.app_logging import get_logger
from typing import Dict, Any, cast
from datetime import datetime, timedelta
from pathlib import Path

from paths import get_raw_news_dir

logger = get_logger(__name__)

def _load_json_object(path: Path) -> dict[str, Any]:
    """Load JSON and guarantee the top-level is an object (dict)."""
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise TypeError(f"Expected JSON object at top level in {path}, got {type(obj).__name__}")
    return cast(dict[str, Any], obj)

def load_article(article_id: str, max_days: int = 30) -> Dict[str, str] | None:
    """
    Loads a single article from raw news directories by its unique ID.
    Tries today, then yesterday, etc., up to max_days back.
    Handles both flat and nested ('data' key) article formats.

    Args:
        article_id: Unique article ID
        max_days: Number of days to look back (default 30)
    Returns:
        Article data as a dictionary
    Raises:
        FileNotFoundError: If the article cannot be found in any day directory
    """
    today = datetime.now()
    for days_back in range(max_days):
        day = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
        day_dir = get_raw_news_dir(day)
        article_path = day_dir / f"{article_id}.json"
        logger.debug("Trying to load article %s from %s", article_id, article_path)

        if not article_path.exists():
            logger.debug("Article %s not found in %s", article_id, article_path)
            continue

        try:
            obj = _load_json_object(article_path)
            logger.debug("Loaded article %s from %s", article_id, article_path)

            # Handle legacy wrapper
            inner = obj.get("data")
            if isinstance(inner, dict):
                return cast(Dict[str, str], inner)
            return obj  # guaranteed dict[str, Any]

        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Failed to parse %s: %s", article_path, e)
            continue
        except Exception as e:
            logger.exception("Unexpected error reading %s: %s", article_path, e)
            continue

    logger.error(
        "Article %s not found in any raw_news day directory (checked %d days)",
        article_id, max_days,
    )
    raise FileNotFoundError(f"Article {article_id} not found")
