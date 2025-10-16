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

# Import strategy management
from API.user_data_manager import (
    list_strategies,
    load_strategy,
    create_strategy,
    update_strategy,
    delete_strategy
)

# Initialize FastAPI
app = FastAPI(
    title="Argos API v3",
    description="Neo4j-based API with strategy support and dual-context chat",
    version="3.0.0"
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
    history: List[Dict[str, str]] = []
    topic_id: Optional[str] = None      # For asset intelligence
    strategy_id: Optional[str] = None   # For user strategy
    username: Optional[str] = None      # Required when strategy_id provided

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
    publisher: Optional[str] = None

class Report(BaseModel):
    topic_id: str
    topic_name: str
    sections: Dict[str, str]

class ChatResponse(BaseModel):
    response: str
    topic_id: str

# Strategy models
class StrategyListItem(BaseModel):
    id: str
    asset: str
    target: str
    updated_at: str
    has_analysis: bool

class StrategyListResponse(BaseModel):
    strategies: List[StrategyListItem]

class CreateStrategyRequest(BaseModel):
    username: str
    asset_primary: str
    strategy_text: str
    position_text: str = ""
    target: str = ""

class UpdateStrategyRequest(BaseModel):
    username: str
    strategy_text: Optional[str] = None
    position_text: Optional[str] = None
    target: Optional[str] = None

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
           a.url as url, a.published_date as published_date, a.publisher as publisher
    ORDER BY a.published_date DESC
    LIMIT $limit
    """
    results = run_cypher(query, {"topic_id": topic_id, "limit": limit})
    
    articles = []
    for result in results:
        # Load full article data
        article_data = load_article(result["id"])
        if article_data:
            # Extract publisher from nested source.domain structure
            publisher = None
            if result.get("publisher"):
                publisher = result["publisher"]
            elif article_data.get("source") and isinstance(article_data["source"], dict):
                publisher = article_data["source"].get("domain")
            
            articles.append({
                "id": result["id"],
                "title": article_data.get("title", result["title"]),
                "summary": result["summary"] or article_data.get("argos_summary", ""),
                "url": result["url"] or article_data.get("url"),
                "published_date": result["published_date"] or article_data.get("pubDate"),
                "publisher": publisher
            })
    
    return articles

def build_asset_context(topic_id: str) -> str:
    """Build market intelligence context for an asset/topic."""
    topic = get_topic_by_id(topic_id)
    topic_name = topic.get("name", topic_id) if topic else topic_id
    
    # Get reports and articles
    try:
        reports = aggregate_reports(topic_id)
    except Exception:
        reports = {}
    
    articles = get_articles_for_topic(topic_id, limit=8)
    
    # Build context parts
    context_parts = ["═══ MARKET INTELLIGENCE ═══", f"Asset: {topic_name}", ""]
    
    # Add articles (real-time intelligence)
    if articles:
        context_parts.append("◆ RECENT DEVELOPMENTS:")
        for i, article in enumerate(articles, 1):
            context_parts.append(f"{i}. {article['title']}")
            if article['summary']:
                summary_preview = article['summary'][:200]
                context_parts.append(f"   {summary_preview}...")
        context_parts.append("")
    
    # Add reports (comprehensive analysis)
    if reports:
        context_parts.append("【ANALYSIS REPORTS】")
        for section, content in reports.items():
            if content and content.strip():
                section_title = section.replace('_', ' ').title()
                content_preview = content.strip()[:500]
                context_parts.append(f"\n{section_title}:")
                context_parts.append(content_preview + "...")
        context_parts.append("")
    
    return "\n".join(context_parts)


def build_strategy_context(username: str, strategy_id: str) -> str:
    """Build user strategy context."""
    strategy = load_strategy(username, strategy_id)
    
    context_parts = [
        "═══ USER'S TRADING STRATEGY ═══",
        f"Asset: {strategy['asset']['primary']}",
        "",
        "USER'S THESIS:",
        strategy['user_input']['strategy_text'],
        ""
    ]
    
    if strategy['user_input']['position_text']:
        context_parts.append("POSITION DETAILS:")
        context_parts.append(strategy['user_input']['position_text'])
        context_parts.append("")
    
    if strategy['user_input']['target']:
        context_parts.append(f"TARGET: {strategy['user_input']['target']}")
        context_parts.append("")
    
    # Add AI analysis if exists
    if strategy['analysis'].get('generated_at'):
        context_parts.append("═══ AI ANALYSIS ═══")
        if strategy['analysis'].get('fundamental'):
            fundamental_preview = strategy['analysis']['fundamental'][:300]
            context_parts.append(f"Fundamental: {fundamental_preview}...")
        if strategy['analysis'].get('current'):
            current_preview = strategy['analysis']['current'][:300]
            context_parts.append(f"Current: {current_preview}...")
        if strategy['analysis'].get('risks'):
            risks_preview = strategy['analysis']['risks'][:200]
            context_parts.append(f"Risks: {risks_preview}...")
        context_parts.append("")
        
        if strategy['analysis'].get('supporting_evidence'):
            context_parts.append("Supporting Evidence:")
            for ev in strategy['analysis']['supporting_evidence'][:3]:
                context_parts.append(f"  • {ev}")
        
        if strategy['analysis'].get('contradicting_evidence'):
            context_parts.append("Contradicting Evidence:")
            for ev in strategy['analysis']['contradicting_evidence'][:3]:
                context_parts.append(f"  • {ev}")
    
    return "\n".join(context_parts)

# Routes
@app.get("/")
def read_root():
    return {"status": "online", "service": "Argos API v3", "version": "3.0.0"}

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

@app.get("/strategies")
def get_strategies(username: str = Query(..., description="Username to get strategies for")):
    """List all strategies for a user"""
    try:
        strategies = list_strategies(username)
        return {"strategies": strategies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing strategies: {str(e)}")


@app.get("/strategies/{strategy_id}")
def get_strategy(
    strategy_id: str,
    username: str = Query(..., description="Username who owns the strategy")
):
    """Get full strategy details"""
    try:
        strategy = load_strategy(username, strategy_id)
        return strategy
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading strategy: {str(e)}")


@app.post("/strategies")
def create_new_strategy(request: CreateStrategyRequest):
    """Create a new strategy"""
    try:
        strategy = create_strategy(
            username=request.username,
            asset_primary=request.asset_primary,
            strategy_text=request.strategy_text,
            position_text=request.position_text,
            target=request.target
        )
        return strategy
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating strategy: {str(e)}")


@app.put("/strategies/{strategy_id}")
def update_existing_strategy(strategy_id: str, request: UpdateStrategyRequest):
    """Update an existing strategy"""
    try:
        strategy = update_strategy(
            username=request.username,
            strategy_id=strategy_id,
            strategy_text=request.strategy_text,
            position_text=request.position_text,
            target=request.target
        )
        return strategy
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating strategy: {str(e)}")


@app.delete("/strategies/{strategy_id}")
def delete_existing_strategy(
    strategy_id: str,
    username: str = Query(..., description="Username who owns the strategy")
):
    """Delete (archive) a strategy"""
    try:
        archived_name = delete_strategy(username, strategy_id)
        return {"message": "Strategy archived successfully", "archived_as": archived_name}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting strategy: {str(e)}")

@app.get("/articles")
def get_articles(
    topic_id: str = Query(..., description="Topic ID to get articles for"),
    limit: int = Query(10, description="Maximum number of articles to return")
):
    """Get articles for a specific topic"""
    articles = get_articles_for_topic(topic_id, limit)
    
    # Log article data to verify all fields are populated
    print(f"\n{'='*80}")
    print(f"GET /articles - Topic: {topic_id}, Count: {len(articles)}")
    print(f"{'='*80}")
    for i, article in enumerate(articles[:3], 1):  # Log first 3 articles
        print(f"\nArticle {i}:")
        print(f"  ID: {article.get('id', 'MISSING')}")
        print(f"  Title: {article.get('title', 'MISSING')[:60]}...")
        print(f"  Publisher: {article.get('publisher', 'MISSING')}")
        print(f"  Published: {article.get('published_date', 'MISSING')}")
        print(f"  URL: {article.get('url', 'MISSING')[:50]}...")
        print(f"  Summary: {len(article.get('summary', ''))} chars")
    if len(articles) > 3:
        print(f"\n... and {len(articles) - 3} more articles")
    print(f"{'='*80}\n")
    
    return {"articles": articles}

@app.get("/articles/{article_id}")
def get_article(article_id: str):
    """Get a specific article by ID"""
    article_data = load_article(article_id)
    if not article_data:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Extract publisher from nested source.domain structure
    publisher = ""
    if article_data.get("source") and isinstance(article_data["source"], dict):
        publisher = article_data["source"].get("domain", "")
    
    response = {
        "id": article_id,
        "title": article_data.get("title", ""),
        "content": article_data.get("content", ""),
        "summary": article_data.get("argos_summary", ""),
        "url": article_data.get("url", ""),
        "published_date": article_data.get("pubDate", ""),
        "publisher": publisher
    }
    
    # Log article data to verify all fields are populated
    print(f"\n{'='*80}")
    print(f"GET /articles/{article_id}")
    print(f"{'='*80}")
    print(f"ID: {response['id']}")
    print(f"Title: {response['title'][:80]}...")
    print(f"Publisher: {response['publisher'] or 'MISSING'}")
    print(f"Published: {response['published_date'] or 'MISSING'}")
    print(f"URL: {response['url'][:60]}...")
    print(f"Summary: {len(response['summary'])} chars")
    print(f"Content: {len(response['content'])} chars")
    print(f"{'='*80}\n")
    
    return response

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
    """Chat with dual context support: asset intelligence OR strategy OR both"""
    try:
        # Validate: if strategy_id provided, username is required
        if request.strategy_id and not request.username:
            raise HTTPException(
                status_code=400,
                detail="username is required when strategy_id is provided"
            )
        
        # Build context based on what's provided
        context_parts = []
        
        # PART 1: Asset/Topic Context
        if request.topic_id:
            asset_context = build_asset_context(request.topic_id)
            context_parts.append(asset_context)
        
        # PART 2: Strategy Context
        if request.strategy_id:
            try:
                strategy_context = build_strategy_context(request.username, request.strategy_id)
                context_parts.append(strategy_context)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=404,
                    detail=f"Strategy {request.strategy_id} not found for user {request.username}"
                )
        
        # Combine contexts
        full_context = "\n\n".join(context_parts) if context_parts else ""
        
        # Build chat history
        messages = []
        for msg in request.history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # Add current message
        messages.append(HumanMessage(content=request.message))
        
        # Determine context type for prompt
        if request.strategy_id and request.topic_id:
            context_type = "strategy + market intelligence"
        elif request.strategy_id:
            context_type = "user's trading strategy"
        elif request.topic_id:
            context_type = "market intelligence"
        else:
            context_type = "general financial knowledge"
        
        # Ultra-concise financial chat prompt
        system_prompt = f"""You are Argos, an elite financial intelligence analyst delivering razor-sharp insights.

═══ MISSION ═══
Transform complex financial questions into concise, actionable intelligence. Maximum 150 words.

═══ CONTEXT TYPE ═══
{context_type}

{full_context}

═══ RESPONSE FRAMEWORK ═══
**Answer:** [Direct 2-3 sentence response]

**Key Insight:** [Most critical non-obvious factor]

**Risk/Opportunity:** [What could go wrong/right]

**Next:** [Strategic question to advance discussion]

═══ RULES ═══
• BREVITY IS INTELLIGENCE: Max 150 words total
• SPECIFICITY: Use exact numbers, dates, probabilities
• Contrarian Edge: Challenge consensus where evidence supports
• ACTIONABLE ONLY: Every sentence drives decisions
• CONVERSATION LEADERSHIP: End with strategic question

Question: "{request.message}"

Deliver maximum insight density. Every word must earn its place."""
        
        # Get LLM response
        response = COMPLEX_LLM.invoke(system_prompt)
        reply = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "response": reply.strip(),
            "topic_id": request.topic_id,
            "strategy_id": request.strategy_id
        }
        
    except HTTPException:
        raise
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
    print("\nArgos API v3 server starting...")
    print("API available at: http://0.0.0.0:8000")
    print("Docs available at: http://0.0.0.0:8000/docs")
    print("\nNew features:")
    print("  • Strategy management (CRUD)")
    print("  • Dual-context chat (asset + strategy)")
    print("  • Ultra-concise 150-word responses\n")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
