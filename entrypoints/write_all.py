#!/usr/bin/env python3
"""
Write All - Server 3 Entrypoint

Runs the full analysis pipeline for all topics AND user strategies.
Designed to run continuously on a dedicated writing server.

Continuous loop priorities (--loop mode):
1. Daily strategy analysis (6am) - uses COMPLEX tier (DeepSeek)
2. Topic rewrites when new Tier 3 articles exist - uses MEDIUM tier (120B)
3. Exploration (risks/opportunities) - uses MEDIUM tier (120B, free via OpenRouter)

The loop is interleaved: after each exploration, it checks if any writes are needed.
This keeps the system responsive to new articles while continuously improving
risk/opportunity coverage.

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

from typing import Optional, List
from src.graph.ops.topic import get_all_topics
from src.analysis_agents.orchestrator import analysis_rewriter_with_agents
from src.strategy_agents.orchestrator import analyze_user_strategy
from src.api.backend_client import get_user_strategies, get_all_users, get_strategy, get_strategy_topics
from src.graph.neo4j_client import run_cypher
from src.config.worker_mode import get_mode_description
from src.observability.stats_client import track
from src.analysis.rewrite_policy import should_rewrite_topic
from utils import app_logging
from dateutil import parser as date_parser

logger = app_logging.get_logger(__name__)

# Track last strategy run date to ensure once-per-day at 6am
_last_strategy_date = None


def strategy_needs_update(username: str, strategy_id: str) -> tuple[bool, str]:
    """
    Check if strategy needs reanalysis.

    A strategy needs update if ANY of its linked topics have been
    analyzed more recently than the strategy's last analysis.

    This ensures strategy analysis reflects the latest topic insights.

    Args:
        username: User who owns the strategy
        strategy_id: Strategy ID to check

    Returns:
        Tuple of (needs_update: bool, reason: str)
    """
    # Get strategy details
    strategy = get_strategy(username, strategy_id)
    if not strategy:
        return False, "strategy_not_found"

    strategy_last_analyzed = strategy.get("latest_analysis", {}).get("analyzed_at")
    if not strategy_last_analyzed:
        return True, "never_analyzed"

    # Parse strategy timestamp
    try:
        strategy_analyzed_dt = date_parser.parse(strategy_last_analyzed)
        if strategy_analyzed_dt.tzinfo is not None:
            strategy_analyzed_dt = strategy_analyzed_dt.replace(tzinfo=None)
    except Exception as e:
        logger.warning(f"Could not parse strategy last_analyzed_at: {e}")
        return True, "invalid_timestamp"

    # Get linked topics
    topics_data = get_strategy_topics(username, strategy_id)
    if not topics_data:
        return False, "no_linked_topics"

    topic_ids = topics_data.get("topics", [])
    if not topic_ids:
        return False, "no_linked_topics"

    # Check if any linked topic has newer analysis via Neo4j
    query = """
    UNWIND $topic_ids AS topic_id
    MATCH (t:Topic {id: topic_id})
    WHERE t.last_analyzed IS NOT NULL
    RETURN t.id AS topic_id, t.last_analyzed AS last_analyzed
    """
    result = run_cypher(query, {"topic_ids": topic_ids})

    for row in result or []:
        topic_last_analyzed = row.get("last_analyzed")
        if not topic_last_analyzed:
            continue

        try:
            # Handle both string and Neo4j datetime types
            if isinstance(topic_last_analyzed, str):
                topic_analyzed_dt = date_parser.parse(topic_last_analyzed)
                if topic_analyzed_dt.tzinfo is not None:
                    topic_analyzed_dt = topic_analyzed_dt.replace(tzinfo=None)
            else:
                # Neo4j datetime object
                topic_analyzed_dt = datetime.datetime(
                    topic_last_analyzed.year, topic_last_analyzed.month, topic_last_analyzed.day,
                    topic_last_analyzed.hour, topic_last_analyzed.minute, topic_last_analyzed.second
                )

            # If topic was analyzed after strategy, strategy needs update
            if topic_analyzed_dt > strategy_analyzed_dt:
                return True, f"topic_{row['topic_id']}_updated"
        except Exception as e:
            logger.warning(f"Could not compare timestamps for topic {row.get('topic_id')}: {e}")
            continue

    return False, "no_topic_updates"


def run_topic_exploration(topic_id: str) -> None:
    """
    Ensure topic has 3 risks and 3 opportunities.

    - If < 3 findings: run exploration until we have 3
    - If already 3: run once to potentially improve/refresh
    """
    from src.graph.ops.topic_findings import get_topic_findings
    from src.exploration_agent.orchestrator import explore_topic

    for mode in ["risk", "opportunity"]:
        existing = get_topic_findings(topic_id, mode)
        count = len(existing)

        # Run 3 times if < 3, otherwise run 1 time to refresh
        runs = 3 - count if count < 3 else 1

        logger.info(f"🔍 {topic_id}: {count} {mode}s exist, running {runs} exploration(s)")

        for i in range(runs):
            try:
                logger.info(f"   🔍 Explore {topic_id} {mode} ({i+1}/{runs})")
                explore_topic(topic_id, mode)
                track("exploration_completed", f"{topic_id}:{mode}")
            except Exception as e:
                logger.warning(f"   ⚠️ Exploration failed for {topic_id} {mode}: {e}")
                track("exploration_failed", f"{topic_id}:{mode}")


def run_strategy_exploration(username: str, strategy_id: str) -> None:
    """
    Ensure strategy has 3 risks and 3 opportunities.

    - If < 3 findings: run exploration until we have 3
    - If already 3: run once to potentially improve/refresh
    """
    from src.api.backend_client import get_strategy_findings
    from src.exploration_agent.orchestrator import explore_strategy

    for mode in ["risk", "opportunity"]:
        existing = get_strategy_findings(username, strategy_id, mode)
        count = len(existing)

        # Run 3 times if < 3, otherwise run 1 time to refresh
        runs = 3 - count if count < 3 else 1

        logger.info(f"🔍 {username}/{strategy_id}: {count} {mode}s exist, running {runs} exploration(s)")

        for i in range(runs):
            try:
                logger.info(f"   🔍 Explore {username}/{strategy_id} {mode} ({i+1}/{runs})")
                explore_strategy(username, strategy_id, mode)
                track("exploration_completed", f"{username}/{strategy_id}:{mode}")
            except Exception as e:
                logger.warning(f"   ⚠️ Exploration failed for {username}/{strategy_id} {mode}: {e}")
                track("exploration_failed", f"{username}/{strategy_id}:{mode}")


def write_single_topic(topic_id: str, new_article_ids: Optional[List[str]] = None) -> bool:
    """
    Run full analysis for a single topic. Returns True if successful.

    Args:
        topic_id: Topic to analyze
        new_article_ids: Optional list of NEW article IDs to highlight to agents.
                        If provided, agents will focus on these new articles.

    Note: Exploration is handled separately in run_one_exploration() to allow
    interleaving with write tasks for better responsiveness.
    """
    try:
        logger.info(f"🎯 Writing analysis for: {topic_id}")
        if new_article_ids:
            logger.info(f"   📰 Highlighting {len(new_article_ids)} NEW articles to agents")

        # Pass new_article_ids to orchestrator so agents know what's new
        analysis_rewriter_with_agents(topic_id, new_article_ids=new_article_ids)
        logger.info(f"✅ Completed: {topic_id}")
        track("agent_analysis_completed", f"{topic_id}")
        return True
    except Exception as e:
        logger.error(f"Failed {topic_id}: {e}")
        return False


def write_all_topics(shuffle: bool = True, force: bool = False) -> dict:
    """
    Run full analysis for all topics that need updates.

    Smart rewrite logic (unless force=True):
    - Only rewrites topics with NEW Tier 3 articles since last analysis
    - Respects cooldown period (MIN_REWRITE_INTERVAL_HOURS)
    - Highlights new articles to agents for focused analysis

    Args:
        shuffle: Randomize topic order for balanced coverage
        force: If True, skip rewrite checks and write all topics

    Returns:
        dict with success/failure/skipped counts
    """
    all_topics = get_all_topics(fields=["id", "name"])
    topic_ids = [t["id"] for t in all_topics]

    logger.info(f"{'='*60}")
    logger.info(f"📊 WRITE ALL TOPICS - Checking {len(topic_ids)} topics")
    if force:
        logger.info("⚠️  FORCE MODE: Skipping rewrite checks")
    logger.info(f"{'='*60}")

    if shuffle:
        random.shuffle(topic_ids)
        logger.info("🎲 Shuffled order for balanced coverage")

    stats = {
        "success": 0,
        "failed": 0,
        "skipped_no_new": 0,
        "skipped_cooldown": 0,
        "total": len(topic_ids)
    }

    for i, topic_id in enumerate(topic_ids, 1):
        logger.info(f"[{i}/{len(topic_ids)}] Checking {topic_id}")

        # Smart rewrite check (unless force mode)
        if not force:
            should_write, reason, new_article_ids = should_rewrite_topic(topic_id)

            if not should_write:
                if reason == "no_new_articles":
                    stats["skipped_no_new"] += 1
                elif reason == "cooldown":
                    stats["skipped_cooldown"] += 1
                continue
        else:
            new_article_ids = None  # Force mode doesn't track new articles

        # Rewrite with highlighted new articles
        if write_single_topic(topic_id, new_article_ids=new_article_ids):
            stats["success"] += 1
        else:
            stats["failed"] += 1

    logger.info(f"{'='*60}")
    logger.info(f"🎉 TOPICS COMPLETE:")
    logger.info(f"   ✅ Rewritten: {stats['success']}")
    logger.info(f"   ❌ Failed: {stats['failed']}")
    logger.info(f"   ⏭️  Skipped (no new articles): {stats['skipped_no_new']}")
    logger.info(f"   ⏸️  Skipped (cooldown): {stats['skipped_cooldown']}")
    logger.info(f"{'='*60}")

    return stats


def write_all_strategies() -> dict:
    """
    Run strategy analysis for all users.

    Smart rewrite logic:
    - Only analyzes strategies whose linked topics have newer analysis
    - Prevents rewriting strategies when no underlying data changed

    Returns:
        dict with success/failure/skipped counts
    """
    all_users = get_all_users()

    if not all_users:
        logger.warning("No users found, skipping strategy analysis")
        return {"success": 0, "failed": 0, "skipped": 0, "total": 0}

    logger.info(f"{'='*60}")
    logger.info(f"📈 WRITE ALL STRATEGIES - Checking {len(all_users)} users")
    logger.info(f"{'='*60}")

    stats = {"success": 0, "failed": 0, "skipped": 0, "total": 0}

    for username in all_users:
        user_strategies = get_user_strategies(username)
        stats["total"] += len(user_strategies)
        logger.info(f"User {username}: {len(user_strategies)} strategies")

        for strategy in user_strategies:
            strategy_id = strategy['id']

            # Check if strategy needs update
            needs_update, reason = strategy_needs_update(username, strategy_id)

            if not needs_update:
                logger.info(f"  ⏭️  Skip {username}/{strategy_id}: {reason}")
                stats["skipped"] += 1
                track("strategy_analysis_skipped", f"{username}/{strategy_id}:{reason}")
                continue

            try:
                logger.info(f"  🔄 Analyzing {username}/{strategy_id}: {reason}")
                track("strategy_analysis_triggered", f"{username}/{strategy_id}:{reason}")

                # Run exploration BEFORE analysis so findings are available as context
                run_strategy_exploration(username, strategy_id)

                analyze_user_strategy(username, strategy_id)
                stats["success"] += 1
                track("strategy_analysis_completed", f"{username}/{strategy_id}")
            except Exception as e:
                logger.error(f"  ❌ Failed {username}/{strategy_id}: {e}")
                stats["failed"] += 1

    logger.info(f"{'='*60}")
    logger.info(f"🎉 STRATEGIES COMPLETE:")
    logger.info(f"   ✅ Analyzed: {stats['success']}")
    logger.info(f"   ❌ Failed: {stats['failed']}")
    logger.info(f"   ⏭️  Skipped (no updates): {stats['skipped']}")
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
            last_analyzed = strategy.get("latest_analysis", {}).get("analyzed_at")
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


def find_topic_needing_rewrite() -> Optional[tuple[str, List[str]]]:
    """
    Find ONE topic that needs rewriting.
    Returns (topic_id, new_article_ids) or None if nothing needs rewriting.
    """
    from src.analysis.rewrite_policy import should_rewrite_topic

    all_topics = get_all_topics(fields=["id"])
    random.shuffle(all_topics)  # Randomize for balanced coverage

    for topic in all_topics:
        topic_id = topic["id"]
        should_write, reason, new_article_ids = should_rewrite_topic(topic_id)
        if should_write:
            return (topic_id, new_article_ids)

    return None


def run_one_exploration() -> bool:
    """
    Run ONE exploration (risk or opportunity) for ONE strategy or topic.
    Strategies are prioritized (user-facing).

    Returns True if exploration was run, False if nothing to explore.
    """
    from src.exploration_agent.orchestrator import explore_topic, explore_strategy
    from src.api.backend_client import get_strategy_findings
    from src.graph.ops.topic_findings import get_topic_findings

    # Priority 1: Strategies (user-facing)
    all_users = get_all_users()
    all_strategies = []
    for username in all_users:
        for strategy in get_user_strategies(username):
            all_strategies.append((username, strategy['id']))

    random.shuffle(all_strategies)  # Randomize for balanced coverage

    for username, strategy_id in all_strategies:
        for mode in ["risk", "opportunity"]:
            try:
                logger.info(f"🔍 Exploring {mode} for strategy {username}/{strategy_id}")
                explore_strategy(username, strategy_id, mode)
                track("exploration_completed", f"{username}/{strategy_id}:{mode}")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Exploration failed for {username}/{strategy_id} {mode}: {e}")
                track("exploration_failed", f"{username}/{strategy_id}:{mode}")

    # Priority 2: Topics
    all_topics = get_all_topics(fields=["id"])
    random.shuffle(all_topics)

    for topic in all_topics:
        topic_id = topic["id"]
        for mode in ["risk", "opportunity"]:
            try:
                logger.info(f"🔍 Exploring {mode} for topic {topic_id}")
                explore_topic(topic_id, mode)
                track("exploration_completed", f"{topic_id}:{mode}")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Exploration failed for {topic_id} {mode}: {e}")
                track("exploration_failed", f"{topic_id}:{mode}")

    return False


def run_continuous_loop(delay_between_cycles: int = 60):
    """
    Run continuously with interleaved priorities:

    1. Daily strategy analysis (6am) - uses COMPLEX (DeepSeek)
    2. Topic rewrites when new Tier 3 articles exist - uses MEDIUM (120B)
    3. Exploration (risks/opportunities) - uses MEDIUM (120B, free via OpenRouter)

    The loop checks for writes after each exploration to stay responsive.
    """
    global _last_strategy_date

    logger.info("🔄 CONTINUOUS MODE - Write server running")
    logger.info("   Priority 1: Daily strategy analysis (6am)")
    logger.info("   Priority 2: Topic rewrites (new Tier 3 articles)")
    logger.info("   Priority 3: Exploration (risks/opportunities)")

    while True:
        cycle_start = datetime.datetime.now()

        # PRIORITY 1: Daily strategy analysis (6am)
        if should_run_daily_strategies():
            logger.info(f"\n{'='*60}")
            logger.info("🌅 6am strategy analysis triggered")
            logger.info(f"{'='*60}")
            track("daily_strategy_analysis_started")
            strategy_stats = write_all_strategies()
            _last_strategy_date = cycle_start.date()
            track("daily_strategy_analysis_completed", f"{strategy_stats['success']}/{strategy_stats['total']}")

        # PRIORITY 2: Check for ONE topic that needs rewriting
        topic_to_write = find_topic_needing_rewrite()
        if topic_to_write:
            topic_id, new_article_ids = topic_to_write
            logger.info(f"\n{'='*60}")
            logger.info(f"📝 REWRITING topic: {topic_id} ({len(new_article_ids)} new articles)")
            logger.info(f"{'='*60}")
            write_single_topic(topic_id, new_article_ids=new_article_ids)

        # PRIORITY 3: Exploration (always runs, tries to find better risks/opportunities)
        run_one_exploration()


def main():
    parser = argparse.ArgumentParser(description="Write all topic analyses and strategies")
    parser.add_argument("--topic", type=str, help="Run single topic instead of all")
    parser.add_argument("--strategies", action="store_true", help="Run strategies only")
    parser.add_argument("--topics-only", action="store_true", help="Run topics only (no strategies)")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--no-shuffle", action="store_true", help="Don't randomize topic order")
    parser.add_argument("--delay", type=int, default=60, help="Seconds between loops (default: 60)")
    parser.add_argument("--force", action="store_true", help="Force rewrite all topics (skip cooldown/new article checks)")
    
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
        write_all_topics(shuffle=not args.no_shuffle, force=args.force)


if __name__ == "__main__":
    # Register worker identity for tracking
    from src.api.backend_client import set_worker_identity
    set_worker_identity("worker-writer")

    main()
