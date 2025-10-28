from src.graph.neo4j_client import connect_graph_db, NEO4J_DATABASE
from utils import app_logging
from src.observability.pipeline_logging import master_log, master_log_error, master_statistics
from difflib import get_close_matches
from events.classifier import EventClassifier, EventType
from typing import Optional, Any
from src.graph.ops.topic import get_all_topics, get_topic_by_id
from src.graph.policies.topic import llm_filter_all_interesting_topics
from src.graph.policies.link import llm_select_link_to_remove, llm_select_one_new_link
from pydantic import BaseModel

logger = app_logging.get_logger(__name__)

class LinkModel(BaseModel):
    type: str = ""
    source: str = ""
    target: str = ""

def add_link(link: LinkModel, context: Optional[dict[str, Any]] = None) -> None:
    """
    Adds the link to the graph if not present. Expects link dict with type, source, target, motivation.
    Enhanced: Logs Cypher counters, checks topic existence, fails loud if nothing is created.
    """
    logger.info(f"Adding link: {link}")
    # Minimal tracker for add_relationship
    tracker = EventClassifier(EventType.ADD_RELATIONSHIP)

    tracker.put_many(relationship_type=link.type, source_id=link.source, target_id=link.target, proposed_link=link)

    if isinstance(context, dict):
        # Scalars -> inputs
        for key in (
            "remove_cause",
            "selection_motivation",
            "candidate_motivation",
            "existing_links_count",
            "candidate_count",
            "all_topics_count",
            "user_confirmation",
            "trigger_stage",
            "entry_point",
        ):
            if key in context:
                tracker.put(key, context.get(key))
        # Lists -> length + preview
        for list_key in ("candidate_ids", "existing_links_before"):
            val = context.get(list_key)
            if isinstance(val, list):
                tracker.put(f"{list_key}_len", len(val))
                tracker.put(f"{list_key}_preview", val[:50])
        # Dicts -> details
        for dict_key in ("prioritized_link", "llm_raw_response", "source_topic"):
            val = context.get(dict_key)
            if isinstance(val, dict):
                tracker.put(dict_key, val)
    event_id = f"{link.source.lower()}__{link.type.lower()}__{link.target.lower()}"
    try:
        driver = connect_graph_db()
        with driver.session(database=NEO4J_DATABASE) as session:
            # Fetch and log all Topic topics' IDs and names
            query_topics = """
            MATCH (n:Topic)
            RETURN n.id, n.name
            """
            result_topics = session.run(query_topics)
            topics = [(record["n.id"], record["n.name"]) for record in result_topics]
            logger.info(f"Fetched {len(topics)} Topic topics:")
            for topic in topics[:25]:
                logger.info(f" - {topic[0]}: {topic[1]}")
            if len(topics) > 25:
                logger.info(f" - ... (and {len(topics) - 25} more)")

            # Check if source and target IDs exist in the topic list
            source_exists = any(topic[0] == link.source for topic in topics)
            target_exists = any(topic[0] == link.target for topic in topics)
            logger.info(f"Source ID '{link.source}' exists: {source_exists}")
            logger.info(f"Target ID '{link.target}' exists: {target_exists}")

            # Log closest matches for debugging
            if not source_exists:
                source_matches = get_close_matches(
                    link.source, [topic[0] for topic in topics], n=3, cutoff=0.6
                )
                logger.info(
                    f"Closest matches for source ID '{link.source}': {source_matches}"
                )
            if not target_exists:
                target_matches = get_close_matches(
                    link.target, [topic[0] for topic in topics], n=3, cutoff=0.6
                )
                logger.info(
                    f"Closest matches for target ID '{link.target}': {target_matches}"
                )

            # 1. Check if source and target topics exist
            query_check = """
            MATCH (src:Topic {id: $source}), (tgt:Topic {id: $target})
            RETURN src, tgt
            """
            check_result = session.run(
                query_check, {"source": link.source, "target": link.target}
            )
            topics = check_result.single()
            if not topics:
                logger.warning(f"Source or target topic missing for link: {link}")
                raise RuntimeError(
                    f"Cannot create link: source or target topic missing. Link: {link}"
                )
            # 2. Check if link exists
            query_check_rel = """
            MATCH (src:Topic {id: $source})-[r]->(tgt:Topic {id: $target})
            WHERE type(r) = $type
            RETURN r, elementId(r) AS rel_element_id, r.id AS rel_id
            """
            result = session.run(
                query_check_rel,
                {
                    "source": link.source,
                    "target": link.target,
                    "type": link.type,
                },
            )
            record = result.single()
            if record:
                logger.info(f"Link already exists: {link.type} {link.source}->{link.target}")
                master_log(
                    f"Relationship duplicate | {link.source}->{link.target} | type={link.type}"
                )
                master_statistics(duplicates_skipped=1)
                tracker.put_many(status="skipped_duplicate", dedup_decision="already_linked")
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

                tracker.put_many(rel_graph_element_id=rel_element_id, rel_id=rel_id)
                # After snapshot (same as before if duplicate)
                try:
                    after_links = get_existing_links(link.source)  # snapshot
                    tracker.put_many(existing_links_after_len=len(after_links), existing_links_after_preview=after_links[:50])
                except Exception:
                    pass
                tracker.set_id(event_id)
                return
            # 3. Add link
            query_create = f"""
            MATCH (src:Topic {{id: $source}}), (tgt:Topic {{id: $target}})
            CREATE (src)-[r:{link.type}] -> (tgt)
            SET r.id = $rel_id
            RETURN r, elementId(r) AS rel_element_id
            """
            create_result = session.run(
                query_create,
                {
                    "source": link.source,
                    "target": link.target,
                    "rel_id": event_id,
                },
            )
            create_record = create_result.single()
            summary = create_result.consume().counters
            logger.info(f"Cypher CREATE summary: {summary}")
            if summary.relationships_created == 0:
                logger.error(f"No relationship created for link: {link.type} {link.source}->{link.target}")
                raise RuntimeError(
                    f"Failed to add link: Cypher did not create a relationship. Link: {link.type} {link.source}->{link.target}"
                )
            logger.info(f"Link created: {link.type} {link.source}->{link.target}")
            master_statistics(relationships_added=1)
            try:
                cypher_summary = {
                    "_contains_updates": bool(
                        getattr(summary, "contains_updates", False)
                    ),
                    "relationships_created": int(
                        getattr(summary, "relationships_created", 0)
                    ),
                }
                tracker.put("cypher_summary", cypher_summary)
            except Exception:
                # Best-effort; do not fail tracker on summary extraction
                pass
            # Record graph relationship identifiers
            try:
                rel_element_id = (
                    create_record["rel_element_id"] if create_record else None
                )
                tracker.put_many(rel_graph_element_id=rel_element_id, rel_id=event_id)
            except Exception:
                pass
            # After snapshot
            try:
                after_links = get_existing_links(link.source)  # snapshot
                tracker.put_many(existing_links_after_len=len(after_links), existing_links_after_preview=after_links[:50])
            except Exception:
                pass
            # Increment about_links_added or relationships_added in stats
            if link.type == "ABOUT":
                master_log(
                    f"ABOUT link created | {link.source}->{link.target} | type=ABOUT",
                    about_links_added=1,
                )
            else:
                master_log(
                    f"topic relationship created | {link.source}->{link.target} | type={link.type}",
                    relationships_added=1,
                )
            tracker.put_many(status="success", dedup_decision="new")
            tracker.set_id(event_id)
    except Exception as e:
        logger.error(f"[add_link] Failed to add link: {e}", exc_info=True)
        master_log_error(
            f"Relationship create error | {link.source}->{link.target} | type={link.type}",
            e,
        )
        try:
            tracker.put_many(status="error", error=str(e))
            tracker.set_id(event_id)
        except Exception:
            pass
        raise RuntimeError(f"Failed to add link: {e}")


