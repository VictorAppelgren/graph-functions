"""
Material Collector for Custom User Analysis

Selectively collects analysis from graph topics based on relevance.
"""

from typing import Dict, List, Any
from src.graph.ops.topic import get_topic_by_id
from src.graph.neo4j_client import run_cypher
from src.observability.pipeline_logging import master_log
from utils.app_logging import get_logger

logger = get_logger(__name__)

# Import the canonical list of all analysis sections
from src.analysis.orchestration.analysis_rewriter import SECTIONS

# Map section names to their property names in Neo4j
SECTION_PROPERTY_MAP = {
    "fundamental": "fundamental_analysis",
    "medium": "medium_analysis",
    "current": "current_analysis",
    "drivers": "drivers",
    "movers_scenarios": "movers_scenarios",
    "swing_trade_or_outlook": "swing_trade_or_outlook",
    "executive_summary": "executive_summary",
    "risk_analysis": "risk_analysis",
    "opportunity_analysis": "opportunity_analysis",
    "trend_analysis": "trend_analysis",
    "catalyst_analysis": "catalyst_analysis",
}


def collect_analysis_material(
    primary_topics: List[str],
    driver_topics: List[str],
    correlated_topics: List[str]
) -> Dict[str, Any]:
    """
    Collect analysis material strategically:
    - PRIMARY: ALL sections (fundamental, medium, current, drivers, perspectives, etc.)
    - DRIVERS: Current + drivers + perspectives
    - CORRELATED: Current only
    
    Returns material dict organized by topic type.
    """
    master_log(f"Material collection started | primary={len(primary_topics)} drivers={len(driver_topics)} correlated={len(correlated_topics)}")
    logger.info("="*80)
    logger.info("🔍 MATERIAL COLLECTION STARTED")
    logger.info(f"Primary topics ({len(primary_topics)}): {primary_topics}")
    logger.info(f"Driver topics ({len(driver_topics)}): {driver_topics}")
    logger.info(f"Correlated topics ({len(correlated_topics)}): {correlated_topics}")
    logger.info("="*80)
    
    material = {
        "primary_analysis": {},
        "driver_analysis": {},
        "correlated_analysis": {}
    }
    
    # Collect primary topics - ALL sections
    logger.info("\n📦 COLLECTING PRIMARY TOPICS (ALL SECTIONS)")
    logger.info(f"Sections to collect: {SECTIONS}")
    for topic_id in primary_topics:
        topic_data = get_topic_by_id(topic_id)
        if not topic_data:
            continue
            
        # Get ALL analysis sections for primary topics
        analysis = _get_topic_analysis_sections(
            topic_id,
            sections=SECTIONS  # Use complete list from analysis_rewriter
        )
        
        material["primary_analysis"][topic_id] = {
            "name": topic_data.get("name", topic_id),
            **analysis
        }
    
    # Collect driver topics - current + drivers + perspectives
    logger.info("\n📦 COLLECTING DRIVER TOPICS (FOCUSED SECTIONS)")
    logger.info(f"Sections to collect: current, drivers, risk_analysis, opportunity_analysis, catalyst_analysis")
    for topic_id in driver_topics:
        topic_data = get_topic_by_id(topic_id)
        if not topic_data:
            continue
            
        analysis = _get_topic_analysis_sections(
            topic_id,
            sections=["current", "drivers", "risk_analysis", "opportunity_analysis", "catalyst_analysis"]
        )
        
        material["driver_analysis"][topic_id] = {
            "name": topic_data.get("name", topic_id),
            **analysis
        }
    
    # Collect correlated topics - current only
    logger.info("\n📦 COLLECTING CORRELATED TOPICS (CURRENT ONLY)")
    logger.info(f"Sections to collect: current")
    for topic_id in correlated_topics:
        topic_data = get_topic_by_id(topic_id)
        if not topic_data:
            continue
            
        analysis = _get_topic_analysis_sections(
            topic_id,
            sections=["current"]
        )
        
        material["correlated_analysis"][topic_id] = {
            "name": topic_data.get("name", topic_id),
            **analysis
        }
    
    # Calculate total material size and estimate tokens
    total_chars = _calculate_material_size(material)
    estimated_tokens = total_chars // 4  # Rough estimate: 4 chars per token
    
    # Calculate detailed statistics
    primary_chars = sum(
        len(str(v)) for topic in material["primary_analysis"].values() 
        for k, v in topic.items() if k != "name" and isinstance(v, str)
    )
    driver_chars = sum(
        len(str(v)) for topic in material["driver_analysis"].values() 
        for k, v in topic.items() if k != "name" and isinstance(v, str)
    )
    correlated_chars = sum(
        len(str(v)) for topic in material["correlated_analysis"].values() 
        for k, v in topic.items() if k != "name" and isinstance(v, str)
    )
    
    logger.info("\n" + "="*80)
    logger.info("📊 MATERIAL COLLECTION SUMMARY")
    logger.info("="*80)
    logger.info(f"Primary topics: {len(material['primary_analysis'])} topics, {primary_chars:,} chars")
    logger.info(f"Driver topics: {len(material['driver_analysis'])} topics, {driver_chars:,} chars")
    logger.info(f"Correlated topics: {len(material['correlated_analysis'])} topics, {correlated_chars:,} chars")
    logger.info(f"TOTAL: {total_chars:,} chars (~{estimated_tokens:,} tokens)")
    
    # Show which topics contributed content
    topics_with_content = []
    topics_without_content = []
    
    for category, topics in material.items():
        for topic_id, topic_data in topics.items():
            has_content = any(
                len(str(v)) > 0 for k, v in topic_data.items() 
                if k != "name" and isinstance(v, str)
            )
            if has_content:
                topics_with_content.append(topic_id)
            else:
                topics_without_content.append(topic_id)
    
    logger.info(f"\n✅ Topics with content ({len(topics_with_content)}): {topics_with_content}")
    if topics_without_content:
        logger.warning(f"❌ Topics with NO content ({len(topics_without_content)}): {topics_without_content}")
        logger.warning(f"   → These topics need analysis generation (run main.py or enrichment)")
    
    logger.info("="*80)
    
    master_log(f"Material collected | total_chars={total_chars} estimated_tokens={estimated_tokens}")
    
    # Warn if approaching context limits
    if estimated_tokens > 50000:
        logger.warning(
            f"⚠️  LARGE CONTEXT | estimated_tokens={estimated_tokens} "
            f"(may exceed model limits or be very expensive)"
        )
    elif estimated_tokens > 30000:
        logger.warning(
            f"⚠️  HIGH TOKEN COUNT | estimated_tokens={estimated_tokens} "
            f"(consider reducing topics or sections)"
        )
    
    return material


