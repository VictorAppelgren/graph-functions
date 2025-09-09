"""
Remove all Topic nodes whose importance is invalid (not in 1..5).
Super simple, fail-fast script that immediately deletes offending nodes.

Usage:
  python clean_up_scripts/cleanup_invalid_importance_nodes.py
"""
import sys, os

# Ensure project root is on sys.path so 'utils', 'graph_db', etc. import correctly
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils import app_logging
from src.graph.neo4j_client import run_cypher
from src.graph.ops.remove_node import remove_node
from src.observability.pipeline_logging import master_log

logger = app_logging.get_logger(__name__)

VALID_IMPORTANCE = {1, 2, 3, 4, 5}


def fetch_invalid_topics():
    """Return list of dicts with id, name, importance, labels for invalid Topic nodes."""
    q = (
        "MATCH (t:Topic) "
        "WHERE t.importance IS NULL OR NOT t.importance IN [1,2,3,4,5] "
        "RETURN t.id AS id, t.name AS name, t.importance AS importance, labels(t) AS labels "
        "ORDER BY t.id"
    )
    rows = run_cypher(q) or []
    return rows


def main():
    logger.info("🔍 Scanning for Topic nodes with invalid importance…")
    rows = fetch_invalid_topics()
    total = len(rows)
    if total == 0:
        logger.info("✅ No invalid-importance Topic nodes found.")
        return

    logger.warning(f"Found {total} invalid-importance Topic nodes. Proceeding to remove them now…")
    removed = 0

    for r in rows:
        node_id = r.get("id")
        name = r.get("name")
        imp = r.get("importance")
        labels = r.get("labels")
        if not node_id:
            raise ValueError(f"Encountered Topic node without 'id' property: {r}")

        reason = f"cleanup_invalid_importance:{imp} labels={labels}"
        logger.info(f"🗑️ Removing Topic id={node_id} name={name} importance={imp}")
        out = remove_node(node_id, reason=reason)
        removed += 1
        logger.debug(f"Removed: {out}")

    master_log(f"Cleanup removed {removed}/{total} Topic nodes with invalid importance", removes_node=removed)
    logger.info(f"✅ Cleanup complete. Removed {removed} nodes.")


if __name__ == "__main__":
    main()
