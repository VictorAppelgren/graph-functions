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
import socket
import requests
from typing import Dict, List, Optional, Any

# Backend API configuration
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")

# Worker identification (set by entrypoints)
_WORKER_ID: Optional[str] = None
_WORKER_TASK: Optional[str] = None


def set_worker_identity(worker_id: str) -> None:
    """Set worker ID (call once at entrypoint startup)."""
    global _WORKER_ID
    _WORKER_ID = worker_id


def set_worker_task(task: str) -> None:
    """Set current task (call when starting a task)."""
    global _WORKER_TASK
    _WORKER_TASK = task


def _get_headers() -> Dict[str, str]:
    """Build headers with API key and worker info."""
    headers = {}
    if BACKEND_API_KEY:
        headers["X-API-Key"] = BACKEND_API_KEY
    if _WORKER_ID:
        headers["X-Worker-ID"] = _WORKER_ID
        headers["X-Worker-Machine"] = socket.gethostname()
        if _WORKER_TASK:
            headers["X-Worker-Task"] = _WORKER_TASK
    return headers


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
            headers=_get_headers(),
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
            headers=_get_headers(),
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
            headers=_get_headers(),
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
            headers=_get_headers(),
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
            headers=_get_headers(),
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
            f"{BACKEND_URL}/api/users/{username}/strategies",
            headers=_get_headers(),
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
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}",
            headers=_get_headers(),
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
        response = requests.put(
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}",
            json=strategy_data,
            headers=_get_headers(),
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
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/topics",
            json=topics,
            headers=_get_headers(),
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
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/topics",
            headers=_get_headers(),
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
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/analysis",
            json=analysis,
            headers=_get_headers(),
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
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/analysis",
            headers=_get_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to get analysis from Backend API: {e}")
        return None


def save_dashboard_question(username: str, strategy_id: str, question: str) -> bool:
    """Save dashboard question for strategy"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/question",
            json={"question": question},
            headers=_get_headers(),
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️  Failed to save dashboard question to Backend API: {e}")
        return False


def get_dashboard_question(username: str, strategy_id: str) -> Optional[str]:
    """Get dashboard question for strategy"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/question",
            headers=_get_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("question")
    except Exception as e:
        print(f"⚠️  Failed to get dashboard question from Backend API: {e}")
        return None


def get_analysis_history(username: str, strategy_id: str) -> List[Dict[str, Any]]:
    """Get all analysis history for strategy"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/analysis/history",
            headers=_get_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("history", [])
    except Exception as e:
        print(f"⚠️  Failed to get analysis history from Backend API: {e}")
        return []


# ============ EXPLORATION FINDINGS ============

def get_strategy_findings(username: str, strategy_id: str, mode: str) -> List[Dict[str, Any]]:
    """Get current exploration findings (risks or opportunities) for strategy.

    Args:
        username: User who owns the strategy
        strategy_id: Strategy ID
        mode: "risk" or "opportunity"

    Returns:
        List of findings (max 3), empty list if none or error
    """
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/findings/{mode}",
            headers=_get_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("findings", [])
    except Exception as e:
        print(f"⚠️  Failed to get {mode} findings from Backend API: {e}")
        return []


def save_strategy_finding(
    username: str,
    strategy_id: str,
    mode: str,
    finding: Dict[str, Any],
    replaces: Optional[int] = None
) -> bool:
    """Save an exploration finding to strategy.

    Args:
        username: User who owns the strategy
        strategy_id: Strategy ID
        mode: "risk" or "opportunity"
        finding: The finding dict (headline, rationale, flow_path, evidence, confidence)
        replaces: If None, add new (max 3). If 1/2/3, replace that slot.

    Returns:
        True if saved successfully
    """
    try:
        # Add replaces to finding if specified
        payload = finding.copy()
        if replaces is not None:
            payload["replaces"] = replaces

        response = requests.post(
            f"{BACKEND_URL}/api/users/{username}/strategies/{strategy_id}/findings/{mode}",
            json=payload,
            headers=_get_headers(),
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️  Failed to save {mode} finding to Backend API: {e}")
        return False
