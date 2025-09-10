# file: tests/manual_should_rewrite_smoke.py (do NOT add to repo if you prefer; you can just run it once)

import sys, os, random

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils import app_logging
from src.graph.neo4j_client import run_cypher
from src.analysis.orchestration.should_rewrite import should_rewrite

logger = app_logging.get_logger(__name__)

def main():
    TOPIC_NAME = os.environ.get("ASSET", "EURUSD")  # override with ASSET env if you like
    SAMPLE_LIMIT = int(os.environ.get("SAMPLE_LIMIT", "15"))

    # Resolve topic_id
    t = run_cypher("MATCH (t:Topic {name:$name}) RETURN t.id AS id", {"name": TOPIC_NAME})
    assert t and t[0]["id"], f"Topic not found: {TOPIC_NAME}"
    topic_id = t[0]["id"]
    logger.info(f"Topic resolved: {TOPIC_NAME} -> {topic_id}")

    # Get recent article candidates
    arts = run_cypher("""
MATCH (a:Article)-[:ABOUT]->(t:Topic {id:$topic_id})
RETURN a.id AS id, a.publishedAt AS ts
ORDER BY ts DESC
LIMIT $lim
""", {"topic_id": topic_id, "lim": SAMPLE_LIMIT})

    ids = [row["id"] for row in arts if row.get("id")]
    assert ids, f"No articles found for topic_id={topic_id}"
    random.shuffle(ids)

    # Try should_rewrite on a few recent ones until one returns True
    triggered = False
    for aid in ids:
        logger.info(f"Testing should_rewrite for topic={topic_id}, article={aid}")
        res = should_rewrite(topic_id, aid, test=False)  # returns dict: {'should_rewrite': bool, 'motivation': str, 'section': str}
        logger.info(f"Result: {res}")
        if res["should_rewrite"] is True:
            logger.info(f"Rewrite should have been triggered for section={res['section']} on topic={topic_id}")
            triggered = True
            break

    if not triggered:
        logger.info("No rewrite was triggered in this sample. Increase SAMPLE_LIMIT or try a different ASSET.")

if __name__ == "__main__":
    main()