logger = app_logging.get_logger(__name__)

MAX_LINKS_PER_TYPE = 10


def find_influences_and_correlates(topic_id: str, test: bool = False) -> dict[str, str]:
    """
    God-tier orchestrator: discovers and manages the strongest new relationship for the given topic topic.
    Returns a dict with full trace of actions and results.
    """
    trace = {}
    logger.info(f" Called for topic_id={topic_id}")
    # 1. Fetch source topic
    try:
        topic = get_topic_by_id(topic_id)
    except Exception as e:
        logger.warning(
            f" Source topic missing for topic_id={topic_id}; skipping discovery"
        )
        master_log_error(
            f"find_influences_and_correlates skipped: Topic missing | topic_id={topic_id}",
            error=e,
        )
        trace["action"] = "topic_missing"
        return trace
    trace["source_topic"] = topic
    logger.info(f" Source topic fetched: {topic.get('name', topic.get('id'))}")
    # 2. Fetch all topics
    all_topics = get_all_topics()
    trace["all_topics_count"] = len(all_topics)
    logger.info(f" Fetched {len(all_topics)} total topics for candidate selection.")
    # 3. LLM filter to plausible candidates
    shortlist = llm_filter_all_interesting_topics(topic, all_topics)
    candidate_ids = shortlist.get("candidate_ids", [])
    candidate_motivation = shortlist.get("motivation")
    trace["candidate_ids"] = candidate_ids
    trace["candidate_motivation"] = candidate_motivation
    logger.info(f" LLM shortlisted {len(candidate_ids)} candidate topics.")
    candidate_topics = [n for n in all_topics if n["id"] in candidate_ids]
    # 4. Fetch existing links
    existing_links = get_existing_links(topic_id)
    trace["existing_links"] = existing_links
    logger.info(f" topic has {len(existing_links)} existing links.")
    # 5. LLM propose strongest new link
    new_link = llm_select_one_new_link(topic, candidate_topics, existing_links)
    trace["proposed_link"] = new_link.model_dump() if new_link else None
    if not new_link:
        logger.info(" No strong new link proposed by LLM. Exiting.")
        trace["action"] = "no_link_proposed"
        return trace
    logger.info(f" LLM proposed link: {new_link.type} {new_link.source}->{new_link.target}")
    # 6. Check max-link cap for this type
    link_type = new_link.type
    links_of_type = [l for l in existing_links if l["type"] == link_type]
    if len(links_of_type) >= MAX_LINKS_PER_TYPE:
        logger.info(
            f" Max links ({MAX_LINKS_PER_TYPE}) for type '{link_type}' reached. Invoking LLM removal selector."
        )
        status = select_and_remove_link(topic, links_of_type, new_link.model_dump())
        trace["removal_decision"] = status.get("removal_decision")
        if status.get("ok"):
            # Prepare context for tracker provenance (kept same keys used in add_link tracker)
            context = {
                "candidate_ids": candidate_ids,
                "candidate_motivation": candidate_motivation,
                "selection_motivation": new_link.motivation,
                "existing_links_before": existing_links,
                "all_topics_count": len(all_topics),
                "candidate_count": len(candidate_ids),
                "existing_links_count": len(existing_links),
            }
            add_link(LinkModel(type=new_link.type, source=new_link.source, target=new_link.target), context=context)
            logger.info(f" Added new link after removal: {new_link.type} {new_link.source}->{new_link.target}")
            trace["action"] = "removed_and_added"
            return trace
        else:
            reason = status.get("reason") or "no_removal_recommended"
            if reason == "removal_link_not_found":
                logger.info(
                    " LLM suggested removal, but link not found. No action taken."
                )
                trace["action"] = "removal_link_not_found"
            else:
                logger.info(
                    " LLM did not recommend removing any existing link. No action taken."
                )
                trace["action"] = "no_removal_recommended"
            return trace
    else:
        # Add new link directly
        # Prepare context for tracker provenance
        context = {
            "candidate_ids": candidate_ids,
            "candidate_motivation": candidate_motivation,
            "selection_motivation": new_link.motivation,
            "existing_links_before": existing_links,
            "all_topics_count": len(all_topics),
            "candidate_count": len(candidate_ids),
            "existing_links_count": len(existing_links),
        }
        add_link(LinkModel(type=new_link.type, source=new_link.source, target=new_link.target), context=context)
        logger.info(f" Added new link: {new_link.type} {new_link.source}->{new_link.target}")
        trace["action"] = "added_new_link"
        return trace


