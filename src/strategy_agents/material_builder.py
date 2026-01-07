"""
Strategy Agents - Material Builder

MISSION: Build ONE complete material package with ALL relevant data.
Simple, minimal, complete.

Includes relationship context between topics for richer strategy analysis.
"""

import re
from typing import Dict, List, Any, Set
from src.graph.ops.topic import get_topic_analysis_field
from src.graph.neo4j_client import run_cypher
from src.api.backend_client import get_article as get_article_by_id
from src.market_data.loader import load_market_context
from utils import app_logging

logger = app_logging.get_logger(__name__)


def build_material_package(
    user_strategy: str,
    position_text: str,
    topic_mapping: Dict[str, List[str]],
    has_position: bool,
) -> Dict[str, Any]:
    """
    Build complete material package for strategy agents.
    
    ONE function that gathers ALL material needed by ALL agents.
    Simple, minimal, complete.
    
    Args:
        user_strategy: User's strategy description
        position_text: User's position details
        topic_mapping: {"primary": [...], "drivers": [...], "correlated": [...]}
    
    Returns:
        {
            "user_strategy": str,
            "position_text": str,
            "topics": {
                "eurusd": {
                    "name": "EURUSD",
                    "fundamental": "...",
                    "medium": "...",
                    "current": "...",
                    "drivers": "...",
                    "market_context": "..."
                },
                ...
            },
            "topic_groups": {
                "primary": ["eurusd", "dxy"],
                "drivers": ["fed_policy", "ecb_policy"],
                "correlated": ["usdjpy"]
            }
        }
    """
    logger.info("Building material package for strategy analysis")
    
    # Collect all unique topic IDs (only from topic lists, not 'reasoning' string)
    all_topic_ids = set()
    for key in ['primary', 'drivers', 'correlated']:
        if key in topic_mapping and isinstance(topic_mapping[key], list):
            all_topic_ids.update(topic_mapping[key])
    
    # Load analysis and market data for each topic
    topics = {}
    invalid_topics = []
    
    for topic_id in all_topic_ids:
        try:
            topic_data = {
                "id": topic_id,
                "name": _get_topic_name(topic_id),
                "fundamental": get_topic_analysis_field(topic_id, "fundamental_analysis") or "",
                "medium": get_topic_analysis_field(topic_id, "medium_analysis") or "",
                "current": get_topic_analysis_field(topic_id, "current_analysis") or "",
                "drivers": get_topic_analysis_field(topic_id, "drivers") or "",
                "market_context": load_market_context(topic_id) or ""
            }
            topics[topic_id] = topic_data
        except Exception as e:
            logger.warning(f"⚠️  Skipping invalid topic '{topic_id}': {e}")
            invalid_topics.append(topic_id)
    
    # Remove invalid topics from mapping
    if invalid_topics:
        logger.warning(f"⚠️  Removed {len(invalid_topics)} invalid topics: {invalid_topics}")
        for category in topic_mapping:
            topic_mapping[category] = [t for t in topic_mapping[category] if t not in invalid_topics]
    
    # Log detailed material summary
    _log_material_summary(topics, topic_mapping)
    
    # Build combined strings for high-level logging and downstream consumers
    topic_analyses_str = _build_combined_topic_analyses(topics)
    market_context_str = _build_combined_market_context(topics)
    
    # Extract article IDs from topic analyses and fetch them
    all_article_ids = _extract_article_ids_from_topics(topics)
    logger.info(f"📚 Found {len(all_article_ids)} unique article IDs in topic analyses")
    
    referenced_articles = _fetch_referenced_articles(all_article_ids)
    logger.info(f"📚 Fetched {len(referenced_articles)}/{len(all_article_ids)} articles for strategy material")

    articles_reference_str = _build_articles_reference(referenced_articles)

    # Fetch relationships between topics in our material package
    topic_relationships = _fetch_topic_relationships(all_topic_ids)
    relationship_context_str = _build_relationship_context(topic_relationships, topics)

    rel_count = sum(len(rels) for rels in topic_relationships.values())
    logger.info(f"🔗 Fetched {rel_count} relationships between {len(topic_relationships)} topics")

    return {
        "user_strategy": user_strategy,
        "position_text": position_text,
        "has_position": has_position,
        "topics": topics,
        "topic_groups": topic_mapping,
        # Combined strings for quick visibility into what goes into prompts
        "topic_analyses": topic_analyses_str,
        "market_context": market_context_str,
        # Referenced articles extracted from topic analyses
        "referenced_articles": referenced_articles,
        "articles_reference": articles_reference_str,
        # Topic relationship context for causal/correlation/hedge analysis
        "topic_relationships": topic_relationships,
        "relationship_context": relationship_context_str,
    }


