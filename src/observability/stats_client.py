"""
Simple stats tracking client - sends events to backend API.
Fail fast and loud if tracking breaks.
"""
import requests
import os
from typing import Optional

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("BACKEND_API_KEY", "")


def track(event_type: str, message: Optional[str] = None):
    """
    Track a stat event by calling backend API.
    
    Args:
        event_type: Event name (e.g., "article_processed", "agent_analysis_triggered")
        message: Optional message for logs (e.g., "eurusd: Neo4j timeout")
    
    Usage:
        track("article_processed")
        track("article_rejected_no_topics", "Article ABC123: LLM found no relevant topics")
        track("agent_analysis_completed")
    
    Raises:
        Exception if backend API call fails (fail fast and loud)
    """
    params = {"event_type": event_type}
    if message:
        params["message"] = message
    
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/stats/track",
            params=params,
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
    except Exception as e:
        # Log the error with full details for debugging
        import sys
        print(f"❌ STATS TRACKING FAILED: {e}", file=sys.stderr)
        print(f"   URL: {BACKEND_URL}/api/stats/track", file=sys.stderr)
        print(f"   Event: {event_type}", file=sys.stderr)
        print(f"   API Key: {'SET' if API_KEY else 'NOT SET'}", file=sys.stderr)
        raise
