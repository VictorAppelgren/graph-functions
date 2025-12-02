#!/usr/bin/env python3
"""
Extract all articles from Neo4j backup to local filesystem.
Useful for syncing articles from local Neo4j backup to disk.
"""

import os
import json
from pathlib import Path
from neo4j import GraphDatabase
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Output directory - articles are stored in saga-be, not graph-functions!
GRAPH_FUNCTIONS_DIR = Path(__file__).parent
PROJECT_ROOT = GRAPH_FUNCTIONS_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "saga-be" / "data" / "raw_news"


def extract_articles():
    """Extract all articles from Neo4j and save to disk."""
    
    print(f"🔗 Connecting to Neo4j: {NEO4J_URI}")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            # Count total articles
            result = session.run("MATCH (a:Article) RETURN count(a) as count")
            total = result.single()["count"]
            print(f"📊 Found {total} articles in Neo4j")
            
            if total == 0:
                print("⚠️  No articles found in Neo4j backup!")
                return
            
            # Fetch all articles
            print(f"📥 Extracting articles...")
            result = session.run("""
                MATCH (a:Article)
                RETURN a.article_id as article_id,
                       a.title as title,
                       a.full_text as full_text,
                       a.url as url,
                       a.source as source,
                       a.published_at as published_at,
                       a.created_at as created_at
                ORDER BY a.created_at DESC
            """)
            
            # Create output directory
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            # Save articles
            saved = 0
            skipped = 0
            
            for record in result:
                article_id = record["article_id"]
                
                # Determine date folder
                published_at = record.get("published_at")
                if published_at:
                    try:
                        date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        date_folder = date_obj.strftime("%Y%m%d")
                    except:
                        date_folder = "unknown"
                else:
                    date_folder = "unknown"
                
                # Create date folder
                date_path = OUTPUT_DIR / date_folder
                date_path.mkdir(exist_ok=True)
                
                # Article file path
                article_path = date_path / f"{article_id}.json"
                
                # Skip if already exists
                if article_path.exists():
                    skipped += 1
                    continue
                
                # Build article object
                article = {
                    "article_id": article_id,
                    "title": record.get("title"),
                    "full_text": record.get("full_text"),
                    "url": record.get("url"),
                    "source": record.get("source"),
                    "published_at": published_at,
                    "created_at": record.get("created_at"),
                }
                
                # Save to disk
                with open(article_path, 'w', encoding='utf-8') as f:
                    json.dump(article, f, indent=2, ensure_ascii=False)
                
                saved += 1
                
                if saved % 100 == 0:
                    print(f"   💾 Saved {saved}/{total} articles...")
            
            print(f"\n✅ Extraction complete!")
            print(f"   📥 Saved: {saved} new articles")
            print(f"   ⏭️  Skipped: {skipped} existing articles")
            print(f"   📁 Location: {OUTPUT_DIR}")
            
            # Count total files now
            total_files = sum(1 for _ in OUTPUT_DIR.rglob("*.json"))
            print(f"   📊 Total articles on disk: {total_files}")
    
    finally:
        driver.close()


if __name__ == "__main__":
    print("=" * 60)
    print("📰 Article Extraction from Neo4j")
    print("=" * 60)
    print()
    
    extract_articles()
    
    print()
    print("=" * 60)
