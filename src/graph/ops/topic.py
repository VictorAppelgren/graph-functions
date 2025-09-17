from src.graph.neo4j_client import connect_graph_db

from typing import Any

from src.graph.neo4j_client import run_cypher
from src.graph.models import Neo4jRecord
from utils import app_logging
from events.classifier import EventClassifier, EventType

logger = app_logging.get_logger(__name__)


def add_topic(article_id: str, suggested_names: list[str] = []) -> dict:
    """
    Uses an LLM to propose a new Topic for the graph based on the article.
    Returns the created topic as a dict.
    """

    # Minimal event tracking
    trk = EventClassifier(EventType.ADD_TOPIC)
    trk.put("source_article_id", article_id)
    trk.put("suggested_names", suggested_names)
    # Load the article
    article_json = load_article(article_id)
    logger.debug(
        f"Sample article_json: {str(article_json)[:400]}{'...' if len(str(article_json)) > 400 else ''}"
    )

    # Extract formatted text for LLMs
    article_text = extract_text_from_json_article(article_json)
    logger.debug(
        f"Sample article_text: {article_text[:400]}{'...' if len(article_text) > 400 else ''}"
    )

    # Propose new topic topic using formatted text
    topic_dict = propose_topic_topic(article_text, suggested_names)
    if not isinstance(topic_dict, dict) or not topic_dict:
        # Unified rejection: treat as gating fail, but with special details
        problem_log(
            Problem.TOPIC_REJECTED,
            topic=(
                article_json.get("title", "unknown")
                if "article_json" in locals()
                else "unknown"
            ),
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
        master_log(
            f"Topic rejected | name={topic_dict.get('name', 'unknown')} | category={category} | failure=relevance_gate_reject"
        )
        return {
            "status": "rejected",
            "topic_name": topic_dict["name"],
            "category": category,
            "should_add": should_add,
            "motivation_for_relevance": motivation_for_relevance,
        }

    # Generate wide query for this topic using the same formatted text
    query = create_wide_query(article_text)
    logger.debug(
        f"Sample query: {query['query'][:400]}{'...' if len(query['query']) > 400 else ''}"
    )
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
        master_log(
            f"Topic rejected | name={topic_dict.get('name', 'unknown')} | category={category} | failure=importance_remove"
        )
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
        raise ValueError(
            f"Classifier returned non-numeric importance: {topic_importance}"
        )

    topic_dict["importance"] = topic_importance
    topic_dict["importance_rationale"] = topic_importance_rationale
    topic_dict["last_queried"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    # Attach full reasoning artifacts (IDs only remain in inputs)
    trk.put("llm_topic_proposal_raw", topic_dict_raw)
    trk.put("generated_query", query)
    trk.put("importance_classification", topic_importance)
    trk.put("importance_classification_rationale", topic_importance_rationale)

    # ---- DEMO CAPACITY GUARD (always run) ----
    try:
        existing_topics = get_all_topics(
            fields=["id", "name", "type", "importance", "last_updated"]
        )

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
            master_log(
                f"Topic rejected by capacity guard | name={topic_dict.get('name')}"
            )
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
                    details={
                        "guard_action": action,
                        "guard_motivation": decision.get("motivation"),
                    },
                )
                trk.put("status", "rejected")
                trk.put("reject_category", str(category))
                trk.put("reject_failure_cat", "capacity_guard_replace_missing_id")
                trk.set_id("none")
                master_log(
                    f"Topic rejected by capacity guard (missing id_to_remove) | name={topic_dict.get('name')}"
                )
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
                run_cypher(
                    "MATCH (t:Topic {id: $id}) DETACH DELETE t", {"id": id_to_remove}
                )
                master_log(
                    f"Capacity replace | removed={id_to_remove} | adding={topic_dict.get('id')}"
                )
            except Exception as e:
                problem_log(
                    problem="CapacityGuard replace deletion failed",
                    topic=topic_dict.get("name", "unknown"),
                    details={"id_to_remove": id_to_remove, "error": str(e)},
                )
                raise
    except Exception:
        # Fail-open on guard issues to avoid blocking normal adds due to guard errors.
        logger.exception(
            "Capacity guard encountered an error; proceeding without guard enforcement."
        )
    # ---- END CAPACITY GUARD ----

    # Insert into DB via graph_utils
    created_topic = create_topic_topic(topic_dict)
    # Prefer graph element_id (stable within DB) for event identity; fallback to property id
    event_id = created_topic.get("element_id") or created_topic.get("id")
    if not event_id:
        raise ValueError(
            "create_topic_topic returned topic without usable id (element_id or id)"
        )
    trk.put("status", "success")
    trk.set_id(event_id)

    master_log(
        f"Topic added | name={topic_dict['name']} | category={category} | importance={topic_dict['importance']}",
        added_topic=1,
    )
    return dict(created_topic)


def get_topic_by_id(topic_id: str) -> Dict:
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
            topic_id = record["id"]
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


def get_topic_if_exists(topic_id: str) -> dict:
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
    MATCH (n:AssetTopic {{id:$id}})
    RETURN n.{field} AS analysis
    """
    rows: list[Neo4jRecord] = run_cypher(q, {"id": topic_id}) or []
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
    trk = EventClassifier(EventType.REMOVE_topic)
    trk.put("target_topic_id", topic_id)
    if reason is not None:
        trk.put("reason", reason)

    # 1) Fetch minimal topic details (fail fast if not found)
    q_fetch = (
        "MATCH (t:Topic {id: $id}) "
        "RETURN elementId(t) AS element_id, t.name AS name, t.importance AS importance, labels(t) AS labels"
    )
    res = run_cypher(q_fetch, {"id": topic_id})
    if not res:
        trk.put("status", "not_found")
        trk.set_id("none")
        raise ValueError(f"Topic topic with id '{topic_id}' not found")

    row = res[0]
    element_id = row.get("element_id")
    name = row.get("name")
    importance = row.get("importance")
    labels = row.get("labels")

    trk.put("topic_name", str(name))
    trk.put("topic_importance", str(importance))
    trk.put(
        "topic_labels",
        {"labels": labels} if isinstance(labels, list) else {"labels": []},
    )

    # 2) Count attached relationships (for reporting)
    q_count = (
        "MATCH (t:Topic {id: $id}) "
        "OPTIONAL MATCH (t)-[r]-() "
        "RETURN count(r) AS rel_count"
    )
    count_res = run_cypher(q_count, {"id": topic_id})
    rel_count = int(count_res[0]["rel_count"]) if count_res else 0
    trk.put("attached_relationships", str(rel_count))

    # 3) Delete the topic and detach all rels
    q_delete = "MATCH (t:Topic {id: $id}) " "DETACH DELETE t"
    run_cypher(q_delete, {"id": topic_id})

    trk.put("status", "success")
    trk.set_id(element_id or topic_id)

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
        "name": name,
        "importance": importance,
        "element_id": element_id,
        "deleted_relationships": rel_count,
        "reason": reason,
    }


def create_topic(topic_dict: dict) -> dict:
    """
    Create a Topic topic in the Neo4j graph with the provided properties.
    If a topic with the same ID already exists, it will NOT be overwritten.

    Args:
        topic_dict: Dictionary containing all required topic properties including 'id'

    Returns:
        dict: Created or existing topic data
    """
    topic_id = topic_dict.get("id")
    if not topic_id:
        logger.error("Cannot create topic topic: missing 'id' in topic_dict.")
        raise ValueError("Missing required 'id' field in topic_dict")

    # Check if topic already exists
    if check_if_topic_exists(topic_id):
        logger.info(f"topic with ID '{topic_id}' already exists, skipping creation.")

        # Fetch existing topic and return it
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            cypher = "MATCH (n:Topic {id: $id}) RETURN n, elementId(n) AS eid"
            result = session.run(cypher, {"id": topic_id})
            record = result.single()
            if record:
                topic_dict = dict(record["n"])
                topic_dict["element_id"] = record["eid"]
                return topic_dict
            else:
                # This shouldn't happen if check_if_topic_exists returned True
                logger.error(f"topic existence check inconsistency for ID '{topic_id}'")
                raise RuntimeError(
                    f"topic existence check inconsistency for ID '{topic_id}'"
                )

    # Create the topic
    driver = connect_graph_db()
    with driver.session(database="argosgraph") as session:
        # Fail-fast: validate importance if present
        if "importance" in topic_dict:
            imp = topic_dict.get("importance")
            if isinstance(imp, str) and imp.isdigit():
                imp_val = int(imp)
                topic_dict["importance"] = imp_val
            else:
                imp_val = imp
            if not isinstance(imp_val, int) or imp_val not in {1, 2, 3, 4, 5}:
                raise ValueError(
                    f"Invalid importance value: {imp} (must be integer 1..5)"
                )

        # Convert all properties into a params dict for Cypher
        params = {"props": topic_dict}

        # Create topic with all properties from topic_dict
        cypher = "CREATE (n:Topic $props) RETURN n, elementId(n) AS eid"
        result = session.run(cypher, params)
        record = result.single()

        if record:
            topic_dict = dict(record["n"])
            topic_dict["element_id"] = record["eid"]
            logger.info(
                f"Created new Topic topic: {topic_dict.get('name')} (id={topic_id}, element_id={topic_dict['element_id']})"
            )
            return topic_dict
        else:
            logger.error(f"Failed to create Topic topic with ID '{topic_id}'")
            raise RuntimeError(f"Failed to create Topic topic with ID '{topic_id}'")
