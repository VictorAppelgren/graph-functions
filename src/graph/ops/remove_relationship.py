
from typing import Optional

from graph.neo4j_client import connect_graph_db
from utils import app_logging
from observability.pipeline_logging import master_log, master_log_error
from events.classifier import EventClassifier
from func_add_relationships.get_links import get_existing_links
from graph.policies.link_removal import llm_select_link_to_remove

logger = app_logging.get_logger(__name__)


def remove_link(link: dict, context: Optional[dict] = None):
    """
    Removes the specified link from the graph.
    Minimal tracker: logs IDs, rel identifiers, and before/after snapshots.
    """
    logger.info(f"Removing link: {link}")
    trk = EventClassifier("remove_relationship")
    trk.put("relationship_type", link.get("type"))
    trk.put("source_id", link.get("source"))
    trk.put("target_id", link.get("target"))
    # Store the proposed link object itself for provenance
    trk.put("proposed_link", link)
    # Include upstream selection context (motivation, prioritized link, raw LLM response)
    if isinstance(context, dict):
        for key in (
            "selection_motivation",
            "remove_cause",
            "trigger_stage",
            "entry_point",
        ):
            if key in context:
                trk.put(key, context.get(key))
        # Duplicate a friendly top-level 'motivation' for quick inspection
        if context.get("selection_motivation"):
            trk.put("motivation", context.get("selection_motivation"))
        for dict_key in ("prioritized_link", "llm_raw_response", "removal_decision", "source_node"):
            val = context.get(dict_key)
            if isinstance(val, dict):
                trk.put(dict_key, val)
    event_id = f"{str(link.get('source','none')).lower()}__{str(link.get('type','none')).lower()}__{str(link.get('target','none')).lower()}"
    try:
        # Pre-snapshot
        before_links = get_existing_links(link["source"])  # snapshot
        trk.put("existing_links_before_len", len(before_links))
        trk.put("existing_links_before_preview", before_links[:50])
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            query = """
            MATCH (src:Topic {id: $source})-[r]->(tgt:Topic {id: $target})
            WHERE type(r) = $type
            WITH r, elementId(r) AS rel_element_id, r.id AS rel_id
            DELETE r
            RETURN rel_element_id, rel_id
            """
            delete_result = session.run(query, {"source": link["source"], "target": link["target"], "type": link["type"]})
            record = delete_result.single()
            # Record relationship identifiers
            rel_element_id = record["rel_element_id"] if record else None
            rid = record["rel_id"] if record else None
            trk.put("rel_graph_element_id", rel_element_id)
            trk.put("rel_id", rid if rid else event_id)
            logger.info(f"Link removed: {link}")
        # Post-snapshot and stats
        after_links = get_existing_links(link["source"])  # snapshot
        trk.put("existing_links_after_len", len(after_links))
        trk.put("existing_links_after_preview", after_links[:50])
        if link.get('type') == 'ABOUT':
            master_log(f"ABOUT link removed | {link.get('source','?')}->{link.get('target','?')} | type=ABOUT", about_links_removed=1)
        else:
            master_log(f"Node relationship removed | {link.get('source','?')}->{link.get('target','?')} | type={link.get('type','?')}", relationships_removed=1)
        trk.put("status", "success")
        trk.set_id(event_id)
    except Exception as e:
        logger.error(f"Failed to remove link: {e}", exc_info=True)
        master_log_error(f"Relationship remove error | {link.get('source','?')}->{link.get('target','?')} | type={link.get('type','?')}", e)
        trk.put("status", "error")
        trk.put("error", str(e))
        trk.set_id(event_id)
        raise RuntimeError(f"Failed to remove link: {e}")


def select_and_remove_link(source_node: dict, candidate_links: list[dict], prioritized_link: dict | None = None) -> dict:
    """
    Minimal wrapper used by orchestrators to delegate LLM selection and execute removal.
    Returns: {ok: bool, removal_decision: dict|None, link_removed: dict|None, reason: str|None}
    """
    removal_decision = llm_select_link_to_remove(source_node, candidate_links, prioritized_link)
    if removal_decision and removal_decision.get('remove_link'):
        link_to_remove = next((l for l in candidate_links if l.get('target') == removal_decision['remove_link']), None)
        if link_to_remove:
            ctx = {
                "selection_motivation": removal_decision.get("motivation"),
                "llm_raw_response": removal_decision if isinstance(removal_decision, dict) else None,
                "removal_decision": removal_decision if isinstance(removal_decision, dict) else None,
                "prioritized_link": prioritized_link if isinstance(prioritized_link, dict) else None,
                "source_node": source_node if isinstance(source_node, dict) else None,
                "remove_cause": "capacity_rebalance_for_prioritized_link",
                "entry_point": "graph_relationships.remove_link.select_and_remove_link",
            }
            remove_link(link_to_remove, context=ctx)
            return {"ok": True, "removal_decision": removal_decision, "link_removed": link_to_remove, "reason": None}
        else:
            return {"ok": False, "removal_decision": removal_decision, "link_removed": None, "reason": "removal_link_not_found"}
    return {"ok": False, "removal_decision": removal_decision, "link_removed": None, "reason": "no_removal_recommended"}

