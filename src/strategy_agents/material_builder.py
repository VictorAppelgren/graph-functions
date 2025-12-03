"""
Strategy Agents - Material Builder

MISSION: Build ONE complete material package with ALL relevant data.
Simple, minimal, complete.
"""

from typing import Dict, List, Any
from src.graph.ops.topic import get_topic_analysis_field
from src.market_data.loader import load_market_context
from utils import app_logging

logger = app_logging.get_logger(__name__)


def build_material_package(
    user_strategy: str,
    position_text: str,
    topic_mapping: Dict[str, List[str]]
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
    
    return {
        "user_strategy": user_strategy,
        "position_text": position_text,
        "topics": topics,
        "topic_groups": topic_mapping
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
   Average per topic: {total_chars//len(topics):,} chars

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


def _get_topic_name(topic_id: str) -> str:
    """Get topic display name."""
    from src.graph.ops.topic import get_topic_by_id
    topic = get_topic_by_id(topic_id)
    return topic.get("name", topic_id.upper()) if topic else topic_id.upper()
