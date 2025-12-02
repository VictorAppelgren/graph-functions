"""
Contrarian Finder - Graph Strategy

MISSION: Find contrarian assets and their analysis to challenge consensus.

GRAPH EXPLORATION:
1. Identify contrarian assets (negatively correlated)
2. Get their executive_summary and relevant analysis
3. Return for contrarian angle detection
"""

from typing import Dict, List
from src.graph.neo4j_client import run_cypher


# Contrarian asset mapping (negatively correlated assets)
CONTRARIAN_PAIRS = {
    "eurusd": ["dxy", "usdjpy"],
    "dxy": ["eurusd", "gold"],
    "ust10y": ["spx", "gold"],
    "ust2y": ["spx", "gold"],
    "gold": ["ust10y", "dxy"],
    "wti": ["natgas", "dxy"],
    "brent": ["natgas", "dxy"],
    "spx": ["ust10y", "vix"],
    "ndx": ["ust10y", "vix"],
    "gbpusd": ["dxy"],
    "usdjpy": ["eurusd"],
}


def explore_graph(topic_id: str, section: str) -> Dict:
    """
    Explore graph to find contrarian assets with tier 3 articles.
    
    Returns:
        {
            "topic_name": str,
            "contrarian_assets": List[dict with articles]
        }
    """
    
    # Get contrarian asset IDs
    contrarian_ids = CONTRARIAN_PAIRS.get(topic_id, [])
    
    if not contrarian_ids:
        print(f"[ContrarianFinder] No predefined contrarian assets for {topic_id}")
        return {
            "topic_name": topic_id,
            "topic_id": topic_id,
            "contrarian_assets": []
        }
    
    # Get contrarian topics' executive summaries
    query = """
    MATCH (contrarian:Topic)
    WHERE contrarian.id IN $contrarian_ids
    RETURN 
        contrarian.id as topic_id,
        contrarian.name as topic_name,
        contrarian.executive_summary as executive_summary
    """
    
    result = run_cypher(query, {"contrarian_ids": contrarian_ids})
    
    if not result:
        print(f"[ContrarianFinder] No contrarian topics found in graph")
        return {
            "topic_name": topic_id,
            "topic_id": topic_id,
            "contrarian_assets": []
        }
    
    # Get tier 3 articles (risk OR opportunity) from each contrarian asset
    contrarian_assets = []
    assets_with_articles = []
    
    for contrarian in result:
        contrarian_id = contrarian['topic_id']
        
        query_articles = """
        MATCH (art:Article)-[r:ABOUT]->(t:Topic {id: $contrarian_id})
        WHERE r.timeframe = $section
          AND (r.importance_risk = 3 OR r.importance_opportunity = 3)
        RETURN 
            art.id as id,
            art.summary as summary,
            r.importance_risk as risk,
            r.importance_opportunity as opportunity
        """
        
        articles = run_cypher(query_articles, {
            "contrarian_id": contrarian_id,
            "section": section
        })
        
        contrarian_assets.append({
            "topic_id": contrarian['topic_id'],
            "topic_name": contrarian['topic_name'],
            "executive_summary": contrarian.get('executive_summary', ''),
            "articles": articles if articles else []
        })
        
        if articles:
            sample_ids = [a['id'] for a in articles[:2]]
            assets_with_articles.append({
                'name': contrarian['topic_name'],
                'count': len(articles),
                'sample': ', '.join(sample_ids)
            })
    
    # Summary
    if assets_with_articles:
        print(f"[ContrarianFinder] Contrarian assets with tier-3 articles:")
        for asset in assets_with_articles:
            print(f"   • {asset['name']}: {asset['count']} articles ({asset['sample']})")
    else:
        print(f"[ContrarianFinder] No tier-3 articles found in contrarian assets")
    
    # Get THIS topic's name
    topic_query = """
    MATCH (t:Topic {id: $topic_id})
    RETURN t.name as name
    """
    topic_result = run_cypher(topic_query, {"topic_id": topic_id})
    topic_name = topic_result[0]['name'] if topic_result else topic_id
    
    return {
        "topic_name": topic_name,
        "topic_id": topic_id,
        "contrarian_assets": contrarian_assets
    }
