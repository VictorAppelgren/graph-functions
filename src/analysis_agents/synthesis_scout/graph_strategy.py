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

# How many catalyst articles to include (most recent)
MAX_CATALYST_ARTICLES = 10


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
    
    # Get THIS topic's tier 3 articles (risk OR opportunity perspectives only) - ALL timeframes, limit 5
    query_articles = """
    MATCH (t:Topic {id: $topic_id})
    MATCH (art:Article)-[r:ABOUT]->(t)
    WHERE (r.importance_risk = 3 OR r.importance_opportunity = 3)
    WITH t, art, r
    ORDER BY art.published_at DESC
    LIMIT 5
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
    
    result = run_cypher(query_articles, {"topic_id": topic_id})
    
    # Extract articles if found, but DON'T early-return (related-topics query is independent)
    if result:
        data = result[0]
        topic_name = data.get("topic_name", topic_id)
        articles = data.get("articles", [])
    else:
        topic_name = topic_id
        articles = []
    
    print(f"[SynthesisScout] THIS topic: {len(articles)} tier-3 articles (risk/opportunity)")
    for art in articles[:3]:
        print(f"   • {art['id']}")
    if len(articles) > 3:
        print(f"   ... +{len(articles) - 3} more")
    
    # First check: how many related topics exist at all?
    query_related_count = """
    MATCH (t:Topic {id: $topic_id})
    MATCH (t)-[r]-(related:Topic)
    RETURN type(r) as rel_type, count(DISTINCT related) as count
    """
    count_result = run_cypher(query_related_count, {"topic_id": topic_id})
    if count_result:
        print(f"[SynthesisScout] Related topic edges found:")
        for row in count_result:
            print(f"   • {row['rel_type']}: {row['count']} topics")
    else:
        print(f"[SynthesisScout] NO edges found for topic {topic_id}")
    
    # Get ALL related topics via graph edges WITH relationship type (critical for synthesis!)
    query_related = """
    MATCH (t:Topic {id: $topic_id})
    MATCH (t)-[r:INFLUENCES|CORRELATES_WITH|PEERS|COMPONENT_OF|HEDGES]-(related:Topic)
    WITH related, type(r) as rel_type,
         CASE
             WHEN type(r) = 'INFLUENCES' AND startNode(r) = t THEN 'outgoing'
             WHEN type(r) = 'INFLUENCES' AND endNode(r) = t THEN 'incoming'
             WHEN type(r) = 'COMPONENT_OF' AND startNode(r) = t THEN 'parent'
             WHEN type(r) = 'COMPONENT_OF' AND endNode(r) = t THEN 'child'
             ELSE 'bidirectional'
         END as direction
    RETURN DISTINCT
        related.id as topic_id,
        related.name as topic_name,
        related.executive_summary as executive_summary,
        rel_type as relationship_type,
        direction as relationship_direction
    """
    
    related_result = run_cypher(query_related, {"topic_id": topic_id})
    
    print(f"[SynthesisScout] Query returned {len(related_result) if related_result else 0} related topics")
    if related_result:
        with_summary = sum(1 for r in related_result if r.get('executive_summary'))
        print(f"[SynthesisScout] Topics with executive_summary: {with_summary}/{len(related_result)}")
    
    if not related_result:
        print(f"[SynthesisScout] No related topics found via graph edges")
        return {
            "topic_name": topic_name,
            "topic_id": topic_id,
            "topic_articles": articles,
            "related_topics": [],
            "catalyst_articles": []
        }
    
    print(f"[SynthesisScout] Related topics: {len(related_result)} found")
    
    # Collect ALL tier-3 catalyst articles from ALL related topics
    all_catalyst_articles = []
    
    for rel in related_result:
        rel_id = rel['topic_id']
        
        query_related_articles = """
        MATCH (art:Article)-[r:ABOUT]->(t:Topic {id: $related_id})
        WHERE r.importance_catalyst = 3
        RETURN 
            art.id as id,
            art.summary as summary,
            $related_name as source_topic
        ORDER BY art.published_at DESC
        LIMIT 5
        """
        
        rel_articles = run_cypher(query_related_articles, {
            "related_id": rel_id,
            "related_name": rel['topic_name']
        })
        
        if rel_articles:
            all_catalyst_articles.extend(rel_articles)
    
    print(f"[SynthesisScout] Total catalyst articles from related topics: {len(all_catalyst_articles)}")
    
    # Take the most recent catalyst articles (already sorted by published_at DESC per topic)
    # Sort all by recency and take top N
    top_catalyst_articles = all_catalyst_articles[:MAX_CATALYST_ARTICLES]
    print(f"[SynthesisScout] Using top {len(top_catalyst_articles)} most recent catalyst articles")
    
    # Build related_topics list with executive summaries AND relationship type (critical!)
    related_topics = [
        {
            "topic_id": rel['topic_id'],
            "topic_name": rel['topic_name'],
            "executive_summary": rel.get('executive_summary', ''),
            "relationship_type": rel.get('relationship_type', 'CORRELATES_WITH'),
            "relationship_direction": rel.get('relationship_direction', 'bidirectional'),
            "articles": []  # Articles are now in reranked_articles
        }
        for rel in related_result
    ]
    
    return {
        "topic_name": topic_name,
        "topic_id": topic_id,
        "topic_articles": articles,
        "related_topics": related_topics,
        "catalyst_articles": top_catalyst_articles  # Most recent catalyst articles
    }