def _get_topic_analysis_sections(topic_id: str, sections: List[str]) -> Dict[str, str]:
    """
    Get specific analysis sections for a topic.
    
    Args:
        topic_id: Topic ID
        sections: List of section names (e.g., ["fundamental", "current", "drivers"])
    
    Returns:
        Dict with section names as keys and analysis content as values
    """
    logger.info(f"📥 Fetching sections for topic={topic_id} | requesting {len(sections)} sections: {sections}")
    
    query = """
    MATCH (t:Topic {id: $topic_id})
    RETURN t
    LIMIT 1
    """
    
    result = run_cypher(query, {"topic_id": topic_id})
    
    if not result or len(result) == 0:
        logger.warning(f"❌ Topic not found: {topic_id}")
        return {section: "" for section in sections}
    
    topic_node = result[0]["t"]
    
    # Log what fields exist on the topic
    available_fields = list(topic_node.keys())
    logger.info(f"📋 Topic {topic_id} has {len(available_fields)} fields: {available_fields}")
    
    analysis = {}
    sections_found = 0
    sections_missing = 0
    
    for section in sections:
        # Map section name to property name (e.g., "fundamental" -> "fundamental_analysis")
        property_name = SECTION_PROPERTY_MAP.get(section, section)
        content = topic_node.get(property_name, "")
        
        if content:
            sections_found += 1
            char_count = len(content)
            logger.info(
                f"  ✅ Found {section} (field={property_name}) | {char_count} chars"
            )
            
            # Warn if content is very large (estimate ~4 chars per token)
            if char_count > 12000:  # ~3000 tokens
                estimated_tokens = char_count // 4
                logger.warning(
                    f"  ⚠️  Large section | topic={topic_id} section={section} "
                    f"chars={char_count} estimated_tokens={estimated_tokens}"
                )
        else:
            sections_missing += 1
            logger.warning(
                f"  ❌ Missing {section} (field={property_name}) | "
                f"field_exists={property_name in topic_node} | "
                f"content_empty={property_name in topic_node and not topic_node.get(property_name)}"
            )
        
        # Store with section name as key (not property name) - NO TRUNCATION
        analysis[section] = content or ""
    
    logger.info(
        f"📊 Topic {topic_id} summary: {sections_found} found, {sections_missing} missing "
        f"(out of {len(sections)} requested)"
    )
    
    return analysis


def _calculate_material_size(material: Dict[str, Any]) -> int:
    """Calculate total character count of collected material."""
    total = 0
    
    for category in material.values():
        for topic_data in category.values():
            for section_content in topic_data.values():
                if isinstance(section_content, str):
                    total += len(section_content)
    
    return total


def format_material_for_prompt(
    material: Dict[str, Any],
    category: str,
    section_filter: List[str] = None
) -> str:
    """
    Format collected material for LLM prompt.
    
    Args:
        material: Collected material dict
        category: "primary_analysis", "driver_analysis", or "correlated_analysis"
        section_filter: Optional list of sections to include
    
    Returns:
        Formatted string for prompt
    """
    if category not in material:
        return ""
    
    lines = []
    
    for topic_id, topic_data in material[category].items():
        topic_name = topic_data.get("name", topic_id)
        
        for section_key, section_content in topic_data.items():
            if section_key == "name":
                continue
            
            # Apply section filter if provided
            if section_filter and section_key not in section_filter:
                continue
            
            if section_content and len(section_content.strip()) > 0:
                section_title = section_key.replace("_", " ").title()
                lines.append(f"【{topic_name} - {section_title}】")
                lines.append(section_content.strip())
                lines.append("")
    
    return "\n".join(lines)
