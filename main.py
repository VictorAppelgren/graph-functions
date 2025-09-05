"""
Main orchestration script for Saga Graph pipeline.

This script runs the core pipeline flow:
1. Load all nodes from the graph database
2. Loop through each node
3. Trigger the pipeline for each node
4. Continue to next node

Normally scheduled via main_scheduler.py to run every even hour.
"""

import os
import sys
import datetime
from typing import List, Dict, Any, Optional
import random
import time
import math
import runpy
from func_add_topic.priority_policy import PRIORITY_POLICY

# Canonical import pattern: ensure project root (directory containing this main.py) is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import from V1 using absolute imports
from graph_utils.get_all_nodes import get_all_nodes
from perigon.news_ingestion_orchestrator import NewsIngestionOrchestrator
from utils import minimal_logging
from utils.master_log import master_log
from utils.query_overdue_seconds import query_overdue_seconds
from graph_db.db_driver import run_cypher
from entry_point_enrich_topic.topic_enrichment import backfill_topic_from_storage

# Configure logging
logger = minimal_logging.get_logger(__name__)



def run_pipeline() -> Dict[str, Any]:
    """
    Run the full Saga Graph pipeline.
    
    Returns:
        Dict with statistics about the run
    """

    orchestrator = NewsIngestionOrchestrator(debug=False)

    SLEEP_INTERVAL_MINUTES = 30

    # if ASSET is set, run only that node
    ASSET = ""
    # ASSET = "EURUSD"
    # Note: Asset filter applied at selection time per-iteration

    # Minimal bootstrap: if the graph has no Topic nodes, seed anchors once.
    # This executes the existing script's __main__ block to avoid any refactor.
    if len(get_all_nodes(fields=['id'])) < 1:
        logger.info("No Topic nodes found. Seeding anchors via user_anchor_nodes.py...")
        runpy.run_module("user_anchor_nodes", run_name="__main__")

    while True:
        loop_start_time = datetime.datetime.now()
        logger.info(f"Starting new pipeline cycle at {loop_start_time:%Y-%m-%d %H:%M:%S}")

        # Fresh fetch and selection each iteration
        nodes = get_all_nodes(fields=['id', 'name', 'type', 'query', 'queries', 'last_queried', 'importance'])
        assert nodes, "No Topic nodes found in graph."

        # Optional filter to a single asset
        if ASSET:
            nodes = [n for n in nodes if n['name'] == ASSET]
            assert nodes, f"No Topic node found for ASSET={ASSET}"

        # Compute SLA overdue seconds and select only overdue nodes
        overdues = [(n, query_overdue_seconds(n)) for n in nodes]
        overdue_nodes = [(n, o) for n, o in overdues if o > 0]

        if not overdue_nodes:
            # All nodes are within their SLA windows. Sleep until the earliest node becomes due (clamped 60s..30m).
            next_due_in = min(-o for _, o in overdues) if overdues else 300
            sleep_seconds = min(max(60, int(next_due_in)), 1800)
            logger.info(f"All nodes within SLA. Next due in {sleep_seconds // 60}m {sleep_seconds % 60}s. Sleeping {sleep_seconds}s...")
            time.sleep(sleep_seconds)
            continue

        # Pick the most overdue node
        node, node_overdue = max(overdue_nodes, key=lambda x: x[1])
        node_id = node['id']
        node_name = node['name']
        node_type = node['type']

        # Immediately claim by setting last_queried
        claim_res = run_cypher(
            "MATCH (t:Topic {id: $id}) SET t.last_queried = datetime() RETURN t.id AS id",
            {"id": node_id},
        )
        assert claim_res and claim_res[0]['id'] == node_id, f"Failed to claim node id={node_id}"

        logger.info("=================================================================================================")
        logger.info("=================================================================================================")
        logger.info(f"Processing node        : {node_name}")
        logger.info(f"Processing type        : {node_type}")
        logger.info(f"Processing importance  : {node['importance']}")
        logger.info(f"Processing last_queried: {node['last_queried']}")

        if not math.isfinite(node_overdue):
            # Missing or invalid last_queried -> treat as first run
            logger.info("Overdue by             : first run (no last_queried)")
        else:
            odelta = int(node_overdue // 60)
            if odelta >= 0:
                # Overdue by
                if odelta >= 1440:
                    logger.info(f"Overdue by             : {odelta // 1440}d {(odelta % 1440) // 60}h {odelta % 60}m")
                elif odelta >= 60:
                    logger.info(f"Overdue by             : {odelta // 60}h {odelta % 60}m")
                else:
                    logger.info(f"Overdue by             : {odelta}m")
            else:
                # Due in
                mins = -odelta
                if mins >= 1440:
                    logger.info(f"Due in                 : {mins // 1440}d {(mins % 1440) // 60}h {mins % 60}m")
                elif mins >= 60:
                    logger.info(f"Due in                 : {mins // 60}h {mins % 60}m")
                else:
                    logger.info(f"Due in                 : {mins}m")

        query = node['query']
        max_articles = PRIORITY_POLICY[int(node['importance'])]["number_of_articles"]
        orchestrator.run_query(node_name, query, max_articles=max_articles)

        # Increment queries after successful processing
        res = run_cypher(
            "MATCH (t:Topic {id: $id}) SET t.queries = coalesce(t.queries, 0) + 1 RETURN t.queries AS queries",
            {"id": node_id},
        )
        assert res, f"Failed to increment queries for node id={node_id}"
        logger.info(f"Node updated | id={node_id} | queries={res[0]['queries']}")

        # Opportunistic enrichment: backfill this asset from cold storage to build graph faster
        added_cnt = backfill_topic_from_storage(
            topic_id=node_id,
            test=False,
        )
        logger.info(f"Backfill completed for id={node_id} | added_articles={added_cnt}")

        logger.info(f"Pipeline run complete.")
        master_log("Pipeline complete | pipeline | run complete", queries=1)
    
        # Scheduler: no fixed cycle sleep; loop continues. Sleeping is handled when no nodes are overdue.
        logger.info(f"SLEEPING FUNCTION IS MISSING!!")
        
if __name__ == "__main__":
    run_pipeline()