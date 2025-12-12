"""
Depth Finder - Graph Strategy

MISSION: Find opportunities for causal chains and quantification across timeframes.

GRAPH EXPLORATION:
1. Get tier 3 articles across ALL timeframes (fundamental, medium, current)
2. Only risk OR trend perspectives (causal chain relevant)
3. Order by timeframe for logical chain building
"""

from typing import Dict, List
from src.graph.neo4j_client import run_cypher


def explore_graph(topic_id: str, section: str) -> Dict:
    """
    Get tier 3 articles across ALL timeframes for depth analysis.
    
    Returns:
        {
            "topic_name": str,
            "articles": List[dict grouped by timeframe]
        }
    """
    
    # Get tier 3 articles across ALL timeframes (not just the requested section)
    # Only risk OR trend perspectives
    query = """
    MATCH (t:Topic {id: $topic_id})
    MATCH (art:Article)-[r:ABOUT]->(t)
    WHERE (r.importance_risk = 3 OR r.importance_trend = 3)
    RETURN 
        t.name as topic_name,
        r.timeframe as timeframe,
        art.id as id,
        art.summary as summary,
        art.published_at as published_at,
        r.importance_risk as risk,
        r.importance_trend as trend
    ORDER BY 
        CASE r.timeframe 
            WHEN 'fundamental' THEN 1
            WHEN 'medium' THEN 2
            WHEN 'current' THEN 3
            ELSE 4
        END,
        art.published_at DESC
    LIMIT 45
    """
    
    result = run_cypher(query, {"topic_id": topic_id})
    
    print(f"[DepthFinder] Query returned {len(result) if result else 0} rows")
    
    if not result:
        return {
            "topic_name": topic_id,
            "topic_id": topic_id,
            "articles": []
        }
    
    topic_name = result[0].get("topic_name", topic_id) if result else topic_id
    
    # Group by timeframe for logging
    by_timeframe = {}
    for row in result:
        tf = row['timeframe']
        if tf not in by_timeframe:
            by_timeframe[tf] = []
        by_timeframe[tf].append({
            'id': row['id'],
            'summary': row['summary'],
            'published_at': row['published_at'],
            'risk': row['risk'],
            'trend': row['trend']
        })
    
    print(f"[DepthFinder] Cross-timeframe articles (tier 3, risk/trend):")
    for tf in ['fundamental', 'medium', 'current']:
        if tf in by_timeframe:
            articles = by_timeframe[tf]
            sample_ids = [art['id'] for art in articles[:2]]
            print(f"   {tf.upper()}: {len(articles)} articles ({', '.join(sample_ids)}{'...' if len(articles) > 2 else ''})")
    
    # Flatten for return
    all_articles = []
    for articles in by_timeframe.values():
        all_articles.extend(articles)
    
    return {
        "topic_name": topic_name,
        "topic_id": topic_id,
        "articles": all_articles
    }
