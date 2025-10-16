import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils import app_logging
from typing import cast
from src.graph.ops.topic import get_all_topics, remove_topic

logger = app_logging.get_logger(__name__)

ASSET = "Taylor Swift: The Life of a Showgirl"


def test_remove_topic() -> None:
    all_topics = get_all_topics()
    topic_to_remove = None
    if ASSET:
        for topic in all_topics:
            if topic.get("name") == ASSET:
                topic_to_remove = topic
                break
    if not topic_to_remove:
        for topic in all_topics:
            imp = topic.get("importance")
            try:
                imp_int = int(imp) if imp is not None else None
            except (ValueError, TypeError):
                imp_int = None
            if imp_int == 5:
                topic_to_remove = topic
                break
    if not topic_to_remove:
        logger.warning("No removable topic found (ASSET or importance==5)")
        return
    topic_id = cast(str, topic_to_remove.get("id"))
    logger.info(f"Removing topic: {topic_to_remove.get('name')} (id={topic_id})")
    result = remove_topic(topic_id, reason="cleanup test path")
    print(
        f"[test_remove_topic] Removed: {topic_to_remove.get('name')} (id={topic_id}) Result: {result}"
    )


if __name__ == "__main__":
    test_remove_topic()
