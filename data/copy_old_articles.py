"""
Article Migration Script
- Copies articles from old raw_data folder to current project
- Only copies articles that don't already exist (by ID and date)
- Maintains directory structure by date
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.app_logging import get_logger
from paths import get_raw_news_dir

logger = get_logger(__name__)

# HARDCODE YOUR OLD DATA PATH HERE
OLD_RAW_DATA_PATH = "/Users/xappvi/Documents/Documents - ml-221010-004/Information Refinment Generation 2024/NEW/IntelOrbis_Graph/saga-graph/saga-graph/data/raw_news"  # ← CHANGE THIS!

def get_article_id_from_file(file_path: str) -> str:
    """Extract argos_id from JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('argos_id', '')
    except Exception:
        return ""

def get_existing_article_ids_for_date(date_str: str) -> set[str]:
    """Get all article IDs that already exist for a specific date"""
    current_raw_dir = get_raw_news_dir()
    date_dir = os.path.join(current_raw_dir, date_str)
    
    existing_ids = set()
    if os.path.exists(date_dir):
        for filename in os.listdir(date_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(date_dir, filename)
                article_id = get_article_id_from_file(file_path)
                if article_id:
                    existing_ids.add(article_id)
    
    return existing_ids

def copy_articles_from_old_data():
    """Copy articles from old raw_data folder that don't exist in current project"""
    
    # Validate paths
    if not os.path.exists(OLD_RAW_DATA_PATH):
        logger.error(f"Old data path does not exist: {OLD_RAW_DATA_PATH}")
        logger.error("Please update OLD_RAW_DATA_PATH in the script!")
        return
    
    current_raw_dir = get_raw_news_dir()
    
    total_copied = 0
    total_skipped = 0
    total_errors = 0
    
    # Process each date directory in old data
    for date_dir_name in sorted(os.listdir(OLD_RAW_DATA_PATH)):
        old_date_dir = os.path.join(OLD_RAW_DATA_PATH, date_dir_name)
        
        # Skip if not a directory or not a date format
        if not os.path.isdir(old_date_dir) or len(date_dir_name) != 10:
            continue
        
        # Get existing article IDs for this date
        existing_ids = get_existing_article_ids_for_date(date_dir_name)
        
        # Create target date directory if needed
        target_date_dir = os.path.join(current_raw_dir, date_dir_name)
        os.makedirs(target_date_dir, exist_ok=True)
        
        # Process each article file in old date directory
        for filename in os.listdir(old_date_dir):
            if not filename.endswith('.json'):
                continue
                
            old_file_path = os.path.join(old_date_dir, filename)
            article_id = get_article_id_from_file(old_file_path)
            
            if not article_id:
                logger.error(f"No argos_id found in {filename}")
                total_errors += 1
                continue
                
            # Check if article already exists
            if article_id in existing_ids:
                total_skipped += 1
                continue
                
            # Copy the article
            target_file_path = os.path.join(target_date_dir, filename)
            try:
                shutil.copy2(old_file_path, target_file_path)
                total_copied += 1
            except Exception as e:
                logger.error(f"Failed to copy {filename}: {e}")
                total_errors += 1
    
    logger.info(f"🏆 Migration complete!")
    logger.info(f"  Files copied: {total_copied}")
    logger.info(f"  Files skipped: {total_skipped}")
    logger.info(f"  Errors: {total_errors}")

if __name__ == "__main__":
    logger.info("🚀 Starting article migration from old data folder")
    
    # Safety check
    if OLD_RAW_DATA_PATH == "/path/to/old/project/data/raw_news":
        logger.error("❌ Please update OLD_RAW_DATA_PATH in the script first!")
        sys.exit(1)
    
    copy_articles_from_old_data()
