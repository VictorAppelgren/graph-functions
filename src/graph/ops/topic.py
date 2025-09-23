from src.graph.neo4j_client import connect_graph_db

from typing import Any, TYPE_CHECKING
from datetime import datetime, timezone

from src.graph.neo4j_client import run_cypher
from src.graph.models import Neo4jRecord
from utils import app_logging
from events.classifier import EventClassifier, EventType
from src.articles.load_article import load_article
from src.articles.article_text_formatter import extract_text_from_json_article
from src.observability.pipeline_logging import problem_log, Problem, master_log, ProblemDetailsModel
from src.graph.policies.topic import classify_topic_category, classify_topic_importance, check_topic_relevance
from src.analysis.policies.query_generator import create_wide_query
from src.demo.llm.topic_capacity_guard_llm import decide_topic_capacity

if TYPE_CHECKING:
    from src.analysis.policies.topic_proposal import TopicProposal

logger = app_logging.get_logger(__name__)


def add_topic(article_id: str, suggested_names: list[str] = []) -> dict[str, str] | None:
    """
    Uses an LLM to propose a new Topic for the graph based on the article.
    Returns the created topic as a dict.
    """

    # Initialize variables to prevent UnboundLocalError
    p = None
    
    # Minimal event tracking
    tracker = EventClassifier(EventType.ADD_TOPIC)
    tracker.put_many(source_article_id=article_id, suggested_names=suggested_names)
    # Load the article
    article_json = load_article(article_id)
    logger.debug(
        f"Sample article_json: {str(article_json)[:400]}{'...' if len(str(article_json)) > 400 else ''}"
    )

    # Extract formatted text for LLMs
    if article_json:
        article_text = extract_text_from_json_article(article_json)
        logger.debug(
            f"Sample article_text: {article_text[:400]}{'...' if len(article_text) > 400 else ''}"
        )

        # Propose new topic using formatted text (lazy import to avoid circulars)
        from src.analysis.policies.topic_proposal import propose_topic

        existing_topics = get_all_topics(fields=["id", "name", "importance", "last_updated"])

        topic_proposal = propose_topic(article_text, suggested_names, existing_topics=existing_topics)
        if not topic_proposal:
            # Unified rejection: treat as gating fail, but with special details
            p = ProblemDetailsModel(category=None, failure_category="proposal_null")
            problem_log(
                Problem.TOPIC_REJECTED,
                topic=(
                    article_json.get("title", "unknown")
                    if "article_json" in locals()
                    else "unknown"
                ),
                details=p,
            )
            tracker.put_many(status="rejected", reject_category=str(None), reject_failure_cat="proposal_null", llm_topic_proposal_raw="")
            tracker.set_id("none")
            master_log(
                f"Topic rejected | name={article_json.get('title', 'unknown') if 'article_json' in locals() else 'unknown'} | category=None | failure=proposal_null"
            )
            return {
                "status": "rejected",
                "topic_name": (
                    article_json.get("title", "unknown")
                    if "article_json" in locals()
                    else "unknown"
                ),
                "category": "",
                "failure_category": "proposal_null",
                "reason": "proposal_null",
            }
        # Attach raw proposal immediately so gating rejections are traceable
        tracker.put("llm_topic_proposal_raw", topic_proposal.model_dump())

        # Topic gating: category + trading relevance before any DB write
        category, motivation_for_category = classify_topic_category(
            topic_id=topic_proposal.id,
            topic_name=topic_proposal.name,
            topic_type=topic_proposal.type,
            motivation=topic_proposal.motivation,
            article_summary=article_text,
        )
        should_add, motivation_for_relevance = check_topic_relevance(
            topic_id=topic_proposal.id,
            topic_name=topic_proposal.name,
            topic_type=topic_proposal.type,
            motivation=topic_proposal.motivation,
            article_summary=article_text,
            context=article_text,
        )
        tracker.put_many(topic_category=category, topic_category_motivation=motivation_for_category, should_add=should_add, motivation_for_relevance=motivation_for_relevance)

        if not should_add:
            p = ProblemDetailsModel(category=category, should_add=should_add, should_add_motivation=motivation_for_relevance)
            problem_log(
                problem=Problem.TOPIC_REJECTED,
                topic=topic_proposal.name,
                details=p,
            )
            tracker.put_many(status="rejected", reject_category=str(category), reject_failure_cat="relevance_gate_reject")
            tracker.set_id("none")
            # Do not crash on legitimate rejection; log and return minimal status
            master_log(
                f"Topic rejected | name={topic_proposal.name} | category={category} | failure=relevance_gate_reject"
            )
            return {
                "status": "rejected",
                "topic_name": topic_proposal.name,
                "category": category,
                "should_add": should_add,
                "motivation_for_relevance": motivation_for_relevance,
            }

        # Generate wide query for this topic using the same formatted text
        query = create_wide_query(article_text)
        logger.debug(
            f"Sample query: {query['query'][:400]}{'...' if len(query['query']) > 400 else ''}"
        )
        topic_proposal.query = query["query"]

        # Classify topic importance (1..5) using LLM helper and set scheduling props
        topic_importance, topic_importance_rationale = classify_topic_importance(
            topic_name=topic_proposal.name,
            topic_type=topic_proposal.type,
            context=article_text,
        )
        # If LLM flags this topic for removal, reject and do not persist
        if isinstance(topic_importance, str) and topic_importance.upper() == "REMOVE":
            p = ProblemDetailsModel(failure_category="importance_remove", rationale=topic_importance_rationale)
            problem_log(
                problem=Problem.TOPIC_REJECTED,
                topic=topic_proposal.name,
                details=p,
            )
            tracker.put_many(status="rejected", reject_category=str(category), reject_failure_cat="importance_remove")
            tracker.set_id("none")
            master_log(
                f"Topic rejected | name={topic_proposal.name} | category={category} | failure=importance_remove"
            )
            return {
                "status": "rejected",
                "topic_name": topic_proposal.name,
                "category": category,
                "should_add": False,
                "motivation_for_relevance": motivation_for_relevance,
                "failure_category": "importance_remove",
            }

        # Coerce numeric string importance to int
        if isinstance(topic_importance, str) and topic_importance.isdigit():
            topic_importance = int(topic_importance)
        if not isinstance(topic_importance, int):
            raise ValueError(
                f"Classifier returned non-numeric importance: {topic_importance}"
            )

        topic_proposal.importance = topic_importance
        topic_proposal.importance_rationale = topic_importance_rationale
        topic_proposal.last_updated = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )

        # Attach full reasoning artifacts (IDs only remain in inputs)
        tracker.put_many(llm_topic_proposal_raw=topic_proposal.model_dump(), generated_query=query, importance_classification=topic_importance, importance_classification_rationale=topic_importance_rationale)

        # ---- DEMO CAPACITY GUARD (always run) ----
        try:
            existing_topics = get_all_topics(
                fields=["id", "name", "type", "importance", "last_updated"]
            )

            candidate_topic = {
                "id": topic_proposal.id,
                "name": topic_proposal.name,
                "importance": topic_proposal.importance,
                "category": category,
                "motivation": topic_proposal.motivation,
            }

            decision = decide_topic_capacity(
                candidate_topic=candidate_topic,
                existing_topics=existing_topics,
                test=False,
            )
            logger.info("capacity_guard decision: %s", decision)

            if decision.action == "reject":
                p = ProblemDetailsModel(article_id=topic_proposal.id, importance=topic_proposal.importance, guard_action=decision.action, guard_motivation=decision.motivation)
                problem_log(
                    problem=Problem.CAPACITY_GUARD_REJECT,
                    topic=topic_proposal.name,
                    details=p,
                )

                tracker.put_many(status="rejected", reject_category=str(category), reject_failure_cat="capacity_guard_reject")
                tracker.set_id("none")
                master_log(
                    f"Topic rejected by capacity guard | name={topic_proposal.name}"
                )
                return {
                    "status": "rejected",
                    "topic_name": topic_proposal.name,
                    "category": category,
                    "should_add": False,
                    "motivation_for_relevance": motivation_for_relevance,
                    "capacity_guard": decision,
                }

            elif decision.action == "replace":
                id_to_remove = decision.id_to_remove
                if not id_to_remove:
                    p = ProblemDetailsModel(guard_action=decision.action, guard_motivation=decision.motivation)
                    problem_log(
                        problem=Problem.CAPACITY_GUARD_REPLACE_MISSING_ID_TO_REMOVE,
                        topic=topic_proposal.name,
                        details=p
                    )
                    tracker.put_many(status="rejected", reject_category=str(category), reject_failure_cat="capacity_guard_replace_missing_id")
                    tracker.set_id("none")
                    master_log(
                        f"Topic rejected by capacity guard (missing id_to_remove) | name={topic_proposal.name}"
                    )
                    return {
                        "status": "rejected",
                        "topic_name": topic_proposal.name,
                        "category": category,
                        "should_add": False,
                        "motivation_for_relevance": motivation_for_relevance,
                        "capacity_guard": decision,
                    }

                # Remove the weakest topic suggested by guard, then proceed with creation
                try:
                    run_cypher(
                        "MATCH (t:Topic {id: $id}) DETACH DELETE t", {"id": id_to_remove}
                    )
                    master_log(
                        f"Capacity replace | removed={id_to_remove} | adding={topic_proposal.id}"
                    )
                except Exception as e:
                    p = ProblemDetailsModel(id_to_remove=id_to_remove, error=str(e))
                    problem_log(
                        problem=Problem.CAPACITY_GUARD_REPLACE_DELETION_FAILED,
                        topic=topic_proposal.name,
                        details=p,
                    )
                    raise
        except Exception:
            # Fail-open on guard issues to avoid blocking normal adds due to guard errors.
            logger.exception(
                "Capacity guard encountered an error; proceeding without guard enforcement."
            )
        # ---- END CAPACITY GUARD ----

        # Insert into DB via graph_utils
        created_topic = create_topic(topic_proposal)
        # Prefer graph element_id (stable within DB) for event identity; fallback to property id
        event_id = created_topic.get("element_id") or created_topic.get("id")
        if not event_id:
            raise ValueError(
                "create_topic_topic returned topic without usable id (element_id or id)"
            )
        tracker.put("status", "success")
        tracker.set_id(event_id)

        master_log(
            f"Topic added | name={topic_proposal.name} | category={category} | importance={topic_proposal.importance}",
            topics_created=1,
        )
        return created_topic
    
    else:
        return None


