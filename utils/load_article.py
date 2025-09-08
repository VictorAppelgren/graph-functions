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
from utils.logging import get_logger
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta

from paths import get_data_dir, get_raw_news_dir

logger = get_logger(__name__)

def load_article(article_id: str, max_days: int = 30) -> Dict[str, Any]:
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
        logger.debug(f"Trying to load article {article_id} from {article_path}")
        if article_path.exists():
            try:
                with open(article_path, "r") as f:
                    obj = json.load(f)
                logger.debug(f"Loaded article {article_id} from {article_path}")
                if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], dict):
                    return obj["data"]
                return obj
            except Exception as e:
                logger.error(f"Failed to load article {article_id} from {article_path}: {e}")
                continue
        else:
            logger.debug(f"Article {article_id} not found in {article_path}")
    logger.error(f"Article {article_id} not found in any raw_news day directory (checked {max_days} days)")
    raise FileNotFoundError(f"Article {article_id} not found in any raw_news day directory")

if __name__ == "__main__":
    test_id = "5JO4Z4OKV"
    logger.info(f"Testing load_article with id: {test_id}")
    try:
        article = load_article(test_id)
        logger.info("Loaded article: %s", article)
    except Exception as e:
        logger.error(f"Error: {e}")