def _log_material_summary(topics: Dict[str, Dict], topic_mapping: Dict[str, List[str]]):
    """Log detailed material summary for visibility."""
    
    # Count sections
    section_counts = {
        'fundamental': 0,
        'medium': 0,
        'current': 0,
        'drivers': 0,
        'market_context': 0
    }
    
    section_chars = {
        'fundamental': 0,
        'medium': 0,
        'current': 0,
        'drivers': 0,
        'market_context': 0
    }
    
    total_chars = 0
    
    for topic_id, data in topics.items():
        for section in section_counts.keys():
            content = data.get(section, '')
            if content:
                section_counts[section] += 1
                char_count = len(content)
                section_chars[section] += char_count
                total_chars += char_count
    
    # Build summary message
    summary = f"""
{'='*80}
📦 MATERIAL PACKAGE SUMMARY
{'='*80}

📊 TOPICS: {len(topics)} total
   - Primary: {len(topic_mapping.get('primary', []))} topics
   - Drivers: {len(topic_mapping.get('drivers', []))} topics
   - Correlated: {len(topic_mapping.get('correlated', []))} topics

📝 AVAILABLE SECTIONS:
   - Fundamental: {section_counts['fundamental']}/{len(topics)} topics ({section_chars['fundamental']:,} chars, avg {section_chars['fundamental']//max(section_counts['fundamental'],1):,}/topic)
   - Medium: {section_counts['medium']}/{len(topics)} topics ({section_chars['medium']:,} chars, avg {section_chars['medium']//max(section_counts['medium'],1):,}/topic)
   - Current: {section_counts['current']}/{len(topics)} topics ({section_chars['current']:,} chars, avg {section_chars['current']//max(section_counts['current'],1):,}/topic)
   - Drivers: {section_counts['drivers']}/{len(topics)} topics ({section_chars['drivers']:,} chars, avg {section_chars['drivers']//max(section_counts['drivers'],1):,}/topic)
   - Market Data: {section_counts['market_context']}/{len(topics)} topics

💾 TOTAL MATERIAL: {total_chars:,} characters (~{total_chars//1000}K)
   Average per topic: {total_chars//max(len(topics),1):,} chars

{'='*80}
"""
    
    logger.info(summary)
    
    # Log per-topic breakdown
    logger.info("📋 PER-TOPIC BREAKDOWN:")
    for topic_id, data in topics.items():
        topic_total = sum(len(data.get(s, '')) for s in ['fundamental', 'medium', 'current', 'drivers'])
        sections_available = [s for s in ['fundamental', 'medium', 'current', 'drivers'] if data.get(s, '')]
        market = "✅" if data.get('market_context') else "❌"
        
        logger.info(f"   {data['name']:30s} | {topic_total:6,} chars | Sections: {', '.join(sections_available) if sections_available else 'NONE':30s} | Market: {market}")


def _build_combined_topic_analyses(topics: Dict[str, Dict]) -> str:
    """Build one long string with all topic analyses.

    This mirrors the formatting used in individual agents, but keeps
    the logic local so orchestrator and logs can see exactly what
    goes into downstream prompts.
    """
    lines = []
    for topic_id, data in topics.items():
        lines.append(f"\n{'='*70}")
        lines.append(f"TOPIC: {data.get('name', topic_id)} ({topic_id})")
        lines.append("="*70)
        for section in ["fundamental", "medium", "current", "drivers"]:
            content = data.get(section, "")
            if content:
                lines.append(f"\n{section.upper()}:")
                lines.append(content)
    return "\n".join(lines) if lines else "No topic analyses available"


def _build_combined_market_context(topics: Dict[str, Dict]) -> str:
    """Build one long string with all market context snippets."""
    lines = []
    for topic_id, data in topics.items():
        context = data.get("market_context", "")
        if context:
            lines.append(f"{data.get('name', topic_id)}: {context}")
    return "\n".join(lines) if lines else "No market data available"


def _get_topic_name(topic_id: str) -> str:
    """Get topic display name."""
    from src.graph.ops.topic import get_topic_by_id
    topic = get_topic_by_id(topic_id)
    return topic.get("name", topic_id.upper()) if topic else topic_id.upper()


def _extract_article_ids_from_topics(topics: Dict[str, Dict]) -> Set[str]:
    """
    Extract all 9-character article IDs from topic analyses.
    
    Scans all analysis sections for patterns like (08HD556V4) or (Z7O1DCHS7)(K8M2NQWER)
    """
    all_ids = set()
    # Pattern matches 9-character alphanumeric IDs in parentheses
    pattern = r'\(([A-Z0-9]{9})\)'
    
    for topic_id, data in topics.items():
        for section in ["fundamental", "medium", "current", "drivers"]:
            content = data.get(section, "")
            if content:
                matches = re.findall(pattern, content)
                all_ids.update(matches)
    
    return all_ids


def _fetch_referenced_articles(article_ids: Set[str]) -> Dict[str, Dict]:
    """
    Fetch article data for all referenced IDs.
    
    Returns dict of {article_id: {id, title, summary, published_date}}
    """
    articles = {}
    for article_id in article_ids:
        try:
            article = get_article_by_id(article_id)
            if article:
                articles[article_id] = {
                    'id': article_id,
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'published_date': article.get('published_date', ''),
                }
        except Exception as e:
            logger.debug(f"Could not fetch article {article_id}: {e}")
    return articles