def get_existing_links(topic_id: str) -> list[dict]:
    """
    Fetch all existing topic-to-topic links for the given topic_id.
    Returns list of dicts: {type, source, target}
    """
    logger.info(
        f"[get_existing_links] Fetching all topic-to-topic links for topic_id={topic_id}"
    )
    try:
        driver = connect_graph_db()
        with driver.session(database=NEO4J_DATABASE) as session:
            query = """
            MATCH (src:Topic {id: $id})-[r]->(tgt:Topic)
            RETURN type(r) AS type, src.id AS source, tgt.id AS target
            """
            logger.info(
                f"[get_existing_links] Running query: {query} with id={topic_id}"
            )
            result = session.run(query, {"id": topic_id})
            links = [dict(record) for record in result]
            logger.info(
                f"[get_existing_links] Fetched {len(links)} links for topic_id={topic_id}"
            )
            return links
    except Exception as e:
        logger.error(
            f"[get_existing_links] Failed to fetch links from Neo4j: {e}", exc_info=True
        )
        raise RuntimeError(f"Failed to fetch links from Neo4j: {e}")


def remove_link(link: dict[str, str], context: Optional[dict[str, str]] = None):
    """
    Removes the specified link from the graph.
    Minimal tracker: logs IDs, rel identifiers, and before/after snapshots.
    """
    logger.info(f"Removing link: {link}")
    tracker = EventClassifier(EventType.REMOVE_RELATIONSHIP)
    tracker.put_many(relationship_type=link.get("type"), source_id=link.get("source"), target_id=link.get("target"), proposed_link=link)
 
    # Include upstream selection context (motivation, prioritized link, raw LLM response)
    if isinstance(context, dict):
        for key in (
            "selection_motivation",
            "remove_cause",
            "trigger_stage",
            "entry_point",
        ):
            if key in context:
                tracker.put(key, context.get(key))
        # Duplicate a friendly top-level 'motivation' for quick inspection
        if context.get("selection_motivation"):
            tracker.put("motivation", context.get("selection_motivation"))
        for dict_key in (
            "prioritized_link",
            "llm_raw_response",
            "removal_decision",
            "source_topic",
        ):
            val = context.get(dict_key)
            if isinstance(val, dict):
                tracker.put(dict_key, val)
    event_id = f"{str(link.get('source','none')).lower()}__{str(link.get('type','none')).lower()}__{str(link.get('target','none')).lower()}"
    try:
        # Pre-snapshot
        before_links = get_existing_links(link["source"])  # snapshot
        tracker.put_many(existing_links_before_len=len(before_links), existing_links_before_preview=before_links[:50])
        driver = connect_graph_db()
        with driver.session(database=NEO4J_DATABASE) as session:
            query = """
            MATCH (src:Topic {id: $source})-[r]->(tgt:Topic {id: $target})
            WHERE type(r) = $type
            WITH r, elementId(r) AS rel_element_id, r.id AS rel_id
            DELETE r
            RETURN rel_element_id, rel_id
            """
            delete_result = session.run(
                query,
                {
                    "source": link["source"],
                    "target": link["target"],
                    "type": link["type"],
                },
            )
            record = delete_result.single()
            # Record relationship identifiers
            rel_element_id = record["rel_element_id"] if record else None
            rid = record["rel_id"] if record else None
            tracker.put_many(rel_graph_element_id=rel_element_id, rel_id=rid if rid else event_id)
            logger.info(f"Link removed: {link}")
        # Post-snapshot and stats
        after_links = get_existing_links(link["source"])  # snapshot
        tracker.put_many(existing_links_after_len=len(after_links), existing_links_after_preview=after_links[:50])
        if link.get("type") == "ABOUT":
            master_log(
                f"ABOUT link removed | {link.get('source','?')}->{link.get('target','?')} | type=ABOUT",
                about_links_removed=1,
            )
        else:
            master_log(
                f"topic relationship removed | {link.get('source','?')}->{link.get('target','?')} | type={link.get('type','?')}",
                relationships_removed=1,
            )
        tracker.put("status", "success")
        tracker.set_id(event_id)
    except Exception as e:
        logger.error(f"Failed to remove link: {e}", exc_info=True)
        master_log_error(
            f"Relationship remove error | {link.get('source','?')}->{link.get('target','?')} | type={link.get('type','?')}",
            e,
        )
        tracker.put_many(status="error", error=str(e))
        tracker.set_id(event_id)
        raise RuntimeError(f"Failed to remove link: {e}")


