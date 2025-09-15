"""
Adds new nodes (Topic, Article) to the graph and creates relationships.
For Topic nodes, uses LLM to propose all required fields.
For Article nodes, extracts properties directly from article data.
"""

from typing import TypedDict
from utils import app_logging
from src.articles.load_article import load_article
from src.articles.article_text_formatter import extract_text_from_json_article
from datetime import datetime, timezone
from src.graph.policies.topic_priority import classify_topic_importance
from src.graph.policies.topic_relevance import check_topic_relevance
from src.graph.policies.topic_category import classify_topic_category
from src.observability.pipeline_logging import problem_log, master_log
from src.analysis.policies.query_generator import create_wide_query
from src.analysis.policies.topic_proposal import propose_topic_node
from src.graph.ops.create_topic_node import create_topic_node
from src.demo.llm.topic_capacity_guard_llm import decide_topic_capacity
from src.graph.ops.get_all_nodes import get_all_nodes
from src.graph.neo4j_client import run_cypher
from events.classifier import EventClassifier

logger = app_logging.get_logger(__name__)

class NodeStatus(TypedDict):
    status: str
    topic_name: str
    category: None | str
    should_add: bool
    motivation_for_relevance: str
    failure_category: str

def add_node(article_id: str, suggested_names: list[str] = []) -> dict:
    """
    Uses an LLM to propose a new Topic node for the graph based on the article.
    Returns the created node as a dict.
    """
    logger.info('---------')
    logger.info('REMOVE THIS LATER! IF WE ADD A NODE, DOES IT ALSO CREATE THE ARTICLE AND THE ABOUT RELATIONSHIP?')
    logger.info('---------')
    
    # Minimal event tracking
    trk = EventClassifier("add_node")
    trk.put("source_article_id", article_id)
    trk.put("suggested_names", suggested_names)
    # Load the article
    article_json = load_article(article_id)
    logger.debug(f"Sample article_json: {str(article_json)[:400]}{'...' if len(str(article_json)) > 400 else ''}")

    # Extract formatted text for LLMs
    article_text = extract_text_from_json_article(article_json)
    logger.debug(f"Sample article_text: {article_text[:400]}{'...' if len(article_text) > 400 else ''}")

    # Propose new topic node using formatted text
    topic_dict = propose_topic_node(article_text, suggested_names)
    if not isinstance(topic_dict, dict) or not topic_dict:
        # Unified rejection: treat as gating fail, but with special details
        problem_log(
            problem="Topic rejected",
            topic=article_json.get("title", "unknown") if 'article_json' in locals() else "unknown",
            details={
                "category": None,
                "failure_category": "proposal_null",
            },
        )
        trk.put("status", "rejected")
        trk.put("reject_category", str(None))
        trk.put("reject_failure_cat", "proposal_null")
        trk.put("llm_topic_proposal_raw", topic_dict)
        trk.set_id("none")
        master_log(f"Topic rejected | name={article_json.get('title', 'unknown') if 'article_json' in locals() else 'unknown'} | category=None | failure=proposal_null")
        return {
            "status": "rejected",
            "topic_name": article_json.get("title", "unknown") if 'article_json' in locals() else "unknown",
            "category": None,
            "failure_category": "proposal_null",
            "reason": "proposal_null",
        }
    topic_dict_raw = dict(topic_dict)  # capture raw LLM output for traceability
    # Attach raw proposal immediately so gating rejections are traceable
    trk.put("llm_topic_proposal_raw", topic_dict_raw)
    logger.info("All fields in topic_dict: %s", list(topic_dict.keys()))

    # Topic gating: category + trading relevance before any DB write
    category, motivation_for_category = classify_topic_category(
        topic_id=topic_dict.get("id", ""),
        topic_name=topic_dict.get("name", ""),
        topic_type=topic_dict.get("type", ""),
        motivation=topic_dict.get("motivation", ""),
        article_summary=article_text,
    )
    should_add, motivation_for_relevance = check_topic_relevance(
        topic_id=topic_dict.get("id", ""),
        topic_name=topic_dict.get("name", ""),
        topic_type=topic_dict.get("type", ""),
        motivation=topic_dict.get("motivation", ""),
        article_summary=article_text,
        context=article_text,
    )
    trk.put("topic_category", category)
    trk.put("topic_category_motivation", motivation_for_category)
    trk.put("should_add", should_add)
    trk.put("motivation_for_relevance", motivation_for_relevance)
    if not should_add:
        # Hard abort: persist fail event and propagate errors (no fallbacks)
        problem_log(
            problem="Topic rejected",
            topic=topic_dict["name"],
            details={
                "category": category,
                "should_add": should_add,
                "should_add_motivation": motivation_for_relevance,
            },
        )
        trk.put("status", "rejected")
        trk.put("reject_category", str(category))
        trk.put("reject_failure_cat", "relevance_gate_reject")
        trk.set_id("none")
        # Do not crash on legitimate rejection; log and return minimal status
        master_log(f"Topic rejected | name={topic_dict.get('name', 'unknown')} | category={category} | failure=relevance_gate_reject")
        return {
            "status": "rejected",
            "topic_name": topic_dict["name"],
            "category": category,
            "should_add": should_add,
            "motivation_for_relevance": motivation_for_relevance,
        }

    # Generate wide query for this node using the same formatted text
    query = create_wide_query(article_text)
    logger.debug(f"Sample query: {query['query'][:400]}{'...' if len(query['query']) > 400 else ''}")
    topic_dict["query"] = query["query"]

    # Classify topic importance (1..5) using LLM helper and set scheduling props
    topic_importance, topic_importance_rationale = classify_topic_importance(
        topic_name=topic_dict["name"],
        topic_type=topic_dict["type"],
        context=article_text,
    )
    # If LLM flags this topic for removal, reject and do not persist
    if isinstance(topic_importance, str) and topic_importance.upper() == "REMOVE":
        problem_log(
            problem="Topic rejected",
            topic=topic_dict.get("name", "unknown"),
            details={
                "failure_category": "importance_remove",
                "rationale": topic_importance_rationale,
            },
        )
        trk.put("status", "rejected")
        trk.put("reject_category", str(category))
        trk.put("reject_failure_cat", "importance_remove")
        trk.set_id("none")
        master_log(f"Topic rejected | name={topic_dict.get('name', 'unknown')} | category={category} | failure=importance_remove")
        return {
            "status": "rejected",
            "topic_name": topic_dict.get("name"),
            "category": category,
            "should_add": False,
            "motivation_for_relevance": motivation_for_relevance,
            "failure_category": "importance_remove",
        }

    # Coerce numeric string importance to int
    if isinstance(topic_importance, str) and topic_importance.isdigit():
        topic_importance = int(topic_importance)
    if not isinstance(topic_importance, int):
        raise ValueError(f"Classifier returned non-numeric importance: {topic_importance}")

    topic_dict["importance"] = topic_importance
    topic_dict["importance_rationale"] = topic_importance_rationale
    topic_dict["last_queried"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Attach full reasoning artifacts (IDs only remain in inputs)
    trk.put("llm_topic_proposal_raw", topic_dict_raw)
    trk.put("generated_query", query)
    trk.put("importance_classification", topic_importance)
    trk.put("importance_classification_rationale", topic_importance_rationale)

    # ---- DEMO CAPACITY GUARD (always run) ----
    try:
        existing_topics = get_all_nodes(fields=["id", "name", "type", "importance", "last_updated"])

        candidate_topic = {
            "id": topic_dict.get("id"),
            "name": topic_dict.get("name"),
            "importance": topic_dict.get("importance", 0),
            "category": category,
            "motivation": topic_dict.get("motivation"),
        }

        decision = decide_topic_capacity(
            candidate_topic=candidate_topic,
            existing_topics=existing_topics,
            test=False,
        )
        logger.info("capacity_guard decision: %s", decision)

        action = (decision.get("action") or "").lower()
        if action == "reject":
            problem_log(
                problem="CapacityGuard reject",
                topic=topic_dict.get("name", "unknown"),
                details={
                    "id": topic_dict.get("id"),
                    "importance": topic_dict.get("importance"),
                    "guard_action": action,
                    "guard_motivation": decision.get("motivation"),
                },
            )
            trk.put("status", "rejected")
            trk.put("reject_category", str(category))
            trk.put("reject_failure_cat", "capacity_guard_reject")
            trk.set_id("none")
            master_log(f"Topic rejected by capacity guard | name={topic_dict.get('name')}")
            return {
                "status": "rejected",
                "topic_name": topic_dict.get("name"),
                "category": category,
                "should_add": False,
                "motivation_for_relevance": motivation_for_relevance,
                "capacity_guard": decision,
            }

        elif action == "replace":
            id_to_remove = decision.get("id_to_remove")
            if not id_to_remove:
                problem_log(
                    problem="CapacityGuard replace missing id_to_remove",
                    topic=topic_dict.get("name", "unknown"),
                    details={"guard_action": action, "guard_motivation": decision.get("motivation")},
                )
                trk.put("status", "rejected")
                trk.put("reject_category", str(category))
                trk.put("reject_failure_cat", "capacity_guard_replace_missing_id")
                trk.set_id("none")
                master_log(f"Topic rejected by capacity guard (missing id_to_remove) | name={topic_dict.get('name')}")
                return {
                    "status": "rejected",
                    "topic_name": topic_dict.get("name"),
                    "category": category,
                    "should_add": False,
                    "motivation_for_relevance": motivation_for_relevance,
                    "capacity_guard": decision,
                }

            # Remove the weakest topic suggested by guard, then proceed with creation
            try:
                run_cypher("MATCH (t:Topic {id: $id}) DETACH DELETE t", {"id": id_to_remove})
                master_log(f"Capacity replace | removed={id_to_remove} | adding={topic_dict.get('id')}")
            except Exception as e:
                problem_log(
                    problem="CapacityGuard replace deletion failed",
                    topic=topic_dict.get("name", "unknown"),
                    details={"id_to_remove": id_to_remove, "error": str(e)},
                )
                raise
    except Exception:
        # Fail-open on guard issues to avoid blocking normal adds due to guard errors.
        logger.exception("Capacity guard encountered an error; proceeding without guard enforcement.")
    # ---- END CAPACITY GUARD ----

    # Insert into DB via graph_utils
    created_node = create_topic_node(topic_dict)
    # Prefer graph element_id (stable within DB) for event identity; fallback to property id
    event_id = created_node.get("element_id") or created_node.get("id")
    if not event_id:
        raise ValueError("create_topic_node returned node without usable id (element_id or id)")
    trk.put("status", "success")
    trk.set_id(event_id)

    master_log(f"Topic added | name={topic_dict['name']} | category={category} | importance={topic_dict['importance']}", added_node=1)
    return dict(created_node)

