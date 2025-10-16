# Minimal test for topic importance LLM helper
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
from src.graph.policies.topic import classify_topic_importance
from utils import app_logging

logger = app_logging.get_logger(__name__)


def test_time_importance() -> None:
    topics = get_all_topics()
    if not topics:
        logger.error("No topics found in the graph!")
        return
    topic = random.choice(topics)
    name = topic.get("name", "")
    ttype = topic.get("type", "")
    context = (
        topic.get("fundamental_analysis", "") or topic.get("medium_analysis", "") or ""
    )
    logger.info(f'Picked topic: {topic.get("id")} | name: {name} | type: {ttype}')
    result = classify_topic_importance(
        topic_name=name, topic_type=ttype, context=context
    )
    logger.info(f'Picked topic: {topic.get("id")} | name: {name} | type: {ttype}')
    logger.info(f"Result for topic {topic.get('id')}: {result}")


if __name__ == "__main__":
    test_time_importance()
