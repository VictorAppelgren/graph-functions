# Minimal test for add_node
import os
import sys
import json
import random

# Ensure project root (V1) is on sys.path when running from tests/
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.load_article import load_article
from graph_nodes.add_node import add_node
from utils import minimal_logging
from paths import get_raw_news_dir

logger = minimal_logging.get_logger(__name__)

def test_add_node():
    raw_base = get_raw_news_dir()  # base raw_news directory
    raw_base_str = str(raw_base)
    logger.info(f"Raw news base directory: {raw_base_str}")
    # List all day subdirectories (YYYY-MM-DD), try newest to oldest until one has JSONs
    day_dirs = [d for d in os.listdir(raw_base_str) if os.path.isdir(os.path.join(raw_base_str, d))]
    logger.info(f"Found day directories: {day_dirs}")
    if not day_dirs:
        raise FileNotFoundError(f"No day folders found in {raw_base_str}")
    for day in sorted(day_dirs, reverse=True):
        logger.info(f"Trying day folder: {day}")
        day_folder = os.path.join(raw_base_str, day)
        article_files = [f for f in os.listdir(day_folder) if f.endswith('.json')]
        logger.info(f"Article JSON files in {day_folder}: {len(article_files)}")
        if article_files:
            article_file = random.choice(article_files)
            logger.info(f"Randomly selected article file: {article_file}")
            article_path = os.path.join(day_folder, article_file)
            logger.info(f"Full article path: {article_path}")
            article_id = article_file.split('.')[0]
            logger.info(f"Full article id: {article_id}")
            break
    else:
        raise FileNotFoundError(f"No article JSONs found in any day folder under {raw_base_str}")
    logger.info(f'Picked article: {article_path}')
    article = load_article(article_id)
    # Normalize structure if stored under top-level 'data'
    if isinstance(article, dict) and isinstance(article.get('data'), dict):
        article = article['data']
    # Minimal preview log: title and truncated summary/description
    title = article.get('title', '[no title]')
    summary = article['argos_summary']
    logger.info(f"Article preview: title='{title}', summary='{summary[:120]}{'...' if len(summary) > 120 else ''}")
    article_id = article.get('argos_id') or article.get('id')
    if not article_id:
        raise ValueError(f'No argos_id or id found in article file {article_path}!')
    result = add_node(article_id)
    print("[test_add_node] Result:", result)

if __name__ == "__main__":
    test_add_node()
