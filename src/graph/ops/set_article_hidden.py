from graph.neo4j_client import run_cypher
from utils import app_logging
logger = app_logging.get_logger(__name__)

def set_article_hidden(article_id: str) -> None:
    """
    Sets the status of an Article node to 'hidden' in the graph DB.
    """
    if not article_id:
        raise ValueError("article_id is required")
    cypher = """
    MATCH (a:Article {id: $article_id})
    SET a.status = 'hidden'
    """
    run_cypher(cypher, {"article_id": article_id})
    logger.info(f"Set article {article_id} to hidden.")
