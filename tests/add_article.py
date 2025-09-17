# Minimal test for add_article
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import sys

sys.path.insert(0, "..")

import json
import random
from src.articles.ingest_article import add_article
from utils import app_logging

logger = app_logging.get_logger(__name__)


def find_latest_day_folder(base_dir) -> int | None:
    days = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    return max(days) if days else None


def pick_random_article_json(day_folder) -> str | None:
    files = [f for f in os.listdir(day_folder) if f.endswith(".json")]
    return random.choice(files) if files else None


def test_add_article(article_id: str = ""):
    # If an ID is provided, use it directly; else pick a random article from latest day
    if article_id:
        result = add_article(article_id, test=True)
        print("[test_add_article] Result:", result)
        return

    base_dir = os.path.join(os.path.dirname(__file__), "../data/raw_news")
    base_dir = os.path.abspath(base_dir)
    day = find_latest_day_folder(base_dir)
    if not day:
        logger.error("No day folders found in raw_news!")
        return
    day_folder = os.path.join(base_dir, str(day))
    article_file = pick_random_article_json(day_folder)
    if not article_file:
        logger.error(f"No article JSONs found in {day_folder}!")
        return
    article_path = os.path.join(day_folder, article_file)
    logger.info(f"Picked article: {article_path}")

    with open(article_path, "r") as f:
        article = json.load(f)

    # Minimal preview log: title and truncated summary/description
    title = article.get("title", "[no title]")
    summary = article.get("summary") or article.get("description") or ""
    logger.info(
        f"Article preview: title='{title}', summary='{summary[:120]}{'...' if len(summary) > 120 else ''}"
    )
    picked_id = article.get("argos_id") or article.get("id")
    if not picked_id:
        logger.error(f"No argos_id or id found in article file {article_path}!")
        return

    result = add_article(picked_id, test=True)
    print("[test_add_article] Result:", result)


if __name__ == "__main__":
    test_add_article("1N8X6GTA2")
    # test_add_article()