def get_topic_by_id(topic_id: str) -> dict[str, str]:
    """
    Fetch the full Topic topic (all properties) from the Neo4j database by id.
    Returns:
        Dict: topic dict with all properties, or raises RuntimeError if not found.
    """
    logger.info(
        f" Called: Fetching full Topic topic with id='{topic_id}' from Neo4j..."
    )
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            query = "MATCH (n:Topic {id: $id}) RETURN n"
            logger.info(f" Running query: {query} with id={topic_id}")
            result = session.run(query, {"id": topic_id})
            record = result.single()
            if not record:
                logger.warning(f" topic with id '{topic_id}' not found.")
                raise RuntimeError(f"topic with id '{topic_id}' not found.")
            topic_props = dict(record["n"])
            preview = str(topic_props)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            logger.info(f" Fetched topic: {preview}")
            return topic_props
    except Exception as e:
        logger.error(f" Failed to fetch topic from Neo4j: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch topic from Neo4j: {e}")


def get_topic_id_by_name(name: str) -> str:
    """
    Resolve a Topic topic's canonical id from its display name.

    Args:
        name (str): Topic.name (e.g., "EURUSD").

    Returns:
        str: Topic.id (e.g., "eurusd").

    Raises:
        RuntimeError: If no topic is found with the provided name.
    """
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")

    logger.info(f"Resolving topic id by name: name='{name}'")
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            query = "MATCH (n:Topic {name: $name}) RETURN n.id AS id"
            logger.info(f"Running query: {query} | params={{'name': '{name}'}}")
            result = session.run(query, {"name": name})
            record = result.single()
            if not record or not record.get("id"):
                logger.error(f"No topic found with name '{name}'")
                raise RuntimeError(f"No topic found with name '{name}'")
            topic_id = str(record["id"])
            logger.info(f"Resolved topic name '{name}' -> id '{topic_id}'")
            return topic_id
    except Exception as e:
        logger.error(f"Failed to resolve topic id by name: {e}", exc_info=True)
        raise RuntimeError(f"Failed to resolve topic id by name: {e}")


