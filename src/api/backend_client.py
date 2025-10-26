"""
Backend API Client - Simple interface to Backend API
Handles articles and user strategies
"""
import os
import requests
from typing import Dict, List, Optional, Any

# Backend API configuration
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("BACKEND_API_KEY", "")


# ============ ARTICLES ============

def store_article(article_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Send article to Backend API for file storage
    
    Args:
        article_data: Article dictionary with all fields
        
    Returns:
        {"argos_id": "...", "status": "stored"}
    """
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/articles",
            json=article_data,
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to store article to Backend API: {e}")
        return {"argos_id": article_data.get("argos_id", "unknown"), "status": "failed"}


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
    except Exception as e:
        print(f"⚠️  Failed to get article from Backend API: {e}")
        return None


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
            f"{BACKEND_URL}/strategies",
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
            f"{BACKEND_URL}/strategies/{strategy_id}",
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
            f"{BACKEND_URL}/strategies/{strategy_id}",
            json=strategy_data,
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️  Failed to update strategy in Backend API: {e}")
        return False
