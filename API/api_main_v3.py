"""
Argos API v2 - Neo4j Based API
Simplified user-based topic access with Neo4j backend
"""
import os
import sys
import json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# Import Neo4j functions
from src.graph.ops.topic import get_all_topics, get_topic_by_id
from src.articles.load_article import load_article
from src.analysis.utils.report_aggregator import aggregate_reports
from src.graph.neo4j_client import run_cypher
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier

# Initialize FastAPI
app = FastAPI(
    title="Argos API v2",
    description="Neo4j-based API for topic research and chat",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Complex LLM for chat
COMPLEX_LLM = get_llm(ModelTier.COMPLEX)

# Load users data
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")
with open(USERS_FILE, 'r') as f:
    USERS_DATA = json.load(f)

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    topic_id: str
    history: List[Dict[str, str]] = []

class User(BaseModel):
    username: str
    accessible_topics: List[str]

class Interest(BaseModel):
    id: str
    name: str

class Article(BaseModel):
    id: str
    title: str
    summary: str
    url: Optional[str] = None
    published_date: Optional[str] = None

class Report(BaseModel):
    topic_id: str
    topic_name: str
    sections: Dict[str, str]

class ChatResponse(BaseModel):
    response: str
    topic_id: str

# Utility functions
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Simple authentication against users.json"""
    for user in USERS_DATA["users"]:
        if user["username"] == username and user["password"] == password:
            return user
    return None

def get_articles_for_topic(topic_id: str, limit: int = 10) -> List[Dict]:
    """Get articles for a topic from Neo4j"""
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
    WHERE coalesce(a.priority, '') <> 'hidden'
    RETURN a.id as id, a.title as title, a.argos_summary as summary, 
           a.url as url, a.published_date as published_date
    ORDER BY a.published_date DESC
    LIMIT $limit
    """
    results = run_cypher(query, {"topic_id": topic_id, "limit": limit})
    
    articles = []
    for result in results:
        # Load full article data
        article_data = load_article(result["id"])
        if article_data:
            articles.append({
                "id": result["id"],
                "title": article_data.get("title", result["title"]),
                "summary": result["summary"] or article_data.get("argos_summary", ""),
                "url": result["url"] or article_data.get("url"),
                "published_date": result["published_date"]
            })
    
    return articles

# Context building is now handled directly in the chat endpoint for better separation

# Routes
@app.get("/")
def read_root():
    return {"status": "online", "service": "Argos API v2", "version": "2.0.0"}

@app.post("/login")
def login(request: LoginRequest):
    """Authenticate user and return user info"""
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "username": user["username"],
        "accessible_topics": user["accessible_topics"]
    }

@app.get("/interests")
def get_interests(username: str = Query(..., description="Username to get interests for")):
    """Get list of topics (interests) accessible to a user"""
    # Find user
    user = None
    for u in USERS_DATA["users"]:
        if u["username"] == username:
            user = u
            break
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get topic details for accessible topics
    interests = []
    for topic_id in user["accessible_topics"]:
        topic = get_topic_by_id(topic_id)
        if topic:
            interests.append({
                "id": topic_id,
                "name": topic.get("name", topic_id)
            })
    
    return {"interests": interests}

@app.get("/articles")
def get_articles(
    topic_id: str = Query(..., description="Topic ID to get articles for"),
    limit: int = Query(10, description="Maximum number of articles to return")
):
    """Get articles for a specific topic"""
    articles = get_articles_for_topic(topic_id, limit)
    return {"articles": articles}

@app.get("/articles/{article_id}")
def get_article(article_id: str):
    """Get a specific article by ID"""
    article_data = load_article(article_id)
    if not article_data:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {
        "id": article_id,
        "title": article_data.get("title", ""),
        "content": article_data.get("content", ""),
        "summary": article_data.get("argos_summary", ""),
        "url": article_data.get("url", ""),
        "published_date": article_data.get("published_date", "")
    }

