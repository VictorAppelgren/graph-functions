"""
Saves updated analysis fields to the graph DB for a topic node.
"""

from src.graph.neo4j_client import run_cypher

from utils import app_logging
from src.observability.pipeline_logging import master_log

logger = app_logging.get_logger(__name__)


def save_analysis(topic_id: str, field: str, text: str) -> None:
    """
    Writes a single updated analysis field (from the LLM) to the topic in the graph DB, updating the timestamp as needed.
    Args:
        topic_id (str): The topic ID.
        field (str): The analysis field name.
        text (str): The analysis text.
    """
    if not topic_id or not field:
        raise ValueError("topic_id and field are required")
    logger.info(f"Saving analysis for topic_id={topic_id} field={field}")
    # Fetch before
    fetch_query = """
        MATCH (t:Topic {id: $topic_id})
        RETURN t { .* } AS topic
    """
    before = run_cypher(fetch_query, {"topic_id": topic_id})
    before_sample = str(before[0]["topic"])[:400] if before else ""
    # Update
    update_query = f"""
        MATCH (t:Topic {{id: $topic_id}})
        SET t.{field} = $text, t.last_updated = datetime()
    """
    params = {"topic_id": topic_id, "text": text}
    run_cypher(update_query, params)
    # Fetch after
    after = run_cypher(fetch_query, {"topic_id": topic_id})
    after_sample = str(after[0]["topic"])[:400] if after else ""
    logger.info(
        f"Saved analysis for topic_id={topic_id} field={field} before_sample={before_sample} after_sample={after_sample}"
    )

    master_log(
        f'Saved analysis | {topic_id} | field "{field}" len={len(str(text))}',
        rewrites_saved=1,
    )
