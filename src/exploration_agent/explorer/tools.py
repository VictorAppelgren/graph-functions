"""
Exploration Agent - Tool Implementations

Each tool reads from the graph and returns structured data for the agent.

Key design:
- read_articles returns (list_of_article_dicts, list_of_ids) for individual message creation
- read_section returns (content, source_id) for tracking
- Each piece of content gets a unique ID for selective saving/deletion
"""

from typing import Optional, List, Dict, Any, Tuple
from src.graph.neo4j_client import run_cypher, get_articles
from src.graph.ops.topic import get_topic_by_id, get_topic_analysis_field
from src.api.backend_client import get_strategy
from src.strategy_agents.topic_mapper.agent import TopicMapperAgent
from src.api.backend_client import save_strategy_topics
from src.exploration_agent.models import TopicSnapshot, MessageEntry
from utils import app_logging

logger = app_logging.get_logger(__name__)


# =============================================================================
# SECTION NAMES (for prompt and validation)
# =============================================================================

ANALYSIS_SECTIONS = [
    "chain_reaction_map",
    "structural_threats",
    "tactical_scenarios",
    "immediate_intelligence",
    "macro_cascade",
    "trade_intelligence",
    "house_view",
    "risk_monitor",
    "executive_summary",
]

RISK_FOCUSED_SECTIONS = ["chain_reaction_map", "structural_threats", "risk_monitor"]
OPPORTUNITY_FOCUSED_SECTIONS = ["tactical_scenarios", "immediate_intelligence", "trade_intelligence"]

ARTICLE_TIMEFRAMES = ["current", "medium", "fundamental"]
ARTICLE_CATEGORIES = ["risk", "opportunity", "catalyst", "driver"]


# =============================================================================
# GRAPH QUERIES
# =============================================================================

def get_topic_snapshot(topic_id: str) -> TopicSnapshot:
    """
    Get a full snapshot of a topic including executive summary and connections.
    """
    try:
        topic = get_topic_by_id(topic_id)
    except Exception as e:
        logger.warning(f"Topic {topic_id} not found: {e}")
        return TopicSnapshot(
            id=topic_id,
            name=topic_id.replace("_", " ").title(),
            executive_summary=None,
            connected_topics=[]
        )
    
    # Get executive summary
    exec_summary = get_topic_analysis_field(topic_id, "executive_summary")
    
    # Get connected topics
    connected = get_connected_topics(topic_id)
    
    return TopicSnapshot(
        id=topic_id,
        name=topic.get("name", topic_id),
        executive_summary=exec_summary,
        connected_topics=connected
    )


def get_connected_topics(topic_id: str) -> List[Dict[str, str]]:
    """
    Get all topics connected to this one via INFLUENCES, CORRELATES_WITH, PEERS, COMPONENT_OF, HEDGES.
    Returns list of {id, name, relationship_type, direction}.
    """
    query = """
    MATCH (t:Topic {id: $topic_id})
    OPTIONAL MATCH (t)-[r1:INFLUENCES]->(influenced:Topic)
    OPTIONAL MATCH (t)<-[r2:INFLUENCES]-(influencer:Topic)
    OPTIONAL MATCH (t)-[r3:CORRELATES_WITH]-(correlated:Topic)
    OPTIONAL MATCH (t)-[r4:PEERS]-(peer:Topic)
    OPTIONAL MATCH (t)-[r5:COMPONENT_OF]-(component:Topic)
    OPTIONAL MATCH (t)-[r6:HEDGES]-(hedged:Topic)

    WITH t,
        collect(DISTINCT {id: influenced.id, name: influenced.name, rel: 'INFLUENCES', dir: 'outgoing'}) as influenced_list,
        collect(DISTINCT {id: influencer.id, name: influencer.name, rel: 'INFLUENCED_BY', dir: 'incoming'}) as influencer_list,
        collect(DISTINCT {id: correlated.id, name: correlated.name, rel: 'CORRELATES_WITH', dir: 'both'}) as correlated_list,
        collect(DISTINCT {id: peer.id, name: peer.name, rel: 'PEERS', dir: 'both'}) as peer_list,
        collect(DISTINCT {id: component.id, name: component.name, rel: 'COMPONENT_OF', dir: 'both'}) as component_list,
        collect(DISTINCT {id: hedged.id, name: hedged.name, rel: 'HEDGES', dir: 'both'}) as hedged_list

    RETURN influenced_list + influencer_list + correlated_list + peer_list + component_list + hedged_list as connections
    """
    
    result = run_cypher(query, {"topic_id": topic_id})
    if not result:
        return []
    
    connections = result[0].get("connections", [])
    # Filter out nulls and format
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "relationship_type": c["rel"],
            "direction": c["dir"]
        }
        for c in connections
        if c.get("id") is not None
    ]


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def read_section(topic_id: str, section: str) -> Tuple[Optional[str], str, bool]:
    """
    Read a specific analysis section from a topic.
    
    Returns:
        (content, source_id, success)
        - content: The section text (or error message)
        - source_id: Unique ID like "sec_eurusd_executive_summary"
        - success: Whether content was found
    """
    source_id = f"sec_{topic_id}_{section}"
    
    if section not in ANALYSIS_SECTIONS:
        logger.warning(f"Invalid section requested: {section}")
        return f"❌ Invalid section '{section}'. Valid: {', '.join(ANALYSIS_SECTIONS)}", source_id, False
    
    content = get_topic_analysis_field(topic_id, section)
    
    if not content:
        logger.info(f"Section '{section}' empty for topic '{topic_id}'")
        return f"📭 Section '{section}' is empty for topic '{topic_id}'.", source_id, False
    
    # Truncate if too long
    original_len = len(content)
    if len(content) > 4000:
        content = content[:4000] + "\n\n[... truncated ...]"
    
    logger.info(f"📖 Read section '{section}' for '{topic_id}' | {original_len} chars | ID: {source_id}")
    return content, source_id, True