def select_and_remove_link(
    source_topic: dict,
    candidate_links: list[dict],
    prioritized_link: dict | None = None,
) -> dict:
    """
    Minimal wrapper used by orchestrators to delegate LLM selection and execute removal.
    Returns: {ok: bool, removal_decision: dict|None, link_removed: dict|None, reason: str|None}
    """
    removal_decision = llm_select_link_to_remove(
        source_topic, candidate_links, prioritized_link
    )
    if removal_decision and removal_decision.get("remove_link"):
        link_to_remove = next(
            (
                l
                for l in candidate_links
                if l.get("target") == removal_decision["remove_link"]
            ),
            None,
        )
        if link_to_remove:
            ctx = {
                "selection_motivation": removal_decision.get("motivation"),
                "llm_raw_response": (
                    removal_decision if isinstance(removal_decision, dict) else None
                ),
                "removal_decision": (
                    removal_decision if isinstance(removal_decision, dict) else None
                ),
                "prioritized_link": (
                    prioritized_link if isinstance(prioritized_link, dict) else None
                ),
                "source_topic": (
                    source_topic if isinstance(source_topic, dict) else None
                ),
                "remove_cause": "capacity_rebalance_for_prioritized_link",
                "entry_point": "graph_relationships.remove_link.select_and_remove_link",
            }
            remove_link(link_to_remove, context=ctx)
            return {
                "ok": True,
                "removal_decision": removal_decision,
                "link_removed": link_to_remove,
                "reason": None,
            }
        else:
            return {
                "ok": False,
                "removal_decision": removal_decision,
                "link_removed": None,
                "reason": "removal_link_not_found",
            }
    return {
        "ok": False,
        "removal_decision": removal_decision,
        "link_removed": None,
        "reason": "no_removal_recommended",
    }


