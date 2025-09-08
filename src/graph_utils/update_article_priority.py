from graph_db.db_driver import run_cypher
from utils import logging
logger = logging.get_logger(__name__)

def update_article_priority(article_id: str) -> None:
    """
    Updates the priority of an Article node in the graph DB.
    """
    if not article_id:
        raise ValueError("article_id is required")
    # Fetch current priority
    cypher_get = """
    MATCH (a:Article {id: $article_id}) RETURN a.priority AS priority
    """
    result = run_cypher(cypher_get, {"article_id": article_id})
    if not result or 'priority' not in result[0]:
        logger.error(f"Article {article_id} not found or missing priority.")
        return
    current = str(result[0]['priority'])
    next_priority = {'3': '2', '2': '1', '1': 'hidden', 'hidden': 'hidden'}.get(current, 'hidden')
    cypher_set = """
    MATCH (a:Article {id: $article_id}) SET a.priority = $priority
    """
    run_cypher(cypher_set, {"article_id": article_id, "priority": next_priority})
    logger.info(f"Lowered article {article_id} priority from {current} to {next_priority}.")
