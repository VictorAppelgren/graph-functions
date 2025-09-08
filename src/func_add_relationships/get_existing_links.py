from graph_db.db_driver import connect_graph_db
from utils import logging

logger = logging.get_logger(__name__)

def get_existing_links(node_id: str) -> list[dict]:
    """
    Fetch all existing topic-to-topic links for the given node_id.
    Returns list of dicts: {type, source, target}
    """
    logger.info(f"[get_existing_links] Fetching all topic-to-topic links for node_id={node_id}")
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            query = """
            MATCH (src:Topic {id: $id})-[r]->(tgt:Topic)
            RETURN type(r) AS type, src.id AS source, tgt.id AS target
            """
            logger.info(f"[get_existing_links] Running query: {query} with id={node_id}")
            result = session.run(query, {"id": node_id})
            links = [dict(record) for record in result]
            logger.info(f"[get_existing_links] Fetched {len(links)} links for node_id={node_id}")
            return links
    except Exception as e:
        logger.error(f"[get_existing_links] Failed to fetch links from Neo4j: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch links from Neo4j: {e}")
