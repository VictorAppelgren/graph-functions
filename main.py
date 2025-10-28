"""
Main orchestration script for Saga Graph pipeline.

This script runs the core pipeline flow:
1. Load all topics from the graph database
2. Loop through each topic
3. Trigger the pipeline for each topic
4. Continue to next topic

Normally scheduled via main_scheduler.py to run every even hour.
"""

# Load .env file FIRST before any other imports
from utils.env_loader import load_env
load_env()

import datetime
from typing import Dict, Any
import time
import math
from src.graph.policies.priority import PRIORITY_POLICY, PriorityLevel

# Import from V1 using absolute imports
from src.graph.ops.topic import get_all_topics
from src.clients.perigon.news_ingestion_orchestrator import NewsIngestionOrchestrator
from utils import app_logging
from src.observability.pipeline_logging import master_log, load_stats_file, master_statistics
from src.graph.scheduling.query_overdue import query_overdue_seconds
from src.graph.neo4j_client import run_cypher
from worker.workflows.topic_enrichment import backfill_topic_from_storage
from src.analysis.orchestration.should_rewrite import should_rewrite
from src.custom_user_analysis.daily_rewrite_orchestrator import rewrite_all_user_strategies

logger = app_logging.get_logger(__name__)


def format_time_delta(timestamp_str: str) -> str:
    """Format time delta from Neo4j datetime string to human readable format."""
    if not timestamp_str or timestamp_str == "Never":
        return "Never"
    
    try:
        # Parse Neo4j datetime format
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - dt
        
        total_minutes = int(delta.total_seconds() // 60)
        
        if total_minutes < 60:
            return f"{total_minutes}m ago"
        elif total_minutes < 1440:  # < 24 hours
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}h {minutes}m ago" if minutes > 0 else f"{hours}h ago"
        else:  # >= 24 hours
            days = total_minutes // 1440
            hours = (total_minutes % 1440) // 60
            return f"{days}d {hours}h ago" if hours > 0 else f"{days}d ago"
    except Exception:
        return "Unknown"


