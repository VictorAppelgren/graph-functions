#!/usr/bin/env python3
"""
Market Data Workflow Runner

Simple script to run the market data workflow for all topics.
Can be run with limits for testing.
"""

import sys
import os
import argparse

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from worker.workflows.market_data_workflow import run_market_data_workflow
from utils import app_logging

logger = app_logging.get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run Market Data Workflow")
    parser.add_argument(
        "--limit", 
        type=int, 
        help="Limit number of topics to process (for testing)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be processed without making changes"
    )
    
    args = parser.parse_args()
    
    print("🚀 MARKET DATA WORKFLOW RUNNER")
    print("=" * 50)
    
    if args.limit:
        print(f"📊 Processing {args.limit} topics (limited)")
    else:
        print("📊 Processing ALL topics")
        
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    
    try:
        stats = run_market_data_workflow(limit=args.limit)
        
        print(f"\n✅ Workflow completed successfully!")
        print(f"📈 Final Stats: {stats}")
        
    except Exception as e:
        logger.error(f"❌ Workflow failed: {e}")
        print(f"❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
