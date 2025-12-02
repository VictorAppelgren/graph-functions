"""
Backend API Client - Simple interface to Backend API
Handles articles and user strategies

ARCHITECTURE:
- All backend routes use /api/ prefix
- BACKEND_API_URL changes per environment:
  - Local dev: http://localhost:8000
  - Server internal: http://saga-apis:8000 (Docker DNS)
  - Server external: http://SERVER-IP (public IP)
- All calls use /api/* paths for consistency
- API key checked by NGINX (external) or trusted (internal)
"""
import os
import requests
from typing import Dict, List, Optional, Any

# Backend API configuration
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("BACKEND_API_KEY", "")


# ============ ARTICLES ============

def ingest_article(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ingest article with automatic deduplication.
    
    Backend checks if article exists (by URL + date):
    - If exists: Returns existing article ID
    - If new: Generates ID, stores article, returns new ID
    
    Args:
        article_data: Article dictionary (NO argos_id needed!)
        
    Returns:
        {
            "argos_id": "ABC123XYZ",
            "status": "created" | "existing",
            "data": {...}
        }
    """
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/articles/ingest",
            json=article_data,
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to ingest article: {e}")
        raise


def get_article(article_id: str) -> Optional[Dict[str, Any]]:
    """Get article from Backend API"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/articles/{article_id}",
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        # 404 is expected during bootstrap - local fallback will handle it
        if e.response.status_code == 404:
            return None
        print(f"⚠️  Failed to get article from Backend API: {e}")
        return None
    except Exception as e:
        print(f"⚠️  Failed to get article from Backend API: {e}")
        return None


def search_articles_by_keywords(
    keywords: List[str],
    limit: int = 5,
    min_keyword_hits: int = 3,
    exclude_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Search articles by keywords via Backend API.
    
    Args:
        keywords: List of keywords to search for
        limit: Maximum number of results (default 5)
        min_keyword_hits: Minimum keyword matches required (default 3)
        exclude_ids: Article IDs to exclude from results
    
    Returns:
        List of dicts with article_id, matched_keywords, hit_count, text_preview
    
    Example:
        results = search_articles_by_keywords(
            keywords=["fed", "rate", "inflation"],
            limit=5,
            min_keyword_hits=2
        )
        # Returns: [{"article_id": "ABC", "matched_keywords": [...], ...}, ...]
    """
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/articles/search",
            json={
                "keywords": keywords,
                "limit": limit,
                "min_keyword_hits": min_keyword_hits,
                "exclude_ids": exclude_ids or []
            },
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=30  # Longer timeout for search
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception as e:
        print(f"⚠️  Failed to search articles from Backend API: {e}")
        return []


def get_article_storage_stats() -> Dict[str, int]:
    """Get article storage statistics from Backend API"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/articles/storage/stats",
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to get storage stats from Backend API: {e}")
        return {"total_raw_articles": 0}


# ============ USERS & STRATEGIES ============

def get_all_users() -> List[str]:
    """Get all usernames from Backend API"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/users",
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        users = response.json().get("users", [])
        return [u["username"] for u in users]
    except Exception as e:
        print(f"⚠️  Failed to get users from Backend API: {e}")
        return []


def get_user_strategies(username: str) -> List[Dict[str, Any]]:
    """Get all strategies for a user"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/strategies",
            params={"username": username},
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("strategies", [])
    except Exception as e:
        print(f"⚠️  Failed to get strategies from Backend API: {e}")
        return []


def get_strategy(username: str, strategy_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific strategy"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/strategies/{strategy_id}",
            params={"username": username},
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to get strategy from Backend API: {e}")
        return None


def update_strategy(username: str, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
    """Update a strategy"""
    try:
        # Add username to strategy data
        strategy_data["username"] = username
        
        response = requests.put(
            f"{BACKEND_URL}/api/strategies/{strategy_id}",
            json=strategy_data,
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️  Failed to update strategy in Backend API: {e}")
        return False


def save_strategy_topics(username: str, strategy_id: str, topics: Dict[str, List[str]]) -> bool:
    """Save topic mapping for strategy"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/{username}/strategies/{strategy_id}/topics",
            json=topics,
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️  Failed to save topics to Backend API: {e}")
        return False


def get_strategy_topics(username: str, strategy_id: str) -> Optional[Dict[str, List[str]]]:
    """Get topic mapping for strategy"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/users/{username}/strategies/{strategy_id}/topics",
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to get topics from Backend API: {e}")
        return None


def save_strategy_analysis(username: str, strategy_id: str, analysis: Dict[str, Any]) -> bool:
    """Save analysis results (updates latest + appends to history)"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/{username}/strategies/{strategy_id}/analysis",
            json=analysis,
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️  Failed to save analysis to Backend API: {e}")
        return False


def get_latest_analysis(username: str, strategy_id: str) -> Optional[Dict[str, Any]]:
    """Get latest analysis for strategy"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/users/{username}/strategies/{strategy_id}/analysis",
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to get analysis from Backend API: {e}")
        return None
