"""
Minimal Neo4j database driver utility for Argos Graph.
Centralized connection point for all Neo4j operations.
"""
import os
import logging
from neo4j import GraphDatabase, basic_auth
from utils import minimal_logging

logger = minimal_logging.get_logger(__name__)

NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "argosgraph")

def connect_graph_db():
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
        logging.getLogger("neo4j").setLevel(logging.ERROR)
        logging.getLogger("neo4j.io").setLevel(logging.ERROR)
        logging.getLogger("neo4j.pool").setLevel(logging.ERROR)
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
                waited = 0
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

def run_cypher(query: str, params: dict = None, database: str = None):
    """
    Run a Cypher query against the specified (or default) Neo4j database and return results as a list of dicts.
    Args:
        query (str): Cypher query string
        params (dict): Query parameters
        database (str): Database name (defaults to NEO4J_DATABASE)
    Returns:
        list[dict]: Query results
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
