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

# Import admin router
from API.admin_api import router as admin_router

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

# Include admin router
app.include_router(admin_router)

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
    """Get aggregated report for a topic"""
    try:
        reports = aggregate_reports(topic_id)
        topic = get_topic_by_id(topic_id)
        
        if not reports:
            raise HTTPException(status_code=404, detail="No reports found")
        
        topic_name = topic.get("name", topic_id) if topic else topic_id
        
        # Format as markdown
        markdown_parts = [f"# {topic_name}", ""]
        
        for section, content in reports.items():
            if content and content.strip():
                section_title = section.replace('_', ' ').title()
                markdown_parts.append(f"## {section_title}")
                markdown_parts.append("")
                markdown_parts.append(content.strip())
                markdown_parts.append("")
        
        markdown_content = "\n".join(markdown_parts)
        
        return {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "markdown": markdown_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============ CONTEXT BUILDING (NO LLM) ============

@app.post("/neo/build-context")
def build_context(topic_id: Optional[str] = None):
    """Build context from Neo4j - returns data only, NO LLM"""
    try:
        if not topic_id:
            return {"context": None}
        
        # Get topic data
        topic = get_topic_by_id(topic_id)
        topic_name = topic.get("name", topic_id) if topic else topic_id
        
        # Get recent articles from Neo4j
        query = """
        MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
        WHERE coalesce(a.priority, '') <> 'hidden'
        RETURN a.title as title, a.argos_summary as summary, a.published_date as date
        ORDER BY a.published_date DESC
        LIMIT 8
        """
        articles = run_cypher(query, {"topic_id": topic_id})
        
        # Get reports if available
        try:
            reports = aggregate_reports(topic_id)
        except:
            reports = {}
        
        return {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "articles": articles,
            "reports": reports,
            "topic_data": topic
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context building error: {str(e)}")


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
