"""
Minimal Neo4j database driver utility for Argos Graph.
Centralized connection point for all Neo4j operations.
"""
import os
from typing import List, Dict, Any, Optional, TypeVar, cast
from neo4j import GraphDatabase, basic_auth, Driver
from utils import app_logging
from .models import Neo4jRecord, TopicNode, ArticleNode, CountResult, IdResult, NodeExistsResult

T = TypeVar('T', bound=Dict[str, Any])

logger = app_logging.get_logger(__name__)

NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "argosgraph")

def connect_graph_db() -> Driver:
    """
    Creates and returns a Neo4j driver object using config from environment variables or defaults.
    Checks if the target database exists; if not, tries to create it (admin required).
    Returns:
        neo4j.Driver: Neo4j driver instance
    Raises:
        RuntimeError: If connection fails or database cannot be created
    """
    try:
        # Suppress noisy warnings from the Neo4j Python driver unless explicitly enabled
        app_logging.getLogger("neo4j").setLevel(app_logging.ERROR)
        app_logging.getLogger("neo4j.io").setLevel(app_logging.ERROR)
        app_logging.getLogger("neo4j.pool").setLevel(app_logging.ERROR)
        logger.debug(f"Connecting to Neo4j at {NEO4J_URI} as user '{NEO4J_USER}' (database: '{NEO4J_DATABASE}')")
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD)
        )
        # First, check if the database exists (connect to system db)
        with driver.session(database="system") as sys_session:
            logger.debug(f"Checking if database '{NEO4J_DATABASE}' exists...")
            dbs = [r["name"] for r in sys_session.run("SHOW DATABASES")]
            if NEO4J_DATABASE not in dbs:
                logger.warning(f"Database '{NEO4J_DATABASE}' does not exist. Attempting to create it...")
                sys_session.run(f"CREATE DATABASE {NEO4J_DATABASE}")
                logger.info(f"CREATE DATABASE command issued for '{NEO4J_DATABASE}'. Waiting for database to be online...")
                # ---
                # Neo4j may take a few seconds to bring a new database online. If you try to connect immediately,
                # you may get routing errors. We poll SHOW DATABASES until the db is online or timeout is reached.
                # ---
                import time
                max_wait = 10  # seconds
                interval = 0.5 # seconds
                waited = 0.0
                while waited < max_wait:
                    dbs_info = list(sys_session.run("SHOW DATABASES"))
                    db_status = None
                    for r in dbs_info:
                        if r["name"] == NEO4J_DATABASE:
                            db_status = r.get("currentStatus") or r.get("status")
                            break
                    logger.info(f"Waited {waited:.1f}s: Database '{NEO4J_DATABASE}' status: {db_status}")
                    if db_status == "online":
                        break
                    time.sleep(interval)
                    waited += interval
                else:
                    logger.error(f"Database '{NEO4J_DATABASE}' did not become online after {max_wait}s.")
                    raise RuntimeError(f"Database '{NEO4J_DATABASE}' did not become online after {max_wait}s.")
        # Now test connection on the specified database
        with driver.session(database=NEO4J_DATABASE) as session:
            session.run("RETURN 1")
        logger.debug(f"✅ Successfully connected to Neo4j database '{NEO4J_DATABASE}'!")
        return driver
    except Exception as e:
        logger.error(f"❌ Failed to connect to Neo4j or create database: {e}", exc_info=True)
        raise RuntimeError(f"Neo4j connection error: {e}")

def run_cypher(query: str, params: Optional[Dict[str, Any]] = None, database: Optional[str] = None) -> List[Neo4jRecord]:
    """
    Run a Cypher query against the specified (or default) Neo4j database and return results as a list of dicts.
    
    Args:
        query: Cypher query string
        params: Query parameters (optional)
        database: Database name (defaults to NEO4J_DATABASE)
    
    Returns:
        List of dictionaries containing query results. Keys depend on the RETURN clause.
        
    Example:
        # Returns [{'n.id': 'topic1', 'n.name': 'EUR/USD'}]
        results = run_cypher("MATCH (n:Topic) RETURN n.id, n.name LIMIT 1")
        
        # For node queries, use specialized methods below for better typing
    """
    driver = connect_graph_db()
    db = database or NEO4J_DATABASE
    try:
        with driver.session(database=db) as session:
            # Normalize params to ensure logging never errors on None
            p = params or {}
            result = session.run(query, p)
            records = [dict(r) for r in result]
            # Log query as before
            def _log_query(query, params, rows):
                def truncate(val):
                    if isinstance(val, str) and len(val) > 100:
                        return val[:100] + '...'
                    return val
                params_str = "{\n" + ",\n".join(f"  {k}: {truncate(v)!r}" for k, v in params.items()) + "\n}"
                logger.debug("Query executed:\nQUERY:\n%s\nPARAMS:\n%s\nROWS: %s", query.strip(), params_str, rows)
            _log_query(query, p, len(records))
            # Log Neo4j property warnings in a readable way
            notifications = getattr(result, 'notifications', [])
            for n in notifications:
                if n.get('code', '').startswith('Neo.ClientNotification.Statement.UnknownPropertyKeyWarning'):
                    prop = n.get('title', 'Unknown property')
                    desc = n.get('description', '')
                    query_preview = query.strip().replace('\n', ' ')
                    if len(query_preview) > 120:
                        query_preview = query_preview[:120] + '...'
                    location = n.get('position', {})
                    line = location.get('line')
                    col = location.get('column')
                    # Demote to DEBUG to suppress noise in normal runs
                    logger.debug("[NEO4J PROPERTY WARNING]\nProperty: %s\nQuery: %s\nDescription: %s\nLocation: line %s, column %s", prop, query_preview, desc, line, col)
            return records
    except Exception as e:
        logger.error(f"Cypher query failed: {e}", exc_info=True)
        raise


