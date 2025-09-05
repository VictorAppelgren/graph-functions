from graph_db.db_driver import run_cypher
from utils import minimal_logging
logger = minimal_logging.get_logger(__name__)

def remove_article_from_graph(article_id: str) -> None:
    """
    Removes an Article node and all its relationships from the graph DB.
    """
    if not article_id:
        raise ValueError("article_id is required")
    cypher = """
    MATCH (a:Article {id: $article_id}) DETACH DELETE a
    """
    run_cypher(cypher, {"article_id": article_id})
    logger.info(f"Removed article {article_id} from graph.")
