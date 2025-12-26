#!/usr/bin/env python3
"""
Write All - Server 3 Entrypoint

Runs the full analysis pipeline for all topics AND user strategies.
Designed to run continuously on a dedicated writing server with a larger model.

Daily schedule:
- 06:00: Write all user strategies (once per day)
- Continuous: Write topic analyses for topics that need updates

Usage:
    python write_all.py              # Run all topics + strategies once
    python write_all.py --loop       # Run continuously (recommended for Server 3)
    python write_all.py --topic XYZ  # Run single topic only
    python write_all.py --strategies # Run strategies only
"""

import sys
import os
import argparse
import random
import time
import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.env_loader import load_env
load_env()

from src.graph.ops.topic import get_all_topics
from src.analysis_agents.orchestrator import analysis_rewriter_with_agents
from src.strategy_agents.orchestrator import analyze_user_strategy
from src.api.backend_client import get_user_strategies, get_all_users
from src.config.worker_mode import get_mode_description
from src.observability.stats_client import track
from utils import app_logging
from dateutil import parser as date_parser

logger = app_logging.get_logger(__name__)

# Track last strategy run date to ensure once-per-day at 6am
_last_strategy_date = None


def write_single_topic(topic_id: str) -> bool:
    """Run full analysis for a single topic. Returns True if successful."""
    try:
        logger.info(f"🎯 Writing analysis for: {topic_id}")
        analysis_rewriter_with_agents(topic_id)
        logger.info(f"✅ Completed: {topic_id}")
        return True
    except Exception as e:
        logger.error(f"Failed {topic_id}: {e}")
        return False


def write_all_topics(shuffle: bool = True) -> dict:
    """
    Run full analysis for all topics.
    
    Returns:
        dict with success/failure counts
    """
    all_topics = get_all_topics(fields=["id", "name"])
    topic_ids = [t["id"] for t in all_topics]
    
    logger.info(f"{'='*60}")
    logger.info(f"📊 WRITE ALL TOPICS - Found {len(topic_ids)} topics")
    logger.info(f"{'='*60}")
    
    if shuffle:
        random.shuffle(topic_ids)
        logger.info("🎲 Shuffled order for balanced coverage")
    
    stats = {"success": 0, "failed": 0, "total": len(topic_ids)}
    
    for i, topic_id in enumerate(topic_ids, 1):
        logger.info(f"[{i}/{len(topic_ids)}] Processing {topic_id}")
        
        if write_single_topic(topic_id):
            stats["success"] += 1
        else:
            stats["failed"] += 1
    
    logger.info(f"{'='*60}")
    logger.info(f"🎉 TOPICS COMPLETE: {stats['success']}/{stats['total']} succeeded, {stats['failed']} failed")
    logger.info(f"{'='*60}")
    
    return stats


def write_all_strategies() -> dict:
    """
    Run strategy analysis for all users.
    
    Returns:
        dict with success/failure counts
    """
    all_users = get_all_users()
    
    if not all_users:
        logger.warning("No users found, skipping strategy analysis")
        return {"success": 0, "failed": 0, "total": 0}
    
    logger.info(f"{'='*60}")
    logger.info(f"📈 WRITE ALL STRATEGIES - Found {len(all_users)} users")
    logger.info(f"{'='*60}")
    
    stats = {"success": 0, "failed": 0, "total": 0}
    
    for username in all_users:
        user_strategies = get_user_strategies(username)
        stats["total"] += len(user_strategies)
        logger.info(f"User {username}: {len(user_strategies)} strategies")
        
        for strategy in user_strategies:
            try:
                logger.info(f"  Analyzing {username}/{strategy['id']}")
                analyze_user_strategy(username, strategy['id'])
                stats["success"] += 1
                track("strategy_analysis_completed", f"{username}/{strategy['id']}")
            except Exception as e:
                logger.error(f"  Failed {username}/{strategy['id']}: {e}")
                stats["failed"] += 1
    
    logger.info(f"{'='*60}")
    logger.info(f"🎉 STRATEGIES COMPLETE: {stats['success']}/{stats['total']} succeeded, {stats['failed']} failed")
    logger.info(f"{'='*60}")
    
    return stats