def run_pipeline() -> Dict[str, Any]:
    """
    Run the full Saga Graph pipeline.

    Returns:
        Dict with statistics about the run
    """

    orchestrator = NewsIngestionOrchestrator(debug=False, scrape_enabled=False)

    # if ASSET is set, run only that topic
    ASSET = ""
    # ASSET = "EURUSD"
    # Note: Asset filter applied at selection time per-iteration

    # Bootstrap check: if the graph has no topics, run bootstrap automatically
    just_bootstrapped = False
    if len(get_all_topics(fields=["id"])) < 1:
        logger.warning("="*80)
        logger.warning("NO TOPICS FOUND IN GRAPH!")
        logger.warning("Running bootstrap script automatically...")
        logger.warning("="*80)
        from src.start_scripts.bootstrap_graph import main as bootstrap_main
        bootstrap_main()
        logger.info("✅ Bootstrap complete! Starting pipeline...")
        just_bootstrapped = True

    while True:
        loop_start_time = datetime.datetime.now()
        logger.info(
            f"Starting new pipeline cycle at {loop_start_time:%Y-%m-%d %H:%M:%S}"
        )

        # Daily strategy rewrite (once per day at 7am)
        if loop_start_time.hour >= 7 and not just_bootstrapped:
            stats = load_stats_file()
            flag_status = stats.today.custom_analysis.daily_rewrite_completed
            logger.debug(f"Daily rewrite check: hour={loop_start_time.hour}, flag={flag_status}")
            
            if not flag_status:
                # Set flag IMMEDIATELY to prevent other processes from starting
                master_statistics(daily_rewrite_completed=True)
                logger.info("🔄 Daily rewrite started (flag set to prevent duplicates)")
                try:
                    results = rewrite_all_user_strategies()
                    logger.info(f"✅ Daily rewrite: {results['succeeded']}/{results['total']} succeeded")
                except Exception as e:
                    logger.error(f"❌ Daily rewrite failed: {e}")
            else:
                logger.debug("Daily rewrite already completed today, skipping")
        elif just_bootstrapped:
            logger.info("⏭️  Skipping daily rewrite (just bootstrapped)")
            just_bootstrapped = False  # Reset flag after first iteration

        # Fresh fetch and selection each iteration
        topics = get_all_topics(
            fields=[
                "id",
                "name",
                "type",
                "query",
                "queries",
                "last_queried",
                "last_updated",
                "last_analyzed",
                "importance",
            ]
        )
        assert topics, "No Topic topics found in graph."

        # Optional filter to a single asset
        if ASSET:
            topics = [n for n in topics if n["name"] == ASSET]
            assert topics, f"No Topic topic found for ASSET={ASSET}"

        # Log all topic IDs for diagnostics
        logger.info(f"📋 Loaded {len(topics)} topics from database")
        logger.debug(f"Topic IDs: {[t['id'] for t in topics[:10]]}...")  # Show first 10
        
        # Compute SLA overdue seconds and select only overdue topics
        overdues = [(n, query_overdue_seconds(n)) for n in topics]
        overdue_topics = [(n, o) for n, o in overdues if o > 0]

        if not overdue_topics:
            # All topics are within their SLA windows. Sleep until the earliest topic becomes due (clamped 60s..30m).
            next_due_in = min(-o for _, o in overdues) if overdues else 300
            sleep_seconds = min(max(60, int(next_due_in)), 1800)
            logger.info(
                f"All topics within SLA. Next due in {sleep_seconds // 60}m {sleep_seconds % 60}s. Sleeping {sleep_seconds}s..."
            )
            time.sleep(sleep_seconds)
            continue

        # Pick the most overdue topic
        topic, topic_overdue = max(overdue_topics, key=lambda x: x[1])
        topic_id = topic["id"]
        topic_name = topic["name"]
        topic_type = topic["type"]

        # Log what we're trying to claim
        logger.info(f"🎯 Attempting to claim topic: id='{topic_id}', name='{topic_name}'")
        logger.debug(f"Topic data: {topic}")
        
        # Immediately claim by setting last_queried
        claim_res = run_cypher(
            "MATCH (t:Topic {id: $id}) SET t.last_queried = datetime() RETURN t.id AS id",
            {"id": topic_id},
        )
        
        # Skip if claim fails (topic might have been deleted or race condition)
        if not claim_res or not claim_res[0] or claim_res[0].get("id") != topic_id:
            logger.error(f"❌ CLAIM FAILED for topic id='{topic_id}' name='{topic_name}'")
            logger.error(f"Claim query returned: {claim_res}")
            logger.error(f"Expected id: '{topic_id}' (type: {type(topic_id).__name__})")
            
            # Try to find if topic exists with different query
            check_res = run_cypher(
                "MATCH (t:Topic) WHERE t.id = $id OR t.name = $name RETURN t.id AS id, t.name AS name",
                {"id": topic_id, "name": topic_name},
            )
            logger.error(f"Topic existence check: {check_res}")
            
            continue  # Skip to next topic in the loop

        logger.info(
            "================================================================================================="
        )
        logger.info(
            "================================================================================================="
        )
        logger.info(f"Processing topic        : {topic_name}")
        logger.info(f"Processing type        : {topic_type}")
        logger.info(f"Processing importance  : {topic['importance']}")
        logger.info(f"Processing last_queried: {topic['last_queried']}")
        logger.info(f"Processing last_analyzed: {format_time_delta(topic.get('last_analyzed', 'Never'))}")

        if not math.isfinite(topic_overdue):
            # Missing or invalid last_queried -> treat as first run
            logger.info("Overdue by             : first run (no last_queried)")
        else:
            odelta = int(topic_overdue // 60)
            if odelta >= 0:
                # Overdue by
                if odelta >= 1440:
                    logger.info(
                        f"Overdue by             : {odelta // 1440}d {(odelta % 1440) // 60}h {odelta % 60}m"
                    )
                elif odelta >= 60:
                    logger.info(
                        f"Overdue by             : {odelta // 60}h {odelta % 60}m"
                    )
                else:
                    logger.info(f"Overdue by             : {odelta}m")
            else:
                # Due in
                mins = -odelta
                if mins >= 1440:
                    logger.info(
                        f"Due in                 : {mins // 1440}d {(mins % 1440) // 60}h {mins % 60}m"
                    )
                elif mins >= 60:
                    logger.info(f"Due in                 : {mins // 60}h {mins % 60}m")
                else:
                    logger.info(f"Due in                 : {mins}m")

        query = topic["query"]
        importance = PriorityLevel(int(topic["importance"]))  # fails early if invalid
        policy = PRIORITY_POLICY[importance]
        max_articles = policy.number_of_articles

        orchestrator.run_query(topic_name, query, max_articles=max_articles)

        # Increment queries after successful processing
        res = run_cypher(
            "MATCH (t:Topic {id: $id}) SET t.queries = coalesce(t.queries, 0) + 1 RETURN t.queries AS queries",
            {"id": topic_id},
        )
        assert res, f"Failed to increment queries for topic id={topic_id}"
        logger.info(f"topic updated | id={topic_id} | queries={res[0]['queries']}")

        # Opportunistic enrichment: backfill this asset from cold storage to build graph faster
        added_cnt = backfill_topic_from_storage(
            topic_id=topic_id,
            test=False,
        )
        logger.info(
            f"Backfill completed for id={topic_id} | added_articles={added_cnt}"
        )

        logger.info("Pipeline run complete.")
        master_log("Pipeline complete | pipeline | run complete", queries=1)

        # Scheduler: no fixed cycle sleep; loop continues. Sleeping is handled when no topics are overdue.
        logger.info("SLEEPING FUNCTION IS MISSING!!")


if __name__ == "__main__":
    run_pipeline()
