"""
Graph API - Minimal Neo4j + LLM Operations
Internal API for Backend to call for Neo4j queries and LLM chat
"""
import os
import sys
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# Load environment variables from saga-graph/.env
load_dotenv()

# Import Neo4j functions only
from src.graph.ops.topic import get_topic_by_id
from src.analysis.utils.report_aggregator import aggregate_reports
from src.graph.neo4j_client import run_cypher

# Initialize FastAPI
app = FastAPI(
    title="Graph API",
    description="Internal API for Neo4j queries and LLM operations",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models - No LLM needed anymore!


# ============ NEO4J ENDPOINTS ============

@app.get("/neo/topics/all")
def get_all_topics():
    """Get all topics from Neo4j - NO LIMIT to see everything"""
    # First, get total count
    count_query = "MATCH (t:Topic) RETURN count(t) as total"
    count_result = run_cypher(count_query, {})
    total_count = count_result[0]["total"] if count_result else 0
    
    # Get ALL topics (no limit)
    query = """
    MATCH (t:Topic)
    RETURN t.id as id, t.name as name, t.importance as importance, 
           t.category as category, labels(t) as labels
    ORDER BY t.importance DESC, t.name ASC
    """
    
    results = run_cypher(query, {})
    topics = [
        {
            "id": r["id"],
            "name": r.get("name", r["id"]),
            "importance": r.get("importance", 0),
            "category": r.get("category", ""),
            "labels": r.get("labels", [])
        }
        for r in results
    ]
    
    return {
        "topics": topics, 
        "count": len(topics),
        "total_in_db": total_count,
        "showing_all": len(topics) == total_count
    }


@app.get("/neo/topic-names")
def get_topic_names(topic_ids: str = Query(...)):
    """Get topic names from Neo4j"""
    ids = [tid.strip() for tid in topic_ids.split(",")]
    topic_names = {}
    
    for topic_id in ids:
        topic = get_topic_by_id(topic_id)
        if topic:
            topic_names[topic_id] = topic.get("name", topic_id)
        else:
            topic_names[topic_id] = topic_id
    
    return topic_names


@app.get("/neo/query-articles")
def query_articles(topic_id: str = Query(...)):
    """Query Neo4j for article IDs related to a topic"""
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
    WHERE coalesce(a.priority, '') <> 'hidden'
    RETURN a.id as id
    ORDER BY a.published_date DESC
    LIMIT 50
    """
    
    results = run_cypher(query, {"topic_id": topic_id})
    article_ids = [r["id"] for r in results]
    
    return {"article_ids": article_ids}


@app.get("/neo/reports/{topic_id}")
def get_report(topic_id: str):
    """Get aggregated report for a topic - returns sections dict for collapsible UI"""
    try:
        sections = aggregate_reports(topic_id)
        topic = get_topic_by_id(topic_id)
        
        if not sections:
            raise HTTPException(status_code=404, detail="No reports found")
        
        topic_name = topic.get("name", topic_id) if topic else topic_id
        
        return {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "sections": sections
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============ CONTEXT BUILDING (NO LLM) ============

class ContextRequest(BaseModel):
    topic_id: Optional[str] = None
    include_full_articles: bool = False
    include_related_topics: bool = True
    max_articles: int = 20

@app.post("/neo/build-context")
def build_context(request: ContextRequest):
    """Build comprehensive context from Neo4j with all canonical fields"""
    topic_id = request.topic_id
    include_full = request.include_full_articles
    include_related = request.include_related_topics
    max_articles = request.max_articles
    try:
        if not topic_id:
            return {"context": None}
        
        # Get ALL topic properties
        topic = get_topic_by_id(topic_id)
        topic_name = topic.get("name", topic_id) if topic else topic_id
        
        # Get article statistics by canonical timeframes
        stats_query = """
        MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
        WHERE coalesce(a.priority, '') <> 'hidden'
        RETURN 
            count(a) as total_articles,
            count(CASE WHEN r.timeframe = 'fundamental' THEN 1 END) as fundamental_count,
            count(CASE WHEN r.timeframe = 'medium' THEN 1 END) as medium_count,
            count(CASE WHEN r.timeframe = 'current' THEN 1 END) as current_count
        """
        stats_result = run_cypher(stats_query, {"topic_id": topic_id})
        article_stats = stats_result[0] if stats_result else {
            "total_articles": 0,
            "fundamental_count": 0,
            "medium_count": 0,
            "current_count": 0
        }
        
        # Get articles with ALL ABOUT relationship properties
        articles_query = """
        MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
        WHERE coalesce(a.priority, '') <> 'hidden'
        RETURN 
            a.id as id,
            a.title as title, 
            a.summary as summary,
            a.published_at as published_at,
            a.source as source,
            a.priority as priority,
            r.timeframe as timeframe,
            r.importance_risk as importance_risk,
            r.importance_opportunity as importance_opportunity,
            r.importance_trend as importance_trend,
            r.importance_catalyst as importance_catalyst,
            r.motivation as motivation,
            r.implications as implications,
            r.created_at as linked_at
        ORDER BY a.published_at DESC
        LIMIT $max_articles
        """
        articles = run_cypher(articles_query, {"topic_id": topic_id, "max_articles": max_articles})
        
        # If full content requested, load article files
        if include_full and articles:
            from src.storage.article_loader import load_article
            for article in articles:
                try:
                    full_article = load_article(article["id"])
                    if full_article:
                        # Add full content fields
                        article["content"] = full_article.get("content", "")
                        article["full_text"] = full_article.get("full_text", "")
                except Exception as e:
                    # Continue without full content if loading fails
                    pass
        
        # Get relationship statistics
        relationships_query = """
        MATCH (t:Topic {id: $topic_id})
        OPTIONAL MATCH (t)-[:INFLUENCES]-(influenced:Topic)
        OPTIONAL MATCH (t)-[:CORRELATES_WITH]-(correlated:Topic)
        RETURN 
            count(DISTINCT influenced) as influences_count,
            count(DISTINCT correlated) as correlates_count
        """
        rel_result = run_cypher(relationships_query, {"topic_id": topic_id})
        relationships = rel_result[0] if rel_result else {
            "influences_count": 0,
            "correlates_count": 0
        }
        
        # Get ALL analysis reports (all canonical sections)
        try:
            reports = aggregate_reports(topic_id)
        except:
            reports = {}
        
        # Get related topics with their executive summaries
        related_topics = []
        if include_related:
            related_query = """
            MATCH (t:Topic {id: $topic_id})-[r]-(related:Topic)
            WHERE type(r) IN ['INFLUENCES', 'CORRELATES_WITH', 'PEERS', 'COMPONENT_OF']
            RETURN DISTINCT
                related.id as id,
                related.name as name,
                type(r) as relationship_type,
                coalesce(r.strength, 0.5) as strength
            ORDER BY strength DESC
            LIMIT 5
            """
            related_results = run_cypher(related_query, {"topic_id": topic_id})
            
            # For each related topic, get executive summary
            for rel in related_results:
                try:
                    rel_reports = aggregate_reports(rel["id"])
                    executive_summary = rel_reports.get("executive_summary", "")
                    if executive_summary:
                        related_topics.append({
                            "id": rel["id"],
                            "name": rel["name"],
                            "relationship": rel["relationship_type"],
                            "strength": rel["strength"],
                            "executive_summary": executive_summary[:500]  # First 500 chars
                        })
                except:
                    # Skip if no reports available
                    pass
        
        return {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "topic_data": topic,
            "articles": articles,
            "article_stats": article_stats,
            "relationships": relationships,
            "reports": reports,
            "related_topics": related_topics
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context building error: {str(e)}")


# ============ STRATEGY ANALYSIS TRIGGER ============

@app.post("/trigger/strategy-analysis")
def trigger_strategy_analysis(request: Dict[str, str]):
    """
    Trigger strategy analysis asynchronously.
    Called by Backend when user saves a strategy.
    """
    username = request.get("username")
    strategy_id = request.get("strategy_id")
    
    if not username or not strategy_id:
        raise HTTPException(400, "Missing username or strategy_id")
    
    # Run in background thread (non-blocking)
    import threading
    from src.strategy_agents.orchestrator import analyze_user_strategy
    
    def run_analysis():
        try:
            analyze_user_strategy(username, strategy_id)
        except Exception as e:
            print(f"❌ Strategy analysis failed for {username}/{strategy_id}: {e}")
    
    thread = threading.Thread(target=run_analysis, daemon=True)
    thread.start()
    
    return {"status": "triggered", "username": username, "strategy_id": strategy_id}


# ============ HEALTH ============

@app.get("/neo/health")
def health_check():
    """Check Neo4j connection"""
    try:
        result = run_cypher("RETURN 1 as test", {})
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "neo4j": f"error: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    print("\n🔷 Graph API starting on port 8001")
    print("📊 Neo4j queries + LLM operations only\n")
    uvicorn.run(app, host="0.0.0.0", port=8001)
