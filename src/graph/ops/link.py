from src.graph.neo4j_client import connect_graph_db, NEO4J_DATABASE
from utils import app_logging
from src.observability.stats_client import track
from difflib import get_close_matches
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
    except Exception as e:
        logger.error(f"[add_link] Failed to add link: {e}", exc_info=True)
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
    """
    logger.info(f"Removing link: {link}")
    event_id = f"{str(link.get('source','none')).lower()}__{str(link.get('type','none')).lower()}__{str(link.get('target','none')).lower()}"
    try:
        driver = connect_graph_db()
        with driver.session(database=NEO4J_DATABASE) as session:
            query = """
            MATCH (src:Topic {id: $source})-[r]->(tgt:Topic {id: $target})
            WHERE type(r) = $type
            DELETE r
            """
            session.run(
                query,
                {
                    "source": link["source"],
                    "target": link["target"],
                    "type": link["type"],
                },
            )
            logger.info(f"Link removed: {link}")
    except Exception as e:
        logger.error(f"Failed to remove link: {e}", exc_info=True)
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
    implications: str,
    test: bool = False
) -> dict:
    """
    Create ABOUT relationship with two-stage capacity management.
    
    This function now includes recursive capacity checking that will:
    1. Check if tier has room
    2. If full, run gate decision (accept/downgrade_new/reject)
    3. If downgrading existing article, recursively add it to lower tier
    4. Continue until all articles find their correct tier
    
    Args:
        article_id: Article ID
        topic_id: Topic ID
        timeframe: "fundamental", "medium", or "current"
        importance_risk: Risk importance score (0-3)
        importance_opportunity: Opportunity importance score (0-3)
        importance_trend: Trend importance score (0-3)
        importance_catalyst: Catalyst importance score (0-3)
        motivation: Why this article matters for THIS topic
        implications: What this could mean for THIS topic
        test: If True, skip capacity checks
    
    Returns:
        {"action": "added"|"archived"|"rejected"|"duplicate", "tier": int}
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
        track("article_duplicate_skipped")
        return {"action": "duplicate"}
    
    # Calculate initial tier
    initial_tier = max(importance_risk, importance_opportunity, importance_trend, importance_catalyst)
    
    # Get article metadata for capacity check
    article_query = """
    MATCH (a:Article {id: $article_id})
    RETURN a.summary as summary, a.source as source, a.published_at as published_at
    """
    article_result = run_cypher(article_query, {"article_id": article_id})
    
    if not article_result:
        logger.error(f"Article {article_id} not found")
        return {"action": "error"}
    
    article_data = article_result[0]
    
    # Add with capacity check (recursive)
    result = add_article_with_capacity_check(
        article_id=article_id,
        topic_id=topic_id,
        timeframe=timeframe,
        initial_tier=initial_tier,
        article_summary=article_data["summary"],
        article_source=article_data["source"],
        article_published=article_data["published_at"],
        motivation=motivation,
        implications=implications,
        test=test
    )
    
    return result


# ============================================================================
# NEW: Recursive Capacity Management Functions
# ============================================================================