def check_if_topic_exists(topic_id: str) -> bool:
    """
    Check if a topic with the given ID exists in the database.

    Args:
        topic_id: String ID of the topic to check

    Returns:
        bool: True if topic exists, False otherwise
    """
    driver = connect_graph_db()
    with driver.session(database="argosgraph") as session:
        cypher = "MATCH (n:Topic {id: $id}) RETURN n LIMIT 1"
        result = session.run(cypher, {"id": topic_id})
        exists = result.single() is not None

        if exists:
            logger.debug(f"topic with ID '{topic_id}' already exists in the database.")
        else:
            logger.debug(f"topic with ID '{topic_id}' does not exist in the database.")

        return exists


def get_topic_if_exists(topic_id: str) -> dict[str, str] | None:
    """
    Get a topic with the given ID if it exists in the database.

    Args:
        topic_id: String ID of the topic to retrieve

    Returns:
        dict: topic data if found, None otherwise
    """
    driver = connect_graph_db()
    with driver.session(database="argosgraph") as session:
        cypher = "MATCH (n:Topic {id: $id}) RETURN n LIMIT 1"
        result = session.run(cypher, {"id": topic_id})
        record = result.single()

        if record:
            topic = dict(record["n"])
            logger.debug(f"Retrieved topic with ID '{topic_id}'")
            return topic
        else:
            logger.debug(f"Failed to retrieve topic with ID '{topic_id}': Not found")
            return None