def should_run_daily_strategies() -> bool:
    """
    Check if we should run daily strategy analysis.
    Returns True if it's after 6am AND we haven't run today yet.
    """
    global _last_strategy_date
    
    now = datetime.datetime.now()
    today = now.date()
    
    # Not yet 6am? Skip
    if now.hour < 6:
        return False
    
    # Already ran today? Skip
    if _last_strategy_date == today:
        return False
    
    # Check if any strategy needs analysis (wasn't analyzed after 6am today)
    today_6am = datetime.datetime.combine(today, datetime.time(6, 0))
    
    all_users = get_all_users()
    if not all_users:
        return False
    
    for username in all_users:
        strategies = get_user_strategies(username)
        for strategy in strategies:
            last_analyzed = strategy.get("last_analyzed_at")
            if not last_analyzed:
                return True
            analyzed_time = date_parser.parse(last_analyzed)
            # Make analyzed_time naive if it has timezone info
            if analyzed_time.tzinfo is not None:
                analyzed_time = analyzed_time.replace(tzinfo=None)
            if analyzed_time < today_6am:
                return True
    
    # All strategies already analyzed today
    _last_strategy_date = today
    return False


def run_continuous_loop(delay_between_cycles: int = 60):
    """
    Run continuously:
    - At 6am: Run all strategies (once per day)
    - Always: Run all topics, then wait and repeat
    """
    global _last_strategy_date
    
    logger.info("🔄 CONTINUOUS MODE - Write server running")
    logger.info(f"   Strategies: Daily at 6am")
    logger.info(f"   Topics: Continuous with {delay_between_cycles}s delay between cycles")
    
    while True:
        cycle_start = datetime.datetime.now()
        logger.info(f"\n{'='*60}")
        logger.info(f"📅 Cycle started at {cycle_start:%Y-%m-%d %H:%M:%S}")
        logger.info(f"{'='*60}")
        
        # Check for daily strategy run (6am)
        if should_run_daily_strategies():
            logger.info("🌅 6am strategy run triggered")
            track("daily_strategy_analysis_started")
            strategy_stats = write_all_strategies()
            _last_strategy_date = cycle_start.date()
            track("daily_strategy_analysis_completed", f"{strategy_stats['success']}/{strategy_stats['total']}")
        
        # Always run topics
        topic_stats = write_all_topics(shuffle=True)
        
        # Wait before next cycle
        logger.info(f"⏳ Waiting {delay_between_cycles}s before next cycle...")
        time.sleep(delay_between_cycles)


def main():
    parser = argparse.ArgumentParser(description="Write all topic analyses and strategies")
    parser.add_argument("--topic", type=str, help="Run single topic instead of all")
    parser.add_argument("--strategies", action="store_true", help="Run strategies only")
    parser.add_argument("--topics-only", action="store_true", help="Run topics only (no strategies)")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--no-shuffle", action="store_true", help="Don't randomize topic order")
    parser.add_argument("--delay", type=int, default=60, help="Seconds between loops (default: 60)")
    
    args = parser.parse_args()
    
    # Log startup
    logger.info(f"🚀 WRITE ALL - Mode: {get_mode_description()}")
    
    if args.topic:
        # Single topic mode
        write_single_topic(args.topic)
    elif args.strategies:
        # Strategies only
        write_all_strategies()
    elif args.loop:
        # Continuous mode (Server 3)
        run_continuous_loop(delay_between_cycles=args.delay)
    else:
        # Single run: strategies (if needed) + topics
        if not args.topics_only and should_run_daily_strategies():
            write_all_strategies()
        write_all_topics(shuffle=not args.no_shuffle)


if __name__ == "__main__":
    # Register worker identity for tracking
    from src.api.backend_client import set_worker_identity
    set_worker_identity("worker-writer")

    main()