def add_article_with_capacity_check(
    article_id: str,
    topic_id: str,
    timeframe: str,
    initial_tier: int,
    article_summary: str,
    article_source: str,
    article_published: str,
    motivation: str,
    implications: str,
    test: bool = False
) -> dict:
    """
    Recursively add article with two-stage capacity management.
    
    CRITICAL: When downgrading an existing article, we recursively call
    try_add_at_tier() which will check capacity at the lower tier and
    potentially trigger another downgrade cascade.
    
    Returns:
        {"action": "added", "tier": int}
        {"action": "archived", "tier": 0}
        {"action": "rejected"}
    """
    from src.articles.orchestration.article_capacity_orchestrator import (
        check_capacity,
        gate_decision
    )
    
    def try_add_at_tier(
        aid: str,
        tier: int,
        summary: str,
        source: str,
        published: str,
        motivation_text: str,
        implications_text: str
    ) -> dict:
        """
        Try to add article at this tier.
        
        This function is RECURSIVE and will cascade down tiers
        until the article finds a home or reaches tier 0 (archive).
        """
        
        if tier == 0:
            # Tier 0 = archive, unlimited capacity
            logger.info(f"Archiving article {aid} at tier 0")
            try:
                create_link_at_tier(aid, topic_id, timeframe, 0, motivation_text, implications_text)
                track("article_archived", f"Article {aid} archived at tier 0")
                return {"action": "archived", "tier": 0}
            except Exception as e:
                logger.error(f"Failed to archive article {aid}: {e}")
                track("error_occurred", f"Failed to archive article {aid}: {e}")
                return {"action": "error", "tier": 0}
        
        # Check capacity at this tier
        capacity_info = check_capacity(topic_id, timeframe, tier)
        
        if capacity_info["has_room"]:
            # Room available - just add it
            logger.info(f"Adding article {aid} at tier {tier} (room available)")
            create_link_at_tier(aid, topic_id, timeframe, tier, motivation_text, implications_text)
            track("about_link_created")
            return {"action": "added", "tier": tier}
        
        # Tier is full - Stage 1: Gate Decision
        logger.info(
            f"Tier {tier} full ({capacity_info['count']}/{capacity_info['max']}) "
            f"- running gate decision for article {aid}"
        )
        
        gate_result = gate_decision(
            topic_id=topic_id,
            timeframe=timeframe,
            tier=tier,
            new_article_summary=summary,
            new_article_source=source,
            new_article_published=published,
            existing_articles=capacity_info["articles"],
            test=test
        )
        
        # Check for rejection
        if gate_result["reject"]:
            logger.warning(f"Article {aid} rejected at tier {tier}: {gate_result['reasoning']}")
            track("article_rejected_capacity", f"Article {aid} rejected at tier {tier}: {gate_result['reasoning']}")
            return {"action": "rejected"}
        
        # Not rejected - check who to downgrade
        downgrade_id = gate_result["downgrade"]
        
        if downgrade_id == "NEW":
            # Downgrade new article - try next tier
            logger.info(
                f"Article {aid} downgraded from tier {tier} to tier {tier-1}: "
                f"{gate_result['reasoning']}"
            )
            track("article_downgraded", f"Article {aid} downgraded on arrival from tier {tier} to {tier-1}")
            return try_add_at_tier(
                aid, tier - 1, summary, source, published, 
                motivation_text, implications_text
            )
        
        # Downgrade existing article - THIS IS WHERE THE CASCADE HAPPENS
        logger.info(
            f"Downgrading existing article {downgrade_id} from tier {tier} to tier {tier-1}: "
            f"{gate_result['reasoning']}"
        )
        
        # Move existing article down one tier IN PLACE (keep ABOUT link)
        new_tier = max(tier - 1, 0)
        set_about_link_tier(downgrade_id, topic_id, timeframe, new_tier)
        track(
            "article_downgraded",
            f"Article {downgrade_id} downgraded in-place from tier {tier} to tier {new_tier}"
        )
        
        # Now we have room at current tier - add new article
        logger.info(f"Adding article {aid} at tier {tier} (made room by downgrading {downgrade_id})")
        create_link_at_tier(aid, topic_id, timeframe, tier, motivation_text, implications_text)
        track("about_link_created")
        return {"action": "added", "tier": tier}
    
    # Start recursive process
    logger.info(f"Starting capacity check for article {article_id} at tier {initial_tier}")
    return try_add_at_tier(
        aid=article_id,
        tier=initial_tier,
        summary=article_summary,
        source=article_source,
        published=article_published,
        motivation_text=motivation,
        implications_text=implications
    )


def create_link_at_tier(
    article_id: str,
    topic_id: str,
    timeframe: str,
    tier: int,
    motivation: str,
    implications: str
):
    """Create ABOUT link with uniform importance scores at tier."""
    from src.graph.neo4j_client import run_cypher
    
    create_query = """
    MATCH (a:Article {id: $article_id}), (t:Topic {id: $topic_id})
    CREATE (a)-[:ABOUT {
        timeframe: $timeframe,
        importance_risk: $tier,
        importance_opportunity: $tier,
        importance_trend: $tier,
        importance_catalyst: $tier,
        motivation: $motivation,
        implications: $implications,
        created_at: datetime()
    }]->(t)
    """
    
    run_cypher(create_query, {
        "article_id": article_id,
        "topic_id": topic_id,
        "timeframe": timeframe,
        "tier": tier,
        "motivation": motivation,
        "implications": implications
    })
    
    logger.info(f"Created ABOUT link: {article_id} -> {topic_id} | tier={tier}")


def set_about_link_tier(
    article_id: str,
    topic_id: str,
    timeframe: str,
    tier: int,
):
    """Set all importance_* fields for an existing ABOUT link to the given tier.

    This updates the relationship in place and does NOT create or delete any links.
    """
    from src.graph.neo4j_client import run_cypher

    safe_tier = max(tier, 0)

    query = """
    MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
    WHERE r.timeframe = $timeframe
    SET
        r.importance_risk = $tier,
        r.importance_opportunity = $tier,
        r.importance_trend = $tier,
        r.importance_catalyst = $tier
    """

    run_cypher(
        query,
        {
            "article_id": article_id,
            "topic_id": topic_id,
            "timeframe": timeframe,
            "tier": safe_tier,
        },
    )

    logger.info(
        f"Set ABOUT link tier for {article_id} -> {topic_id} | timeframe={timeframe} | tier={safe_tier}"
    )


def get_existing_article_data(article_id: str, topic_id: str) -> dict:
    """Get existing article data from relationship."""
    from src.graph.neo4j_client import run_cypher
    
    query = """
    MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
    RETURN 
        a.summary as summary,
        a.source as source,
        a.published_at as published_at,
        r.motivation as motivation,
        r.implications as implications
    """
    
    result = run_cypher(query, {"article_id": article_id, "topic_id": topic_id})
    
    if not result:
        logger.warning(f"No data found for article {article_id} -> topic {topic_id}")
        return {}
    
    return result[0]


def remove_link(article_id: str, topic_id: str):
    """Remove ABOUT relationship."""
    from src.graph.neo4j_client import run_cypher
    
    query = """
    MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
    DELETE r
    """
    
    run_cypher(query, {"article_id": article_id, "topic_id": topic_id})
    logger.info(f"Removed ABOUT link: {article_id} -> {topic_id}")
