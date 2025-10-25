"""
Daily Strategy Rewrite Orchestrator

Rewrites all user strategies once per day (triggered at 7am).
Tracks completion in stats file to prevent duplicate runs.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root and API to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
API_DIR = PROJECT_ROOT / "API"
sys.path.insert(0, str(API_DIR))

from src.custom_user_analysis.strategy_analyzer import generate_custom_user_analysis
from src.observability.pipeline_logging import master_statistics, master_log
from utils.app_logging import get_logger
import user_data_manager

logger = get_logger("custom_analysis.daily_rewrite")


def get_all_user_strategies() -> list[tuple[str, str]]:
    """
    Get all users and their strategies.
    
    Returns:
        List of (username, strategy_id) tuples
    """
    strategies = []
    
    # Get all users from API/users directory
    users_dir = API_DIR / "users"
    if not users_dir.exists():
        logger.warning(f"Users directory not found: {users_dir}")
        return strategies
    
    # Iterate through user directories
    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue
        
        username = user_dir.name
        
        # Skip archive directories
        if username == "archive":
            continue
        
        # Get all strategies for this user
        try:
            user_strategies = user_data_manager.list_strategies(username)
            for strategy in user_strategies:
                strategies.append((username, strategy["id"]))
        except Exception as e:
            logger.error(f"Failed to load strategies for user {username}: {e}")
            continue
    
    return strategies


def rewrite_all_user_strategies() -> dict:
    """
    Rewrite all user strategies.
    
    Returns:
        Dict with results: {
            "total": int,
            "succeeded": int,
            "failed": int,
            "errors": list[str]
        }
    """
    logger.info("=" * 80)
    logger.info("STARTING DAILY STRATEGY REWRITE")
    logger.info("=" * 80)
    
    # Get all strategies
    strategies = get_all_user_strategies()
    
    if not strategies:
        logger.warning("No user strategies found")
        return {
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "errors": []
        }
    
    logger.info(f"Found {len(strategies)} strategies across all users")
    
    # Track results
    results = {
        "total": len(strategies),
        "succeeded": 0,
        "failed": 0,
        "errors": []
    }
    
    # Rewrite each strategy
    for i, (username, strategy_id) in enumerate(strategies, 1):
        logger.info(f"[{i}/{len(strategies)}] Rewriting {username}/{strategy_id}...")
        
        try:
            # Generate analysis
            generate_custom_user_analysis(
                username=username,
                strategy_id=strategy_id,
                test=False  # Use full COMPLEX model
            )
            
            results["succeeded"] += 1
            logger.info(f"✅ Successfully rewrote {username}/{strategy_id}")
            
            # Track in stats
            master_statistics(custom_strategies_rewritten=1)
            
        except Exception as e:
            results["failed"] += 1
            error_msg = f"{username}/{strategy_id}: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(f"❌ Failed to rewrite {username}/{strategy_id}: {e}")
            
            # Track error
            master_statistics(errors=1)
    
    # Log summary
    logger.info("=" * 80)
    logger.info("DAILY STRATEGY REWRITE COMPLETE")
    logger.info(f"Total: {results['total']} | Succeeded: {results['succeeded']} | Failed: {results['failed']}")
    logger.info("=" * 80)
    
    # Log to master log
    master_log(
        f"Daily strategy rewrite complete | "
        f"total={results['total']} | "
        f"succeeded={results['succeeded']} | "
        f"failed={results['failed']}"
    )
    
    logger.info("=" * 80)
    logger.info("DAILY STRATEGY REWRITE COMPLETE")
    logger.info("=" * 80)

    return results


if __name__ == "__main__":
    # For testing
    results = rewrite_all_user_strategies()
    print(f"\n📊 Results: {results}")