def create_about_link_with_classification(
    article_id: str,
    topic_id: str,
    timeframe: str,
    importance_risk: int,
    importance_opportunity: int,
    importance_trend: int,
    importance_catalyst: int,
    motivation: str,
    implications: str
) -> None:
    """
    Create ABOUT relationship with rich classification properties.
    
    This is the NEW way - stores classification on relationship, not article node.
    Each article-topic relationship gets its own context-aware classification.
    
    Args:
        article_id: Article ID
        topic_id: Topic ID
        timeframe: "fundamental", "medium", or "current"
        importance_risk: Risk importance score (0-10)
        importance_opportunity: Opportunity importance score (0-10)
        importance_trend: Trend importance score (0-10)
        importance_catalyst: Catalyst importance score (0-10)
        motivation: Why this article matters for THIS topic (1-2 sentences)
        implications: What this could mean for THIS topic going forward (1-2 sentences)
    
    Example:
        >>> create_about_link_with_classification(
        ...     article_id="ABC123",
        ...     topic_id="spx",
        ...     timeframe="current",
        ...     importance_risk=8,
        ...     importance_opportunity=2,
        ...     importance_trend=5,
        ...     importance_catalyst=9,
        ...     motivation="Powell's hawkish tone signals rates staying higher...",
        ...     implications="Could trigger 5-8% correction as markets reprice..."
        ... )
    """
    from src.graph.neo4j_client import run_cypher
    
    # Check if link already exists
    check_query = """
    MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
    RETURN r
    """
    existing = run_cypher(check_query, {"article_id": article_id, "topic_id": topic_id})
    
    if existing:
        logger.info(f"ABOUT link already exists: {article_id} -> {topic_id}")
        master_statistics(duplicates_skipped=1)
        return
    
    # Create new link with all classification properties
    create_query = """
    MATCH (a:Article {id: $article_id}), (t:Topic {id: $topic_id})
    CREATE (a)-[:ABOUT {
        timeframe: $timeframe,
        importance_risk: $importance_risk,
        importance_opportunity: $importance_opportunity,
        importance_trend: $importance_trend,
        importance_catalyst: $importance_catalyst,
        motivation: $motivation,
        implications: $implications,
        created_at: datetime()
    }]->(t)
    """
    
    run_cypher(create_query, {
        "article_id": article_id,
        "topic_id": topic_id,
        "timeframe": timeframe,
        "importance_risk": importance_risk,
        "importance_opportunity": importance_opportunity,
        "importance_trend": importance_trend,
        "importance_catalyst": importance_catalyst,
        "motivation": motivation,
        "implications": implications
    })
    
    # Calculate overall importance for logging
    overall_importance = max(importance_risk, importance_opportunity, importance_trend, importance_catalyst)
    
    logger.info(
        f"Created ABOUT link: {article_id} -> {topic_id} | "
        f"timeframe={timeframe} | importance={overall_importance} "
        f"(R:{importance_risk} O:{importance_opportunity} T:{importance_trend} C:{importance_catalyst})"
    )
    master_statistics(about_links_added=1)
