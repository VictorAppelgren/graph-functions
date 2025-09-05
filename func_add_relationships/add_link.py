from graph_db.db_driver import connect_graph_db
from utils import minimal_logging
from utils.master_log import master_log, master_log_error
from difflib import get_close_matches
from tracker.tracker import Tracker
from func_add_relationships.get_existing_links import get_existing_links
from typing import Optional

logger = minimal_logging.get_logger(__name__)

def add_link(link: dict, context: Optional[dict] = None):
    """
    Adds the link to the graph if not present. Expects link dict with type, source, target, motivation.
    Enhanced: Logs Cypher counters, checks node existence, fails loud if nothing is created.
    """
    logger.info(f"Adding link: {link}")
    # Minimal tracker for add_relationship
    trk = Tracker("add_relationship")
    trk.put("relationship_type", link.get("type"))
    trk.put("source_id", link.get("source"))
    trk.put("target_id", link.get("target"))
    # Store full proposed link and any LLM motivation/context
    trk.put("proposed_link", link)
    # Include upstream LLM provenance if provided
    if isinstance(context, dict):
        # Scalars -> inputs
        for key in (
            "remove_cause",
            "selection_motivation",
            "candidate_motivation",
            "existing_links_count",
            "candidate_count",
            "all_nodes_count",
            "user_confirmation",
            "trigger_stage",
            "entry_point",
        ):
            if key in context:
                trk.put(key, context.get(key))
        # Lists -> length + preview
        for list_key in ("candidate_ids", "existing_links_before"):
            val = context.get(list_key)
            if isinstance(val, list):
                trk.put(f"{list_key}_len", len(val))
                trk.put(f"{list_key}_preview", val[:50])
        # Dicts -> details
        for dict_key in ("prioritized_link", "llm_raw_response", "source_node"):
            val = context.get(dict_key)
            if isinstance(val, dict):
                trk.put(dict_key, val)
    event_id = f"{str(link.get('source','none')).lower()}__{str(link.get('type','none')).lower()}__{str(link.get('target','none')).lower()}"
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            # Fetch and log all Topic nodes' IDs and names
            query_nodes = """
            MATCH (n:Topic)
            RETURN n.id, n.name
            """
            result_nodes = session.run(query_nodes)
            nodes = [(record["n.id"], record["n.name"]) for record in result_nodes]
            logger.info(f"Fetched {len(nodes)} Topic nodes:")
            for node in nodes[:25]:
                logger.info(f" - {node[0]}: {node[1]}")
            if len(nodes) > 25:
                logger.info(f" - ... (and {len(nodes) - 25} more)")

            # Check if source and target IDs exist in the node list
            source_exists = any(node[0] == link["source"] for node in nodes)
            target_exists = any(node[0] == link["target"] for node in nodes)
            logger.info(f"Source ID '{link['source']}' exists: {source_exists}")
            logger.info(f"Target ID '{link['target']}' exists: {target_exists}")

            # Log closest matches for debugging
            if not source_exists:
                source_matches = get_close_matches(link["source"], [node[0] for node in nodes], n=3, cutoff=0.6)
                logger.info(f"Closest matches for source ID '{link['source']}': {source_matches}")
            if not target_exists:
                target_matches = get_close_matches(link["target"], [node[0] for node in nodes], n=3, cutoff=0.6)
                logger.info(f"Closest matches for target ID '{link['target']}': {target_matches}")

            # 1. Check if source and target nodes exist
            query_check = """
            MATCH (src:Topic {id: $source}), (tgt:Topic {id: $target})
            RETURN src, tgt
            """
            check_result = session.run(query_check, {"source": link["source"], "target": link["target"]})
            nodes = check_result.single()
            if not nodes:
                logger.warning(f"Source or target node missing for link: {link}")
                raise RuntimeError(f"Cannot create link: source or target node missing. Link: {link}")
            # 2. Check if link exists
            query_check_rel = """
            MATCH (src:Topic {id: $source})-[r]->(tgt:Topic {id: $target})
            WHERE type(r) = $type
            RETURN r, elementId(r) AS rel_element_id, r.id AS rel_id
            """
            result = session.run(query_check_rel, {"source": link["source"], "target": link["target"], "type": link["type"]})
            record = result.single()
            if record:
                logger.info(f"Link already exists: {link}")
                master_log(f"Relationship duplicate | {link.get('source','?')}->{link.get('target','?')} | type={link.get('type','?')}", duplicates_skipped=1)
                trk.put("status", "skipped_duplicate")
                trk.put("dedup_decision", "already_linked")
                # Record graph relationship identifiers
                try:
                    rel_element_id = record["rel_element_id"]
                except Exception:
                    rel_element_id = None
                try:
                    rid = record["rel_id"]
                    rel_id = rid if rid else event_id
                except Exception:
                    rel_id = event_id
                trk.put("rel_graph_element_id", rel_element_id)
                trk.put("rel_id", rel_id)
                # After snapshot (same as before if duplicate)
                try:
                    after_links = get_existing_links(link["source"])  # snapshot
                    trk.put("existing_links_after_len", len(after_links))
                    trk.put("existing_links_after_preview", after_links[:50])
                except Exception:
                    pass
                trk.set_id(event_id)
                return
            # 3. Add link
            query_create = f"""
            MATCH (src:Topic {{id: $source}}), (tgt:Topic {{id: $target}})
            CREATE (src)-[r:{link['type']}] -> (tgt)
            SET r.id = $rel_id
            RETURN r, elementId(r) AS rel_element_id
            """
            create_result = session.run(query_create, {"source": link["source"], "target": link["target"], "rel_id": event_id})
            create_record = create_result.single()
            summary = create_result.consume().counters
            logger.info(f"Cypher CREATE summary: {summary}")
            if summary.relationships_created == 0:
                logger.error(f"No relationship created for link: {link}")
                raise RuntimeError(f"Failed to add link: Cypher did not create a relationship. Link: {link}")
            logger.info(f"Link created: {link}")
            # Tracker: record cypher summary
            try:
                cypher_summary = {
                    "_contains_updates": bool(getattr(summary, "contains_updates", False)),
                    "relationships_created": int(getattr(summary, "relationships_created", 0)),
                }
                trk.put("cypher_summary", cypher_summary)
            except Exception:
                # Best-effort; do not fail tracker on summary extraction
                pass
            # Record graph relationship identifiers
            try:
                rel_element_id = (create_record["rel_element_id"] if create_record else None)
                trk.put("rel_graph_element_id", rel_element_id)
                trk.put("rel_id", event_id)
            except Exception:
                pass
            # After snapshot
            try:
                after_links = get_existing_links(link["source"])  # snapshot
                trk.put("existing_links_after_len", len(after_links))
                trk.put("existing_links_after_preview", after_links[:50])
            except Exception:
                pass
            # Increment about_links_added or relationships_added in stats
            if link['type'] == 'ABOUT':
                master_log(f"ABOUT link created | {link['source']}->{link['target']} | type=ABOUT", about_links_added=1)
            else:
                master_log(f"Node relationship created | {link['source']}->{link['target']} | type={link['type']}", relationships_added=1)
            trk.put("status", "success")
            trk.put("dedup_decision", "new")
            trk.set_id(event_id)
    except Exception as e:
        logger.error(f"[add_link] Failed to add link: {e}", exc_info=True)
        master_log_error(f"Relationship create error | {link.get('source','?')}->{link.get('target','?')} | type={link.get('type','?')}", e)
        try:
            trk.put("status", "error")
            trk.put("error", str(e))
            trk.set_id(event_id)
        except Exception:
            pass
        raise RuntimeError(f"Failed to add link: {e}")