@app.get("/reports/{topic_id}")
def get_report(topic_id: str, format: str = Query("markdown", description="Response format: markdown or json")):
    """Get full report for a topic using aggregate_reports"""
    try:
        reports = aggregate_reports(topic_id)
        topic = get_topic_by_id(topic_id)
        
        if not reports:
            raise HTTPException(status_code=404, detail="No reports found for this topic")
        
        topic_name = topic.get("name", topic_id) if topic else topic_id
        
        if format.lower() == "json":
            # Return JSON format (alternative)
            return {
                "topic_id": topic_id,
                "topic_name": topic_name,
                "sections": reports
            }
        else:
            # Return formatted markdown for frontend (default)
            markdown_parts = [
                f"# {topic_name}",
                ""
            ]
            
            # Add each section with proper markdown headers
            for section, content in reports.items():
                if content and content.strip():
                    section_title = section.replace('_', ' ').title()
                    markdown_parts.append(f"## {section_title}")
                    markdown_parts.append("")
                    markdown_parts.append(content.strip())
                    markdown_parts.append("")
            
            markdown_content = "\n".join(markdown_parts)
            
            # Log a large sample of the markdown content
            print(f"\n{'='*80}")
            print(f"MARKDOWN REPORT SAMPLE FOR: {topic_name} ({topic_id})")
            print(f"{'='*80}")
            print(f"Total length: {len(markdown_content)} characters")
            print(f"First 1000 characters:")
            print("-" * 60)
            print(markdown_content[:1000])
            print("-" * 60)
            if len(markdown_content) > 2000:
                print(f"Middle section (chars 1000-2000):")
                print("-" * 60)
                print(markdown_content[1000:2000])
                print("-" * 60)
            if len(markdown_content) > 3000:
                print(f"Last 500 characters:")
                print("-" * 60)
                print(markdown_content[-500:])
                print("-" * 60)
            print(f"{'='*80}\n")
            
            return {
                "topic_id": topic_id,
                "topic_name": topic_name,
                "markdown": markdown_content
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving report: {str(e)}")

@app.post("/chat")
def chat(request: ChatRequest):
    """Chat about a specific topic with context"""
    try:
        # Build separate context components for better prompt structure
        topic = get_topic_by_id(request.topic_id)
        topic_name = topic.get("name", request.topic_id) if topic else request.topic_id
        
        # Get reports and articles separately
        try:
            reports = aggregate_reports(request.topic_id)
        except Exception as e:
            reports = {}
        
        articles = get_articles_for_topic(request.topic_id, limit=8)
        
        # Build articles context (first for chain-of-thought)
        articles_context = ""
        if articles:
            articles_parts = ["═══ REAL-TIME MARKET INTELLIGENCE ═══", ""]
            for i, article in enumerate(articles, 1):
                articles_parts.append(f"◆ ARTICLE {i}: {article['title']}")
                if article['summary']:
                    articles_parts.append(f"Summary: {article['summary']}")
                articles_parts.append("")
            articles_context = "\n".join(articles_parts)
        
        # Build reports context (second for synthesis)
        reports_context = ""
        if reports:
            reports_parts = ["═══ COMPREHENSIVE ANALYSIS REPORTS ═══", ""]
            for section, content in reports.items():
                if content and content.strip():
                    section_title = section.replace('_', ' ').title()
                    reports_parts.append(f"【{section_title}】")
                    reports_parts.append(content.strip())
                    reports_parts.append("")
            reports_context = "\n".join(reports_parts)
        
        # Build chat history
        messages = []
        for msg in request.history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # Add current message
        messages.append(HumanMessage(content=request.message))
        
        # God-tier financial analysis chat prompt
        system_prompt = f"""You are Argos, an elite financial intelligence analyst. Your mission: distill complex market dynamics into razor-sharp, actionable insights.

═══ CORE DIRECTIVE ═══
Transform the world's most difficult financial questions into concise, decision-useful intelligence. You have access to comprehensive research and real-time market data. Your colleague needs immediate clarity, not lengthy explanations.

═══ RESPONSE FRAMEWORK ═══
1. **DIRECT ANSWER** (2-3 sentences max): Address their specific question immediately
2. **KEY INSIGHT** (1-2 bullets): Most critical non-obvious factor they should know
3. **RISK/OPPORTUNITY** (1-2 bullets): What could go wrong/right that others miss
4. **CONVERSATION CATALYST** (1 question): Guide them toward the most valuable next discussion

═══ MARKET INTELLIGENCE (Latest Developments) ═══
{articles_context}

═══ ANALYTICAL FRAMEWORK (Research Foundation) ═══
{reports_context}

═══ COMMUNICATION RULES ═══
• **BREVITY IS INTELLIGENCE**: Maximum 150 words total
• **SPECIFICITY OVER GENERALITY**: Use exact numbers, dates, probabilities
• **CONTRARIAN EDGE**: Challenge consensus where evidence supports it
• **ACTIONABLE ONLY**: Every sentence must drive decision-making
• **CONVERSATION LEADERSHIP**: End with a strategic question to advance their thinking

═══ CURRENT FOCUS ═══
Asset: {request.topic_id.upper()}
Question: "{request.message}"

═══ OUTPUT STRUCTURE ═══
**Answer:** [Direct response to their question]

**Key Insight:** [Most important non-obvious factor]

**Risk/Opportunity:** [Critical upside/downside they should monitor]

**Next:** [Strategic question to guide conversation]

Deliver maximum insight density. Every word must earn its place."""

        # Get LLM response
        response = COMPLEX_LLM.invoke(system_prompt)
        reply = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "response": reply.strip(),
            "topic_id": request.topic_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

# Health check for Neo4j connection
@app.get("/health")
def health_check():
    """Check if Neo4j connection is working"""
    try:
        result = run_cypher("RETURN 1 as test", {})
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "neo4j": f"error: {str(e)}"}

if __name__ == "__main__":
    print("\nArgos API v2 server starting...")
    print("API available at: http://0.0.0.0:8000")
    print("Docs available at: http://0.0.0.0:8000/docs\n")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
