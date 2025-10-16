"""
Material Collector for Custom User Analysis

Selectively collects analysis from graph topics based on relevance.
"""

from typing import Dict, List, Any
from src.graph.ops.topic import get_topic_by_id
from src.graph.neo4j_client import run_cypher
from src.observability.pipeline_logging import master_log


def collect_analysis_material(
    primary_topics: List[str],
    driver_topics: List[str],
    correlated_topics: List[str]
) -> Dict[str, Any]:
    """
    Collect analysis material strategically:
    - PRIMARY: All sections (fundamental, medium, current, drivers, executive_summary)
    - DRIVERS: Current + drivers only
    - CORRELATED: Current only
    
    Returns material dict organized by topic type.
    """
    master_log(f"Material collection started | primary={len(primary_topics)} drivers={len(driver_topics)} correlated={len(correlated_topics)}")
    
    material = {
        "primary_analysis": {},
        "driver_analysis": {},
        "correlated_analysis": {}
    }
    
    # Collect primary topics - full analysis
    for topic_id in primary_topics:
        topic_data = get_topic_by_id(topic_id)
        if not topic_data:
            continue
            
        analysis = _get_topic_analysis_sections(
            topic_id,
            sections=["fundamental_analysis", "medium_analysis", "current_analysis", "drivers", "executive_summary"]
        )
        
        material["primary_analysis"][topic_id] = {
            "name": topic_data.get("name", topic_id),
            **analysis
        }
    
    # Collect driver topics - current + drivers
    for topic_id in driver_topics:
        topic_data = get_topic_by_id(topic_id)
        if not topic_data:
            continue
            
        analysis = _get_topic_analysis_sections(
            topic_id,
            sections=["current_analysis", "drivers"]
        )
        
        material["driver_analysis"][topic_id] = {
            "name": topic_data.get("name", topic_id),
            **analysis
        }
    
    # Collect correlated topics - current only
    for topic_id in correlated_topics:
        topic_data = get_topic_by_id(topic_id)
        if not topic_data:
            continue
            
        analysis = _get_topic_analysis_sections(
            topic_id,
            sections=["current_analysis"]
        )
        
        material["correlated_analysis"][topic_id] = {
            "name": topic_data.get("name", topic_id),
            **analysis
        }
    
    # Calculate total material size
    total_chars = _calculate_material_size(material)
    master_log(f"Material collected | total_chars={total_chars}")
    
    return material


def _get_topic_analysis_sections(topic_id: str, sections: List[str]) -> Dict[str, str]:
    """
    Get specific analysis sections for a topic.
    Returns dict with section names as keys.
    """
    query = """
    MATCH (t:Topic {id: $topic_id})
    RETURN t
    LIMIT 1
    """
    
    result = run_cypher(query, {"topic_id": topic_id})
    
    if not result or len(result) == 0:
        return {section: "" for section in sections}
    
    topic_node = result[0]["t"]
    analysis = {}
    
    for section in sections:
        content = topic_node.get(section, "")
        # Truncate if too long (max 3000 chars per section)
        if content and len(content) > 3000:
            content = content[:3000] + "..."
        analysis[section] = content or ""
    
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
