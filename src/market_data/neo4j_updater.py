"""
Neo4j update functions for market data.
Draft implementation - not used in test mode.
"""

import os
import sys
import json
from datetime import date
from typing import Dict, Any

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.graph.neo4j_client import execute_write, run_cypher
from .models import MarketSnapshot, Neo4jUpdate, AssetClass
from .market_data_mapper import map_to_neo4j_properties
from utils import app_logging

logger = app_logging.get_logger(__name__)


def create_neo4j_update_draft(topic_id: str, snapshot: MarketSnapshot) -> Neo4jUpdate:
    """
    Create a Neo4j update object with standardized market_data_ properties.
    """
    # Map raw data to standardized Neo4j properties
    neo4j_properties = map_to_neo4j_properties(snapshot.data)
    
    # Add metadata
    neo4j_properties.update({
        "market_data_ticker": snapshot.ticker,
        "market_data_asset_class": snapshot.asset_class.value,
        "market_data_last_updated": str(snapshot.updated_at),
        "market_data_source": snapshot.source
    })
    
    return Neo4jUpdate(
        topic_id=topic_id,
        resolved_ticker=snapshot.ticker,
        asset_class=snapshot.asset_class,
        market_data=snapshot.data,  # Keep original for display
        last_market_update=str(snapshot.updated_at),
        update_type="MERGE",
        properties=neo4j_properties  # Standardized properties for Neo4j
    )


def preview_neo4j_update(update: Neo4jUpdate) -> str:
    """
    Preview what would be written to Neo4j.
    """
    lines = [
        f"=== NEO4J UPDATE PREVIEW ===",
        f"Topic ID: {update.topic_id}",
        f"Ticker: {update.resolved_ticker}",
        f"Asset Class: {update.asset_class.value}",
        f"Update Date: {update.last_market_update}",
        "",
        "Market Data Fields:",
    ]
    
    for field, value in update.market_data.items():
        lines.append(f"  {field}: {value}")
    
    lines.extend([
        "",
        "Cypher Query (DRAFT):",
        f"MATCH (t:Topic {{id: '{update.topic_id}'}})",
        f"SET t.resolved_ticker = '{update.resolved_ticker}',",
        f"    t.asset_class = '{update.asset_class.value}',",
        f"    t.market_data = '{json.dumps(update.market_data)}',",
        f"    t.last_market_update = '{update.last_market_update}'"
    ])
    
    return "\n".join(lines)


def apply_neo4j_update(update: Neo4jUpdate) -> bool:
    """
    Apply the Neo4j update to the database with market_data_ properties.
    """
    try:
        # Build SET clause for all market data properties
        set_clauses = []
        params = {"topic_id": update.topic_id}
        
        for prop_name, prop_value in update.properties.items():
            param_name = prop_name.replace("market_data_", "").replace("_", "")
            set_clauses.append(f"t.{prop_name} = ${param_name}")
            params[param_name] = prop_value
        
        set_clause = ", ".join(set_clauses)
        
        cypher = f"""
        MATCH (t:Topic {{id: $topic_id}})
        SET {set_clause}
        RETURN t.id as topic_id, t.name as topic_name
        """
        
        logger.info(f"🔄 Updating Neo4j topic {update.topic_id} with {len(update.properties)} market data properties")
        
        result = execute_write(cypher, params)
        
        if result and len(result) > 0:
            logger.info(f"✅ Successfully updated Neo4j topic: {result[0]['topic_name']}")
            return True
        else:
            logger.warning(f"⚠️  Topic {update.topic_id} not found in Neo4j")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to update Neo4j: {e}")
        return False


def load_market_data_from_neo4j(topic_id: str) -> Dict[str, Any]:
    """
    Load market_data_ properties from Neo4j and convert to display format.
    """
    from .market_data_mapper import extract_market_data_from_neo4j
    
    query = """
        MATCH (t:Topic {id: $topic_id})
        RETURN properties(t) as all_properties
    """
    
    result = run_cypher(query, {"topic_id": topic_id})
    
    if not result or len(result) == 0:
        logger.warning(f"Topic {topic_id} not found in Neo4j")
        return {}
    
    all_props = result[0]["all_properties"]
    
    # Extract market data properties
    market_data = extract_market_data_from_neo4j(all_props)
    
    if not market_data:
        logger.info(f"No market data found for topic {topic_id}")
        return {}
    
    # Get metadata
    ticker = all_props.get("market_data_ticker", "Unknown")
    asset_class = all_props.get("market_data_asset_class", "unknown")
    last_update = all_props.get("market_data_last_updated", "Unknown")
    source = all_props.get("market_data_source", "unknown")
    
    logger.info(f"✅ Loaded {len(market_data)} market data fields for {topic_id}")
    
    return {
        "ticker": ticker,
        "asset_class": asset_class,
        "market_data": market_data,
        "last_update": last_update,
        "source": source
    }