def _build_articles_reference(articles: Dict[str, Dict]) -> str:
    """Build formatted article reference section for prompts."""
    if not articles:
        return "No referenced articles available."

    lines = [f"=== REFERENCED ARTICLES ({len(articles)} articles from topic analyses) ===\n"]
    for article_id, data in articles.items():
        lines.append(f"Article ID: {article_id}")
        lines.append(f"Title: {data.get('title', 'Unknown')}")
        # Truncate summary to avoid huge prompts
        summary = data.get('summary', 'No summary')
        if len(summary) > 500:
            summary = summary[:500] + "..."
        lines.append(f"Summary: {summary}")
        if data.get('published_date'):
            lines.append(f"Date: {data.get('published_date')}")
        lines.append("")

    return "\n".join(lines)


def _fetch_topic_relationships(topic_ids: Set[str]) -> Dict[str, List[Dict]]:
    """
    Fetch ALL relationships between topics in our material package.

    Returns dict of topic_id -> list of relationships:
    {
        "eurusd": [
            {"target": "dxy", "type": "INFLUENCES", "direction": "incoming"},
            {"target": "fed_policy", "type": "INFLUENCES", "direction": "incoming"},
            {"target": "gold", "type": "HEDGES", "direction": "bidirectional"},
        ],
        ...
    }
    """
    if not topic_ids:
        return {}

    topic_list = list(topic_ids)

    query = """
    UNWIND $topic_ids as tid
    MATCH (t:Topic {id: tid})

    // Get all relationships to other topics in our set
    OPTIONAL MATCH (t)-[r:INFLUENCES|CORRELATES_WITH|PEERS|COMPONENT_OF|HEDGES]-(other:Topic)
    WHERE other.id IN $topic_ids AND other.id <> t.id

    WITH t.id as source_id, other.id as target_id, type(r) as rel_type,
         CASE
             WHEN type(r) = 'INFLUENCES' AND startNode(r) = t THEN 'drives'
             WHEN type(r) = 'INFLUENCES' AND endNode(r) = t THEN 'driven_by'
             WHEN type(r) = 'COMPONENT_OF' AND startNode(r) = t THEN 'part_of'
             WHEN type(r) = 'COMPONENT_OF' AND endNode(r) = t THEN 'contains'
             ELSE 'bidirectional'
         END as direction
    WHERE target_id IS NOT NULL

    RETURN source_id, collect(DISTINCT {
        target: target_id,
        type: rel_type,
        direction: direction
    }) as relationships
    """

    result = run_cypher(query, {"topic_ids": topic_list})

    relationships = {}
    if result:
        for row in result:
            source = row.get("source_id")
            rels = row.get("relationships", [])
            if source and rels:
                relationships[source] = [r for r in rels if r.get("target")]

    return relationships


def _build_relationship_context(relationships: Dict[str, List[Dict]], topics: Dict[str, Dict]) -> str:
    """
    Build human-readable relationship context for prompts.

    Format:
    === TOPIC RELATIONSHIPS ===
    EURUSD:
      - driven_by: DXY (INFLUENCES) - Dollar strength drives EUR weakness
      - driven_by: Fed Policy (INFLUENCES) - Fed rate decisions impact pair
      - hedges: Gold (HEDGES) - Inverse relationship in risk-off
    """
    if not relationships:
        return "No topic relationships available."

    # Relationship type hints for analysis
    rel_hints = {
        "INFLUENCES": {
            "drives": "causes movement in",
            "driven_by": "is moved by"
        },
        "CORRELATES_WITH": {
            "bidirectional": "co-moves with (shared drivers)"
        },
        "PEERS": {
            "bidirectional": "competes with / substitutes for"
        },
        "COMPONENT_OF": {
            "part_of": "is a constituent of",
            "contains": "includes as constituent"
        },
        "HEDGES": {
            "bidirectional": "hedges / moves inversely with"
        }
    }

    lines = ["=== TOPIC RELATIONSHIPS (use for causal chains & risk analysis) ===\n"]

    for topic_id, rels in relationships.items():
        if not rels:
            continue

        topic_name = topics.get(topic_id, {}).get("name", topic_id.upper())
        lines.append(f"{topic_name}:")

        for rel in rels:
            target_id = rel.get("target")
            rel_type = rel.get("type", "UNKNOWN")
            direction = rel.get("direction", "bidirectional")

            target_name = topics.get(target_id, {}).get("name", target_id.upper())
            hint = rel_hints.get(rel_type, {}).get(direction, rel_type.lower())

            lines.append(f"  → {hint}: {target_name}")

        lines.append("")

    return "\n".join(lines) if len(lines) > 1 else "No topic relationships available."