def get_all_topics(fields: list[str] = ["id", "name", "type"]) -> list[dict[str, str]]:
    """
    Fetch all current graph topics from the Neo4j database.
    Args:
        fields (list): Optional list of property names to return for each topic. Defaults to ['id', 'name', 'type'].
    Returns:
        List[Dict]: List of topic dicts with requested fields.
    Raises:
        RuntimeError: If the database query fails.
    """
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            return_clause = ", ".join([f"n.{f} AS {f}" for f in fields])
            query = f"MATCH (n:Topic) RETURN {return_clause}"
            logger.info(f" Running query: {query}")
            result = session.run(query)
            topics = [dict(record) for record in result]
            logger.info(f" Fetched {len(topics)} topic(s) from Neo4j.")
            return topics
    except Exception as e:
        logger.error(f" Failed to fetch topics from Neo4j: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch topics from Neo4j: {e}")


def get_topic_analysis_field(topic_id: str, field: str) -> Any:
    """
    Fetch the value of the specified analysis field for a topic topic.
    Logs clearly if missing, but does NOT raise or crash.
    Returns the string value or an empty string if not found.
    """
    q = f"""
    MATCH (n:Topic {{id:$id}})
    RETURN n.{field} AS analysis
    """
    rows: list[Neo4jRecord] = run_cypher(q, {"id": topic_id}) or []
    if not rows:
        return None
    return rows[0]["analysis"]