def read_articles(
    topic_id: str,
    limit: int = 3
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Read articles for a topic.
    
    Returns:
        (articles, source_ids)
        - articles: List of article dicts with {source_id, title, summary, content}
        - source_ids: List of source IDs like ["art_ABC123", "art_DEF456"]
    """
    # Clamp limit
    limit = max(1, min(5, limit))
    
    # Build query
    query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
    RETURN a.id as id, a.title as title, a.summary as summary, 
           a.content as content, a.temporal_horizon as timeframe, a.type as category
    ORDER BY a.published_at DESC
    LIMIT $limit
    """
    params = {"topic_id": topic_id, "limit": limit}
    
    result = run_cypher(query, params)
    
    if not result:
        logger.info(f"📭 No articles found for topic '{topic_id}'")
        return [], []
    
    articles = []
    source_ids = []
    
    for article in result:
        raw_id = article.get("id", "unknown")
        source_id = f"art_{raw_id}"
        source_ids.append(source_id)
        
        title = article.get("title", "Untitled")
        summary = article.get("summary", "")
        content = article.get("content", "")
        timeframe = article.get("timeframe", "?")
        category = article.get("category", "?")
        
        # Use summary if content is empty, truncate if needed
        text = content if content else summary
        if len(text) > 1500:
            text = text[:1500] + "\n[... truncated ...]"
        
        articles.append({
            "source_id": source_id,
            "title": title,
            "summary": summary[:300] if summary else "",
            "content": text,
            "timeframe": timeframe,
            "category": category,
        })
    
    logger.info(f"📰 Found {len(articles)} articles for '{topic_id}' | IDs: {source_ids}")
    return articles, source_ids


def get_existing_findings(topic_id: str, mode: str) -> List[str]:
    """
    Get existing risks or opportunities for a topic.
    Returns list of headlines/titles.
    """
    from src.graph.ops.topic_findings import get_topic_findings

    findings = get_topic_findings(topic_id, mode)
    return [f.get("headline", "") for f in findings if f.get("headline")]


def get_strategy_context(username: str, strategy_id: str) -> Optional[Dict[str, Any]]:
    """Fetch strategy (with topic mapping) from backend storage."""
    strategy = get_strategy(username, strategy_id)
    if not strategy:
        logger.warning("Strategy %s not found for user %s", strategy_id, username)
        return None
    # Normalize topic mapping structure
    topic_mapping = strategy.get("topic_mapping")
    if not topic_mapping:
        topics_field = strategy.get("topics", {}) or {}
        topic_mapping = {
            "primary": topics_field.get("primary", []) or [],
            "drivers": topics_field.get("drivers", []) or [],
            "correlated": topics_field.get("correlated", []) or [],
        }
        strategy["topic_mapping"] = topic_mapping
    else:
        # Ensure lists and fallbacks
        topic_mapping = {
            "primary": topic_mapping.get("primary", []) or [],
            "drivers": topic_mapping.get("drivers", []) or [],
            "correlated": topic_mapping.get("correlated", []) or [],
        }
        strategy["topic_mapping"] = topic_mapping
    return strategy


def get_initial_context(topic_id: str, mode: str) -> str:
    """
    Get rich initial context for a topic based on exploration mode.
    Includes executive summary + relevant sections.
    """
    sections_to_include = RISK_FOCUSED_SECTIONS if mode == "risk" else OPPORTUNITY_FOCUSED_SECTIONS
    
    output = ""
    
    # Executive summary
    exec_summary = get_topic_analysis_field(topic_id, "executive_summary")
    if exec_summary:
        output += f"📋 **Executive Summary**:\n{exec_summary}\n\n"
    
    # Mode-specific sections (just titles/first 200 chars as preview)
    for section in sections_to_include[:2]:  # Just 2 sections to start
        content = get_topic_analysis_field(topic_id, section)
        if content:
            preview = content[:500] + "..." if len(content) > 500 else content
            output += f"📖 **{section}** (preview):\n{preview}\n\n"
    
    # Existing findings
    existing = get_existing_findings(topic_id, mode)
    if existing:
        output += f"📌 **Existing {mode}s** (don't duplicate these):\n"
        for finding in existing:
            output += f"  • {finding}\n"
        output += "\n"
    
    return output if output else f"No existing analysis for {topic_id}."


def format_connected_topics(connections: List[Dict[str, str]]) -> str:
    """
    Format connected topics for the prompt.
    """
    if not connections:
        return "No connected topics found."
    
    output = "🔗 **Connected Topics** (you can move to any of these):\n"
    
    # Group by relationship type
    by_type: Dict[str, List[Dict]] = {}
    for conn in connections:
        rel = conn.get("relationship_type", "RELATED")
        if rel not in by_type:
            by_type[rel] = []
        by_type[rel].append(conn)
    
    for rel_type, topics in by_type.items():
        output += f"\n**{rel_type}**:\n"
        for t in topics[:10]:  # Limit per type
            output += f"  • `{t['id']}` ({t['name']})\n"
        if len(topics) > 10:
            output += f"  • ... and {len(topics) - 10} more\n"
    
    return output