# Specialized typed query methods for better developer experience

def get_topics(limit: Optional[int] = None, status: Optional[str] = None) -> List[TopicNode]:
    """
    Get topic nodes with strong typing.
    
    Args:
        limit: Maximum number of topics to return
        status: Filter by status ('active', 'hidden', etc.)
    
    Returns:
        List of TopicNode dictionaries with known structure
    """
    query = "MATCH (t:Topic)"
    params: Dict[str, Any] = {}
    
    if status:
        query += " WHERE t.status = $status"
        params['status'] = status
    
    query += " RETURN t"
    
    if limit:
        query += " LIMIT $limit"
        params['limit'] = limit
    
    results = run_cypher(query, params)
    return [cast(TopicNode, r['t']) for r in results]


def get_topic_by_id(topic_id: str) -> Optional[TopicNode]:
    """
    Get a single topic by ID with strong typing.
    
    Args:
        topic_id: The topic ID to find
    
    Returns:
        TopicNode dictionary or None if not found
    """
    results = run_cypher("MATCH (t:Topic {id: $id}) RETURN t", {"id": topic_id})
    return cast(TopicNode, results[0]['t']) if results else None


def get_articles(limit: Optional[int] = None, topic_id: Optional[str] = None) -> List[ArticleNode]:
    """
    Get article nodes with strong typing.
    
    Args:
        limit: Maximum number of articles to return
        topic_id: Filter by topic relationship
    
    Returns:
        List of ArticleNode dictionaries with known structure
    """
    if topic_id:
        query = "MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id}) RETURN a"
        params = {"topic_id": topic_id}
    else:
        query = "MATCH (a:Article) RETURN a"
        params = {}
    
    if limit:
        query += " LIMIT $limit"
        params['limit'] = limit
    
    results = run_cypher(query, params)
    return [cast(ArticleNode, r['a']) for r in results]


def count_nodes(label: str, where_clause: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> int:
    """
    Count nodes with a specific label.
    
    Args:
        label: Node label (e.g., 'Topic', 'Article')
        where_clause: Optional WHERE condition (without 'WHERE' keyword)
        params: Parameters for the WHERE clause
    
    Returns:
        Count of matching nodes
        
    Example:
        topic_count = count_nodes('Topic')
        active_topics = count_nodes('Topic', 'n.status = $status', {'status': 'active'})
    """
    query = f"MATCH (n:{label})"
    if where_clause:
        query += f" WHERE {where_clause}"
    query += " RETURN count(n) as count"
    
    results = run_cypher(query, params or {})
    return cast(CountResult, results[0])['count']


def node_exists(label: str, property_key: str, property_value: Any) -> bool:
    """
    Check if a node exists with the given property.
    
    Args:
        label: Node label (e.g., 'Topic', 'Article')
        property_key: Property name to check (e.g., 'id', 'name')
        property_value: Property value to match
    
    Returns:
        True if node exists, False otherwise
        
    Example:
        exists = node_exists('Topic', 'id', 'eurusd')
    """
    query = f"MATCH (n:{label} {{{property_key}: $value}}) RETURN count(n) > 0 as exists"
    results = run_cypher(query, {"value": property_value})
    return cast(NodeExistsResult, results[0])['exists']


def get_node_ids(label: str, limit: Optional[int] = None) -> List[str]:
    """
    Get list of node IDs for a given label.
    
    Args:
        label: Node label (e.g., 'Topic', 'Article')
        limit: Maximum number of IDs to return
    
    Returns:
        List of node ID strings
    """
    query = f"MATCH (n:{label}) RETURN n.id as id"
    if limit:
        query += " LIMIT $limit"
        params = {"limit": limit}
    else:
        params = {}
    
    results = run_cypher(query, params)
    return [cast(IdResult, r)['id'] for r in results if r.get('id')]


def execute_write(query: str, params: Optional[Dict[str, Any]] = None) -> List[Neo4jRecord]:
    """
    Execute a write query (CREATE, MERGE, UPDATE, DELETE) with explicit transaction.
    
    Args:
        query: Cypher write query
        params: Query parameters
    
    Returns:
        Query results (if any)
        
    Note:
        Use this for write operations to make intent clear.
        For read queries, use run_cypher() or the specialized get_* methods.
    """
    return run_cypher(query, params)
