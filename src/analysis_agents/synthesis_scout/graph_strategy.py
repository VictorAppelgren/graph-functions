"""
Synthesis Scout - Graph Strategy

MISSION: Find cross-topic synthesis opportunities.

GRAPH EXPLORATION:
1. Get THIS topic's tier 3 articles (risk OR opportunity only)
2. Get RELATED topics via graph edges (INFLUENCES, CORRELATES_WITH, PEERS)
3. Get related topics' executive summaries
4. Get tier 3 catalyst articles from related topics
"""

from typing import Dict, List
from src.graph.neo4j_client import run_cypher


def explore_graph(topic_id: str, section: str) -> Dict:
    """
    Get tier 3 articles from this topic + related topics.
    
    Returns:
        {
            "topic_name": str,
            "topic_articles": List[dict],
            "related_topics": List[dict with articles]
        }
    """
    
    # Get THIS topic's tier 3 articles (risk OR opportunity perspectives only)
    query_articles = """
    MATCH (t:Topic {id: $topic_id})
    MATCH (art:Article)-[r:ABOUT]->(t)
    WHERE r.timeframe = $section
      AND (r.importance_risk = 3 OR r.importance_opportunity = 3)
    RETURN 
        t.name as topic_name,
        collect({
            id: art.id,
            summary: art.summary,
            published_at: art.published_at,
            risk: r.importance_risk,
            opportunity: r.importance_opportunity
        }) as articles
    """
    
    result = run_cypher(query_articles, {"topic_id": topic_id, "section": section})
    
    if not result:
        return {
            "topic_name": topic_id,
            "topic_id": topic_id,
            "topic_articles": [],
            "related_topics": []
        }
    
    data = result[0]
    topic_name = data.get("topic_name", topic_id)
    articles = data.get("articles", [])
    
    print(f"[SynthesisScout] THIS topic: {len(articles)} tier-3 articles (risk/opportunity)")
    for art in articles[:3]:
        print(f"   • {art['id']}")
    if len(articles) > 3:
        print(f"   ... +{len(articles) - 3} more")
    
    # Get RELATED topics via graph edges
    query_related = """
    MATCH (t:Topic {id: $topic_id})
    MATCH (t)-[:INFLUENCES|CORRELATES_WITH|PEERS]-(related:Topic)
    RETURN DISTINCT
        related.id as topic_id,
        related.name as topic_name,
        related.executive_summary as executive_summary
    """
    
    related_result = run_cypher(query_related, {"topic_id": topic_id})
    
    if not related_result:
        print(f"[SynthesisScout] No related topics found via graph edges")
        return {
            "topic_name": topic_name,
            "topic_id": topic_id,
            "topic_articles": articles,
            "related_topics": []
        }
    
    print(f"[SynthesisScout] Related topics: {len(related_result)} found")
    
    # Get tier 3 catalyst articles from EACH related topic
    related_topics = []
    topics_with_articles = []
    
    for rel in related_result:
        rel_id = rel['topic_id']
        
        query_related_articles = """
        MATCH (art:Article)-[r:ABOUT]->(t:Topic {id: $related_id})
        WHERE r.timeframe = $section
          AND r.importance_catalyst = 3
        RETURN 
            art.id as id,
            art.summary as summary,
            r.importance_catalyst as catalyst
        """
        
        rel_articles = run_cypher(query_related_articles, {
            "related_id": rel_id,
            "section": section
        })
        
        related_topics.append({
            "topic_id": rel['topic_id'],
            "topic_name": rel['topic_name'],
            "executive_summary": rel.get('executive_summary', ''),
            "articles": rel_articles if rel_articles else []
        })
        
        if rel_articles:
            topics_with_articles.append({
                'name': rel['topic_name'],
                'count': len(rel_articles),
                'sample_ids': [a['id'] for a in rel_articles[:2]]
            })
    
    # Summary of topics with articles
    if topics_with_articles:
        print(f"[SynthesisScout] Topics with tier-3 catalyst articles:")
        for t in topics_with_articles:
            sample = ', '.join(t['sample_ids'])
            print(f"   • {t['name']}: {t['count']} articles ({sample})")
    
    return {
        "topic_name": topic_name,
        "topic_id": topic_id,
        "topic_articles": articles,
        "related_topics": related_topics
    }
