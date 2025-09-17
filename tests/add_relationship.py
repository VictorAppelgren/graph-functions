# Minimal test for add_relationship
import sys
import os

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import random
from src.graph.ops.topic import get_all_topics
from src.graph.ops.link import find_influences_and_correlates
from utils import app_logging
from typing import cast

logger = app_logging.get_logger(__name__)


def test_relationship_finder() -> None:
    topics = get_all_topics()
    if not topics:
        logger.error("No topics found in the graph!")
        return
    topic = random.choice(topics)
    topic_id = cast(str, topic.get("id"))
    logger.info(f"Picked topic: {topic_id}")
    result = find_influences_and_correlates(topic_id, test=False)
    logger.info(f"[test_relationship_finder] Results for topic {topic_id}: {result}")


if __name__ == "__main__":
    test_relationship_finder()