def remove_topic(topic_id: str, reason: str | None = None) -> dict[str, str]:
    """
    Removes a Topic topic (and all its relationships) by property id.

    Args:
        topic_id: The Topic topic's `id` property value.
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
        ValueError if topic_id is invalid or topic is not found.
    """
    if not isinstance(topic_id, str) or not topic_id.strip():
        raise ValueError("topic_id must be a non-empty string")

    # Event Classifier
    tracker = EventClassifier(EventType.REMOVE_TOPIC)
    tracker.put("target_topic_id", topic_id)
    if reason is not None:
        tracker.put("reason", reason)

    # 1) Fetch minimal topic details (fail fast if not found)
    q_fetch = (
        "MATCH (t:Topic {id: $id}) "
        "RETURN elementId(t) AS element_id, t.name AS name, t.importance AS importance, labels(t) AS labels"
    )
    res = run_cypher(q_fetch, {"id": topic_id})
    if not res:
        tracker.put("status", "not_found")
        tracker.set_id("none")
        raise ValueError(f"Topic topic with id '{topic_id}' not found")

    row = res[0]
    element_id = row.get("element_id")
    name = row.get("name")
    importance = row.get("importance")
    labels = row.get("labels")

    tracker.put_many(topic_name=str(name), topic_importance=str(importance), topic_labels={"labels": labels} if isinstance(labels, list) else {"labels": []})

    # 2) Count attached relationships (for reporting)
    q_count = (
        "MATCH (t:Topic {id: $id}) "
        "OPTIONAL MATCH (t)-[r]-() "
        "RETURN count(r) AS rel_count"
    )
    count_res = run_cypher(q_count, {"id": topic_id})
    rel_count = int(count_res[0]["rel_count"]) if count_res else 0
    tracker.put("attached_relationships", str(rel_count))

    # 3) Delete the topic and detach all rels
    q_delete = "MATCH (t:Topic {id: $id}) " "DETACH DELETE t"
    run_cypher(q_delete, {"id": topic_id})

    tracker.put("status", "success")
    tracker.set_id(element_id or topic_id)

    logger.info(
        f"Removed Topic topic: name={name} id={topic_id} element_id={element_id} rels={rel_count}"
    )
    master_log(
        f"Topic removed | name={name} | id={topic_id} | element_id={element_id} | rels={rel_count} | reason={(reason or '')[:200]}",
        removes_topic=1,
    )
    return {
        "status": "deleted",
        "id": topic_id,
        "name": str(name),
        "importance": str(importance),
        "element_id": str(element_id),
        "deleted_relationships": str(rel_count),
        "reason": str(reason),
    }


def create_topic(topic_proposal: "TopicProposal") -> dict[str, str]:
    """
    Create a Topic in the Neo4j graph with the provided properties.
    If a topic with the same ID already exists, it will NOT be overwritten.

    Args:
        topic_dict: Dictionary containing all required topic properties including 'id'

    Returns:
        dict: Created or existing topic data
    """
    # Check if topic already exists
    if check_if_topic_exists(topic_proposal.id):
        logger.info(f"topic with ID '{topic_proposal.id}' already exists, skipping creation.")

        # Fetch existing topic and return it
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            cypher = "MATCH (n:Topic {id: $id}) RETURN n, elementId(n) AS eid"
            result = session.run(cypher, {"id": topic_proposal.id})
            record = result.single()
            if record:
                topic_dict = dict(record["n"])
                topic_dict["element_id"] = record["eid"]
                return topic_dict
            else:
                # This shouldn't happen if check_if_topic_exists returned True
                logger.error(f"topic existence check inconsistency for ID '{topic_proposal.id}'")
                raise RuntimeError(
                    f"topic existence check inconsistency for ID '{topic_proposal.id}'"
                )

    # Create the topic
    driver = connect_graph_db()
    with driver.session(database="argosgraph") as session:
 
        # Convert all properties into a params dict for Cypher
        params = {"props": topic_proposal.model_dump()}

        # Create topic with all properties from topic_dict
        cypher = "CREATE (n:Topic $props) RETURN n, elementId(n) AS eid"
        result = session.run(cypher, params)
        record = result.single()

        if record:
            topic_dict = dict(record["n"])
            topic_dict["element_id"] = record["eid"]
            logger.info(
                f"Created new Topic topic: {topic_dict.get('name')} (id={topic_proposal.id}, element_id={topic_dict['element_id']})"
            )
            return topic_dict
        else:
            logger.error(f"Failed to create Topic topic with ID '{topic_proposal.id}'")
            raise RuntimeError(f"Failed to create Topic topic with ID '{topic_proposal.id}'")
