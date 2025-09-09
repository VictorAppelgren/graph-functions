"""
Remove a Topic node from the graph by id, detaching all relationships.
Stateless, minimal, and fail-fast per project principles.
"""
from utils import app_logging
from graph.neo4j_client import run_cypher
from events.classifier import EventClassifier
from observability.pipeline_logging import master_log

logger = app_logging.get_logger(__name__)


def remove_node(node_id: str, reason: str | None = None) -> dict:
    """
    Removes a Topic node (and all its relationships) by property id.

    Args:
        node_id: The Topic node's `id` property value.
        reason: Optional motivation for removal (e.g., misclassified/irrelevant).

    Returns:
        dict with minimal outcome details:
        {
          "status": "deleted",
          "id": str,
          "name": str|None,
          "importance": int|None,
          "element_id": str,
          "deleted_relationships": int,
        }

    Raises:
        ValueError if node_id is invalid or node is not found.
    """
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError("node_id must be a non-empty string")

    # Event Classifier
    trk = EventClassifier("remove_node")
    trk.put("target_node_id", node_id)
    if reason is not None:
        trk.put("reason", reason)

    # 1) Fetch minimal node details (fail fast if not found)
    q_fetch = (
        "MATCH (t:Topic {id: $id}) "
        "RETURN elementId(t) AS element_id, t.name AS name, t.importance AS importance, labels(t) AS labels"
    )
    res = run_cypher(q_fetch, {"id": node_id})
    if not res:
        trk.put("status", "not_found")
        trk.set_id("none")
        raise ValueError(f"Topic node with id '{node_id}' not found")

    row = res[0]
    element_id = row.get("element_id")
    name = row.get("name")
    importance = row.get("importance")
    labels = row.get("labels")

    trk.put("node_name", str(name))
    trk.put("node_importance", str(importance))
    trk.put("node_labels", {"labels": labels} if isinstance(labels, list) else {"labels": []})

    # 2) Count attached relationships (for reporting)
    q_count = (
        "MATCH (t:Topic {id: $id}) "
        "OPTIONAL MATCH (t)-[r]-() "
        "RETURN count(r) AS rel_count"
    )
    count_res = run_cypher(q_count, {"id": node_id})
    rel_count = int(count_res[0]["rel_count"]) if count_res else 0
    trk.put("attached_relationships", str(rel_count))

    # 3) Delete the node and detach all rels
    q_delete = (
        "MATCH (t:Topic {id: $id}) "
        "DETACH DELETE t"
    )
    run_cypher(q_delete, {"id": node_id})

    trk.put("status", "success")
    trk.set_id(element_id or node_id)

    logger.info(f"Removed Topic node: name={name} id={node_id} element_id={element_id} rels={rel_count}")
    master_log(
        f"Topic removed | name={name} | id={node_id} | element_id={element_id} | rels={rel_count} | reason={(reason or '')[:200]}",
        removes_node=1,
    )
    return {
        "status": "deleted",
        "id": node_id,
        "name": name,
        "importance": importance,
        "element_id": element_id,
        "deleted_relationships": rel_count,
        "reason": reason,
    }
