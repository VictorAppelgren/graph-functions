"""
Admin API endpoints for observability data.
Serves daily statistics, logs, and trends.
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict

from src.observability.pipeline_logging import (
    load_stats_file,
    StatsFileModel,
    STATS_DIR,
    LOG_DIR
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================================
# DAILY STATS ENDPOINTS
# ============================================================================

@router.get("/stats/today")
def get_today_stats() -> StatsFileModel:
    """Get today's complete statistics including graph state and problems."""
    return load_stats_file()


@router.get("/stats/{date}")
def get_stats_by_date(date: str) -> StatsFileModel:
    """
    Get statistics for specific date.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-11-05")
    
    Returns:
        Complete stats file for that date
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Convert to filename format (YYYY_MM_DD)
    file_date = date.replace("-", "_")
    stats_file = Path(STATS_DIR) / f"statistics_{file_date}.json"
    
    if not stats_file.exists():
        raise HTTPException(status_code=404, detail=f"No statistics found for {date}")
    
    try:
        with open(stats_file, "r") as f:
            data = json.load(f)
            return StatsFileModel.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading stats file: {str(e)}")


@router.get("/stats/range")
def get_stats_range(days: int = 10) -> List[Dict]:
    """
    Get statistics for the last N days.
    
    Args:
        days: Number of days to retrieve (default: 10, max: 90)
    
    Returns:
        List of {date, stats} objects sorted by date (newest first)
    """
    if days > 90:
        raise HTTPException(status_code=400, detail="Maximum 90 days allowed")
    
    stats_dir = Path(STATS_DIR)
    if not stats_dir.exists():
        return []
    
    # Get all stats files
    stats_files = sorted(stats_dir.glob("statistics_*.json"), reverse=True)
    
    results = []
    for stats_file in stats_files[:days]:
        try:
            # Extract date from filename: statistics_2025_11_05.json
            filename = stats_file.stem  # Remove .json
            date_part = filename.replace("statistics_", "")
            date_str = date_part.replace("_", "-")  # Convert to YYYY-MM-DD
            
            with open(stats_file, "r") as f:
                data = json.load(f)
                results.append({
                    "date": date_str,
                    "stats": data
                })
        except Exception:
            continue
    
    return results


# ============================================================================
# TREND DATA ENDPOINTS (Optimized for charts)
# ============================================================================

@router.get("/trends/articles")
def get_articles_trend(days: int = 10) -> Dict:
    """
    Get article ingestion trends.
    
    Returns:
        {
            "dates": ["2025-11-05", "2025-11-04", ...],
            "articles_added": [10, 15, 8, ...],
            "articles_processed": [33, 42, 25, ...],
            "duplicates_skipped": [15, 20, 10, ...]
        }
    """
    stats_range = get_stats_range(days)
    
    dates = []
    articles_added = []
    articles_processed = []
    duplicates_skipped = []
    
    for item in reversed(stats_range):  # Oldest to newest for chart
        dates.append(item["date"])
        ingestion = item["stats"].get("today", {}).get("ingestion", {})
        articles_added.append(ingestion.get("articles_added", 0))
        articles_processed.append(ingestion.get("articles_processed", 0))
        duplicates_skipped.append(ingestion.get("duplicates_skipped", 0))
    
    return {
        "dates": dates,
        "articles_added": articles_added,
        "articles_processed": articles_processed,
        "duplicates_skipped": duplicates_skipped
    }


@router.get("/trends/analysis")
def get_analysis_trend(days: int = 10) -> Dict:
    """
    Get analysis generation trends.
    
    Returns:
        {
            "dates": ["2025-11-05", ...],
            "sections_written": [5, 8, 3, ...],
            "rewrite_attempts": [18, 22, 15, ...],
            "rewrite_succeeded": [0, 2, 1, ...]
        }
    """
    stats_range = get_stats_range(days)
    
    dates = []
    sections_written = []
    rewrite_attempts = []
    rewrite_succeeded = []
    
    for item in reversed(stats_range):
        dates.append(item["date"])
        analysis = item["stats"].get("today", {}).get("analysis", {})
        sections_written.append(analysis.get("sections_written", 0))
        rewrite_attempts.append(analysis.get("rewrite_attempts", 0))
        rewrite_succeeded.append(analysis.get("rewrite_succeeded", 0))
    
    return {
        "dates": dates,
        "sections_written": sections_written,
        "rewrite_attempts": rewrite_attempts,
        "rewrite_succeeded": rewrite_succeeded
    }


@router.get("/trends/graph")
def get_graph_trend(days: int = 10) -> Dict:
    """
    Get graph growth trends.
    
    Returns:
        {
            "dates": ["2025-11-05", ...],
            "topics": [36, 35, 34, ...],
            "articles": [150, 140, 135, ...],
            "connections": [500, 480, 460, ...]
        }
    """
    stats_range = get_stats_range(days)
    
    dates = []
    topics = []
    articles = []
    connections = []
    
    for item in reversed(stats_range):
        dates.append(item["date"])
        graph_state = item["stats"].get("graph_state", {})
        topics.append(graph_state.get("topics", 0))
        articles.append(graph_state.get("articles", 0))
        connections.append(graph_state.get("connections", 0))
    
    return {
        "dates": dates,
        "topics": topics,
        "articles": articles,
        "connections": connections
    }


@router.get("/trends/llm")
def get_llm_trend(days: int = 10) -> Dict:
    """
    Get LLM usage trends.
    
    Returns:
        {
            "dates": ["2025-11-05", ...],
            "simple": [50, 60, 45, ...],
            "medium": [20, 25, 18, ...],
            "complex": [5, 8, 3, ...]
        }
    """
    stats_range = get_stats_range(days)
    
    dates = []
    simple = []
    medium = []
    complex = []
    
    for item in reversed(stats_range):
        dates.append(item["date"])
        system = item["stats"].get("today", {}).get("system", {})
        simple.append(system.get("llm_simple_calls", 0))
        medium.append(system.get("llm_medium_calls", 0))
        complex.append(system.get("llm_complex_calls", 0))
    
    return {
        "dates": dates,
        "simple": simple,
        "medium": medium,
        "complex": complex,
        "total": [s + m + c for s, m, c in zip(simple, medium, complex)]
    }


@router.get("/trends/queries")
def get_queries_trend(days: int = 10) -> Dict:
    """
    Get query processing trends.
    
    Returns:
        {
            "dates": ["2025-11-05", ...],
            "queries": [10, 15, 8, ...]
        }
    """
    stats_range = get_stats_range(days)
    
    dates = []
    queries = []
    
    for item in reversed(stats_range):
        dates.append(item["date"])
        ingestion = item["stats"].get("today", {}).get("ingestion", {})
        queries.append(ingestion.get("queries", 0))
    
    return {
        "dates": dates,
        "queries": queries
    }


@router.get("/trends/errors")
def get_errors_trend(days: int = 10) -> Dict:
    """
    Get error trends.
    
    Returns:
        {
            "dates": ["2025-11-05", ...],
            "errors": [2, 0, 1, ...],
            "llm_failures": [1, 0, 0, ...]
        }
    """
    stats_range = get_stats_range(days)
    
    dates = []
    errors = []
    llm_failures = []
    
    for item in reversed(stats_range):
        dates.append(item["date"])
        system = item["stats"].get("today", {}).get("system", {})
        errors.append(system.get("errors", 0))
        llm_failures.append(system.get("llm_calls_failed", 0))
    
    return {
        "dates": dates,
        "errors": errors,
        "llm_failures": llm_failures
    }


# ============================================================================
# LOGS ENDPOINTS
# ============================================================================

@router.get("/logs/today")
def get_today_logs(lines: int = 100) -> Dict:
    """
    Get today's master log (last N lines).
    
    Args:
        lines: Number of lines to return (default: 100, max: 1000)
    
    Returns:
        {
            "date": "2025-11-05",
            "lines": ["...", "...", ...]
        }
    """
    if lines > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 lines allowed")
    
    log_file = Path(LOG_DIR) / f"master_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    if not log_file.exists():
        return {"date": datetime.now().strftime('%Y-%m-%d'), "lines": []}
    
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "lines": [line.strip() for line in all_lines[-lines:]]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")


@router.get("/logs/{date}")
def get_logs_by_date(date: str, lines: int = 100) -> Dict:
    """
    Get logs for specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
        lines: Number of lines to return (default: 100, max: 1000)
    """
    if lines > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 lines allowed")
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    log_file = Path(LOG_DIR) / f"master_{date}.log"
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"No logs found for {date}")
    
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return {
                "date": date,
                "lines": [line.strip() for line in all_lines[-lines:]]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")


# ============================================================================
# SUMMARY ENDPOINT (Dashboard Overview)
# ============================================================================

@router.get("/summary")
def get_admin_summary() -> Dict:
    """
    Get high-level summary for admin dashboard.
    
    Returns complete overview with today's stats, graph state, and recent trends.
    """
    today_stats = load_stats_file()
    trends_7d = get_stats_range(7)
    
    # Calculate 7-day totals
    articles_7d = sum(
        item["stats"].get("today", {}).get("ingestion", {}).get("articles_added", 0)
        for item in trends_7d
    )
    sections_7d = sum(
        item["stats"].get("today", {}).get("analysis", {}).get("sections_written", 0)
        for item in trends_7d
    )
    queries_7d = sum(
        item["stats"].get("today", {}).get("ingestion", {}).get("queries", 0)
        for item in trends_7d
    )
    
    return {
        "today": today_stats.model_dump(),
        "last_7_days": {
            "articles_added": articles_7d,
            "sections_written": sections_7d,
            "queries_processed": queries_7d
        },
        "available_dates": [item["date"] for item in trends_7d]
    }


# ============================================================================
# DEBUG ENDPOINTS (Development/Troubleshooting)
# ============================================================================

@router.get("/stats/debug/files")
def debug_stats_files():
    """
    Debug endpoint: List all available stats files.
    Helps troubleshoot why stats might be missing.
    """
    import os
    
    stats_path = Path(STATS_DIR)
    
    if not stats_path.exists():
        return {
            "stats_dir": str(stats_path.absolute()),
            "exists": False,
            "error": "Stats directory does not exist",
            "files": []
        }
    
    # List all JSON files
    files = sorted([f.name for f in stats_path.glob("*.json")])
    
    return {
        "stats_dir": str(stats_path.absolute()),
        "exists": True,
        "files": files,
        "count": len(files)
    }


@router.get("/stats/debug/latest")
def debug_latest_stats():
    """
    Debug endpoint: Show raw contents of the latest stats file.
    Helps verify if data is being written correctly.
    """
    import os
    
    stats_path = Path(STATS_DIR)
    
    if not stats_path.exists():
        return {
            "error": "Stats directory does not exist",
            "path": str(stats_path.absolute())
        }
    
    # Find all stats files
    files = sorted(list(stats_path.glob("*.json")))
    
    if not files:
        return {
            "error": "No stats files found",
            "path": str(stats_path.absolute()),
            "files_checked": str(list(stats_path.iterdir()))
        }
    
    # Get latest file
    latest_file = files[-1]
    
    try:
        with open(latest_file, 'r') as f:
            stats = json.load(f)
        
        return {
            "file": latest_file.name,
            "path": str(latest_file.absolute()),
            "size": latest_file.stat().st_size,
            "modified": datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat(),
            "stats": stats
        }
    except Exception as e:
        return {
            "error": f"Failed to read file: {str(e)}",
            "file": latest_file.name,
            "path": str(latest_file.absolute())
        }
