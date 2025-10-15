"""
Topic Discovery for Custom User Analysis

Maps user's free-text asset description to actual graph topics using LLM.
"""

from typing import List, Dict
from pydantic import BaseModel
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.graph.ops.topic import get_all_topics
from src.graph.neo4j_client import run_cypher
from src.observability.pipeline_logging import master_log
from src.llm.sanitizer import run_llm_decision


class TopicMapping(BaseModel):
    """LLM output for topic discovery."""
    primary_topics: List[str]
    driver_topics: List[str]
    reasoning: str


def discover_relevant_topics(
    asset_text: str,
    strategy_text: str,
    position_text: str
) -> Dict[str, List[str]]:
    """
    Discover relevant topics from graph based on user's strategy.
    
    Returns:
        {
            "primary": ["eurusd", "dxy"],
            "drivers": ["fed_policy", "ecb_policy"],
            "correlated": ["usdjpy", "gbpusd"]
        }
    """
    master_log(f"Topic discovery started | asset={asset_text[:30]}")
    
    # Get all available topics
    all_topics = get_all_topics()
    topic_list = [{"id": t["id"], "name": t["name"]} for t in all_topics]
    
    # Build LLM prompt
    prompt = f"""You are an expert financial analyst mapping user strategies to market topics.

USER ASSET: {asset_text}

USER STRATEGY:
{strategy_text}

USER POSITION:
{position_text}

AVAILABLE TOPICS (id | name):
{_format_topic_list(topic_list)}

TASK: Identify the most relevant topics for analyzing this strategy.

SELECTION CRITERIA:
1. PRIMARY TOPICS (2-4): Direct assets user is trading or analyzing
   - Match user's asset mentions to actual topic IDs
   - Focus on specific instruments (EURUSD, DXY, BRENT, etc.)

2. DRIVER TOPICS (3-6): Macro/policy factors that drive the primary assets
   - Central bank policy (FED_POLICY, ECB_POLICY, etc.)
   - Economic themes (inflation, growth, employment)
   - Structural factors user mentioned

3. Prioritize topics with clear transmission mechanisms to user's thesis

OUTPUT JSON (use exact topic IDs from list above):
{{
  "primary_topics": ["topic_id_1", "topic_id_2"],
  "driver_topics": ["topic_id_3", "topic_id_4", "topic_id_5"],
  "reasoning": "Brief explanation of topic selection and relevance to user's thesis"
}}"""

    # Get LLM response
    llm = get_llm(ModelTier.COMPLEX)
    
    # Parse response
    mapping = run_llm_decision(
        llm,
        prompt,
        TopicMapping
    )
    
    # Validate topic IDs exist
    valid_ids = {t["id"] for t in all_topics}
    primary = [tid for tid in mapping.primary_topics if tid in valid_ids]
    drivers = [tid for tid in mapping.driver_topics if tid in valid_ids]
    
    if not primary:
        raise ValueError(f"No valid primary topics found for asset: {asset_text}")
    
    master_log(f"Topics discovered | primary={len(primary)} drivers={len(drivers)}")
    
    # Expand with graph relationships
    correlated = _discover_correlated_topics(primary, valid_ids)
    
    return {
        "primary": primary,
        "drivers": drivers,
        "correlated": correlated,
        "reasoning": mapping.reasoning
    }


def _format_topic_list(topics: List[Dict]) -> str:
    """Format topic list for LLM prompt."""
    lines = []
    for t in topics[:100]:  # Limit to avoid token overflow
        lines.append(f"  {t['id']} | {t['name']}")
    return "\n".join(lines)


def _discover_correlated_topics(
    primary_topic_ids: List[str],
    valid_ids: set,
    limit: int = 5
) -> List[str]:
    """
    Discover correlated topics via graph relationships.
    Returns up to `limit` correlated topic IDs.
    """
    if not primary_topic_ids:
        return []
    
    query = """
    MATCH (primary:Topic)
    WHERE primary.id IN $topic_ids
    
    OPTIONAL MATCH (primary)-[:CORRELATES_WITH]-(correlated:Topic)
    WHERE correlated.status = 'active'
    
    WITH collect(DISTINCT correlated.id) as correlated_ids
    RETURN correlated_ids
    LIMIT 1
    """
    
    result = run_cypher(query, {"topic_ids": primary_topic_ids})
    
    if result and len(result) > 0:
        correlated_ids = result[0].get("correlated_ids", [])
        # Filter valid and limit
        correlated = [tid for tid in correlated_ids if tid and tid in valid_ids]
        return correlated[:limit]
    
    return []
