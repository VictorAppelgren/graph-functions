"""
User Strategy Operations

Save and retrieve user strategies with their topic mappings.
"""

from typing import Dict, List, Optional
from datetime import datetime
from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)


def save_user_strategy(
    user_id: str,
    strategy_id: str,
    asset: str,
    strategy_text: str,
    position_text: str,
    topic_mapping: Dict[str, List[str]]
) -> bool:
    """
    Save user strategy with topic mapping to Neo4j.
    
    Args:
        user_id: User ID
        strategy_id: Unique strategy ID
        asset: Asset name (e.g., "EURUSD")
        strategy_text: Strategy description
        position_text: Position details
        topic_mapping: {"primary": [...], "drivers": [...], "correlated": [...]}
    
    Returns:
        True if successful
    """
    try:
        # Create or update UserStrategy node
        query = """
        MERGE (s:UserStrategy {id: $strategy_id})
        SET s.user_id = $user_id,
            s.asset = $asset,
            s.strategy_text = $strategy_text,
            s.position_text = $position_text,
            s.updated_at = datetime()
        
        // Remove old topic relationships
        WITH s
        OPTIONAL MATCH (s)-[r:PRIMARY_TOPIC|DRIVER_TOPIC|CORRELATED_TOPIC]->()
        DELETE r
        
        RETURN s.id as id
        """
        
        result = run_cypher(query, {
            "strategy_id": strategy_id,
            "user_id": user_id,
            "asset": asset,
            "strategy_text": strategy_text,
            "position_text": position_text
        })
        
        if not result:
            logger.error(f"Failed to create UserStrategy node: {strategy_id}")
            return False
        
        # Create topic relationships
        for rel_type, topic_ids in topic_mapping.items():
            if not topic_ids:
                continue
            
            # Map relationship type
            rel_name = {
                "primary": "PRIMARY_TOPIC",
                "drivers": "DRIVER_TOPIC",
                "correlated": "CORRELATED_TOPIC"
            }.get(rel_type, "RELATED_TOPIC")
            
            for topic_id in topic_ids:
                rel_query = f"""
                MATCH (s:UserStrategy {{id: $strategy_id}})
                MATCH (t:Topic {{id: $topic_id}})
                MERGE (s)-[:{rel_name}]->(t)
                """
                
                run_cypher(rel_query, {
                    "strategy_id": strategy_id,
                    "topic_id": topic_id
                })
        
        logger.info(f"✅ Saved user strategy: {strategy_id} with {sum(len(v) for v in topic_mapping.values())} topics")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save user strategy: {e}")
        return False


def get_user_strategy(strategy_id: str) -> Optional[Dict]:
    """
    Load user strategy with topic mapping from Neo4j.
    
    Args:
        strategy_id: Strategy ID
    
    Returns:
        {
            "id": str,
            "user_id": str,
            "asset": str,
            "strategy_text": str,
            "position_text": str,
            "topic_mapping": {
                "primary": [...],
                "drivers": [...],
                "correlated": [...]
            }
        }
    """
    try:
        query = """
        MATCH (s:UserStrategy {id: $strategy_id})
        OPTIONAL MATCH (s)-[:PRIMARY_TOPIC]->(pt:Topic)
        OPTIONAL MATCH (s)-[:DRIVER_TOPIC]->(dt:Topic)
        OPTIONAL MATCH (s)-[:CORRELATED_TOPIC]->(ct:Topic)
        
        RETURN s.id as id,
               s.user_id as user_id,
               s.asset as asset,
               s.strategy_text as strategy_text,
               s.position_text as position_text,
               collect(DISTINCT pt.id) as primary_topics,
               collect(DISTINCT dt.id) as driver_topics,
               collect(DISTINCT ct.id) as correlated_topics
        """
        
        result = run_cypher(query, {"strategy_id": strategy_id})
        
        if not result:
            logger.warning(f"Strategy not found: {strategy_id}")
            return None
        
        data = result[0]
        
        # Filter out None values from collect()
        return {
            "id": data["id"],
            "user_id": data["user_id"],
            "asset": data["asset"],
            "strategy_text": data["strategy_text"],
            "position_text": data["position_text"],
            "topic_mapping": {
                "primary": [t for t in data["primary_topics"] if t],
                "drivers": [t for t in data["driver_topics"] if t],
                "correlated": [t for t in data["correlated_topics"] if t]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to load user strategy: {e}")
        return None


def list_user_strategies(user_id: str) -> List[Dict]:
    """
    List all strategies for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        List of strategy summaries
    """
    try:
        query = """
        MATCH (s:UserStrategy {user_id: $user_id})
        RETURN s.id as id,
               s.asset as asset,
               s.updated_at as updated_at
        ORDER BY s.updated_at DESC
        """
        
        result = run_cypher(query, {"user_id": user_id})
        return result or []
        
    except Exception as e:
        logger.error(f"Failed to list user strategies: {e}")
        return []
