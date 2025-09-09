# scripts/backfill_topic_importance.py
"""
Backfill importance (1..5) for Topic nodes missing it.
Simplicity-first: no CLI flags; runs updates directly.
"""
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils import app_logging
from src.graph.neo4j_client import connect_graph_db
from src.graph.policies.topic_priority import classify_topic_importance
from src.graph.ops.remove_node import remove_node

logger = app_logging.get_logger(__name__)

def fetch_missing(driver, limit: int | None):
    q = """
    MATCH (t:Topic)
    WHERE t.importance IS NULL OR t.importance IN [4,5] OR t.importance = 'REMOVE'
    RETURN t.id AS id, t.name AS name, t.type AS type, t.importance AS importance
    """ + (f" LIMIT {int(limit)}" if limit else "")
    with driver.session(database="argosgraph") as s:
        rows = s.run(q).data()
    return rows or []

def set_props(driver, topic_id: str, importance: int):
    q = """
    MATCH (t:Topic {id: $id})
    SET t.importance = $importance
    RETURN t.id AS id
    """
    with driver.session(database="argosgraph") as s:
        res = s.run(q, {"id": topic_id, "importance": importance}).data()
    return res

def main():
    driver = connect_graph_db()
    rows = fetch_missing(driver, None)
    missing_only = sum(1 for r in rows if r.get("importance") is None)
    logger.info("Found %d topics to audit (importance NULL, in [4,5], or 'REMOVE'). Missing only: %d", len(rows), missing_only)
    updated = 0
    for r in rows:
        name = r.get("name") or ""
        ttype = r.get("type") or ""
        topic_id = r["id"]
        existing_importance = r.get("importance")
        try:
            importance, rationale = classify_topic_importance(topic_name=name, topic_type=ttype, context="")
            # Handle REMOVE outcome by deleting the node
            if isinstance(importance, str) and importance.upper() == "REMOVE":
                reason = (rationale or "")
                logger.info("Topic %s → REMOVE (reason=%s)", topic_id, reason[:200])
                remove_node(topic_id, reason=reason)
            else:
                # Coerce to int if needed
                if isinstance(importance, str) and importance.isdigit():
                    importance_val = int(importance)
                elif isinstance(importance, int):
                    importance_val = importance
                else:
                    raise ValueError(f"Unexpected importance type: {type(importance)} value={importance}")

                if existing_importance is None or (isinstance(existing_importance, str) and str(existing_importance).upper() == "REMOVE"):
                    logger.info("Topic %s → importance=%s", topic_id, importance_val)
                    set_props(driver, topic_id, importance_val)
                    updated += 1
                else:
                    # Existing 4/5: keep as-is unless removed
                    logger.info("Topic %s → kept (existing importance=%s)", topic_id, existing_importance)
        except Exception as e:
            logger.error("Failed to classify topic %s: %r", topic_id, e)
            raise

    logger.info("Backfill completed. Updated=%d", updated)

if __name__ == "__main__":
    main()