"""
Improvement Analyzer - Graph Strategy

MISSION: Compare old vs. new articles to guide rewrite.

GRAPH EXPLORATION:
1. Get existing analysis for this section
2. Get timestamp of last update
3. Get articles used in last analysis (before timestamp)
4. Get NEW articles (after timestamp)
5. Return for comparison
"""

from typing import Dict, List
from src.graph.neo4j_client import run_cypher
from datetime import datetime, timezone


def explore_graph(topic_id: str, section: str) -> Dict:
    """
    Compare old vs. new articles.
    
    Returns:
        {
            "topic_name": str,
            "existing_analysis": str,
            "last_updated": datetime,
            "old_articles": List[dict],
            "new_articles": List[dict]
        }
    """
    
    # Map section to field name
    field_map = {
        "fundamental": "fundamental_analysis",
        "medium": "medium_analysis",
        "current": "current_analysis"
    }
    analysis_field = field_map.get(section, "fundamental_analysis")
    updated_field = f"{analysis_field}_updated_at"
    
    query = f"""
    MATCH (t:Topic {{id: $topic_id}})
    
    // Get existing analysis and last update time
    WITH t, 
         t.{analysis_field} as existing_analysis,
         t.{updated_field} as last_updated
    
    // Get all articles for this section
    MATCH (art:Article)-[r:ABOUT]->(t)
    WHERE r.timeframe = $section
    
    // Separate old vs. new based on last_updated
    WITH t, existing_analysis, last_updated, art, r,
         CASE 
             WHEN last_updated IS NULL THEN 'new'
             WHEN art.published_at < last_updated THEN 'old'
             ELSE 'new'
         END as article_age
    
    RETURN 
        t.name as topic_name,
        existing_analysis,
        last_updated,
        collect(CASE WHEN article_age = 'old' THEN {{
            id: art.id,
            summary: art.summary,
            published_at: art.published_at
        }} END) as old_articles,
        collect(CASE WHEN article_age = 'new' THEN {{
            id: art.id,
            summary: art.summary,
            published_at: art.published_at
        }} END) as new_articles
    """
    
    result = run_cypher(query, {"topic_id": topic_id, "section": section})
    
    if not result:
        return {
            "topic_name": topic_id,
            "topic_id": topic_id,
            "existing_analysis": "",
            "last_updated": None,
            "old_articles": [],
            "new_articles": []
        }
    
    data = result[0]
    
    # Filter out None values from CASE statements
    old_articles = [a for a in data.get("old_articles", []) if a is not None]
    new_articles = [a for a in data.get("new_articles", []) if a is not None]
    
    return {
        "topic_name": data.get("topic_name", topic_id),
        "topic_id": topic_id,
        "existing_analysis": data.get("existing_analysis", ""),
        "last_updated": data.get("last_updated"),
        "old_articles": old_articles,
        "new_articles": new_articles
    }
