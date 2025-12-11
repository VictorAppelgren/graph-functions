#!/usr/bin/env python3
"""
COMPREHENSIVE Article Sync Diagnostic

Compares Neo4j graph with Backend API storage to understand:
- What's in Neo4j but not in storage?
- What's in storage but not in Neo4j?
- Time distribution of articles
- When did the divergence happen?
"""
import sys
import os
import json
import random
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.env_loader import load_env
load_env()

from src.graph.neo4j_client import run_cypher
from src.api.backend_client import get_article
import requests
from utils.app_logging import get_logger

logger = get_logger(__name__)

# Backend API config
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://167.172.185.204:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "785fc6c1647ff650b6b611509cc0a8f47009e6b743340503519d433f111fcf12")


def get_all_storage_ids():
    """Get ALL article IDs from Backend API storage"""
    print("\n📦 Fetching ALL article IDs from Backend API storage...")
    print(f"   API URL: {BACKEND_API_URL}")
    print(f"   API Key: {BACKEND_API_KEY[:10]}...{BACKEND_API_KEY[-10:] if len(BACKEND_API_KEY) > 20 else 'SHORT'}")
    
    all_ids = set()
    offset = 0
    limit = 500
    
    # First, try to get storage stats
    try:
        stats_resp = requests.get(
            f"{BACKEND_API_URL}/api/articles/storage/stats",
            headers={"X-API-Key": BACKEND_API_KEY},
            timeout=10
        )
        print(f"   Storage stats response: {stats_resp.status_code}")
        if stats_resp.status_code == 200:
            print(f"   Stats: {stats_resp.json()}")
    except Exception as e:
        print(f"   ⚠️ Could not get storage stats: {e}")
    
    while True:
        try:
            resp = requests.get(
                f"{BACKEND_API_URL}/api/articles/ids",
                params={"offset": offset, "limit": limit},
                headers={"X-API-Key": BACKEND_API_KEY},
                timeout=30
            )
            
            if resp.status_code != 200:
                print(f"   ⚠️ API returned {resp.status_code} at offset {offset}")
                print(f"   Response: {resp.text[:500]}")
                break
            
            data = resp.json()
            
            # API returns 'article_ids' not 'ids'
            ids = data.get("article_ids", []) or data.get("ids", [])
            if not ids:
                print(f"   No IDs in response at offset {offset}. Done.")
                break
            
            all_ids.update(ids)
            
            if not data.get("has_more", False):
                print(f"   Fetched {len(all_ids)} total IDs (no more pages)")
                break
            
            offset += limit
            if offset % 2000 == 0:
                print(f"   Fetched {len(all_ids)} IDs so far...")
            
        except Exception as e:
            print(f"   ❌ Error fetching IDs: {e}")
            import traceback
            traceback.print_exc()
            break
    
    return all_ids


def get_all_neo4j_article_ids():
    """Get ALL article IDs from Neo4j (Article nodes)"""
    print("\n🔷 Fetching ALL article IDs from Neo4j...")
    
    # Get all Article nodes (not just those with ABOUT links)
    query = """
    MATCH (a:Article)
    RETURN a.id AS id
    """
    results = run_cypher(query, {})
    all_ids = set(r["id"] for r in results if r.get("id"))
    print(f"   Found {len(all_ids)} Article nodes in Neo4j")
    return all_ids


def get_neo4j_articles_with_about():
    """Get article IDs that have ABOUT links to Topics"""
    print("\n🔗 Fetching article IDs with ABOUT links...")
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic)
    RETURN DISTINCT a.id AS id
    """
    results = run_cypher(query, {})
    ids = set(r["id"] for r in results if r.get("id"))
    print(f"   Found {len(ids)} articles with ABOUT links")
    return ids


def get_neo4j_article_details(article_ids: list):
    """Get details for specific articles from Neo4j"""
    if not article_ids:
        return []
    query = """
    MATCH (a:Article)
    WHERE a.id IN $ids
    OPTIONAL MATCH (a)-[:ABOUT]->(t:Topic)
    RETURN a.id AS id, 
           a.pubDate AS pubDate, 
           a.title AS title,
           a.addedAt AS addedAt,
           collect(DISTINCT t.name) AS topics
    """
    return run_cypher(query, {"ids": list(article_ids)})


def get_storage_article_sample(article_ids: list, sample_size: int = 50):
    """Get article details from storage for a sample"""
    articles = []
    for i, aid in enumerate(list(article_ids)[:sample_size]):
        try:
            resp = requests.get(
                f"{BACKEND_API_URL}/api/articles/{aid}",
                headers={"X-API-Key": BACKEND_API_KEY},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                # Try to extract date
                pub_date = data.get("pubDate") or data.get("publishedAt") or data.get("data", {}).get("pubDate")
                articles.append({
                    "id": aid,
                    "pubDate": pub_date,
                    "title": (data.get("title") or data.get("data", {}).get("title", ""))[:60]
                })
        except:
            pass
        if (i + 1) % 20 == 0:
            print(f"   Sampled {i + 1}/{min(sample_size, len(article_ids))}...")
    return articles


def analyze_date_distribution(articles: list, label: str):
    """Analyze date distribution of articles"""
    by_month = defaultdict(int)
    no_date = 0
    
    for a in articles:
        pub_date = a.get("pubDate")
        if pub_date:
            try:
                # Handle various date formats
                if isinstance(pub_date, str):
                    # Try to extract YYYY-MM
                    if len(pub_date) >= 7:
                        month = pub_date[:7]
                        by_month[month] += 1
                    else:
                        no_date += 1
                else:
                    no_date += 1
            except:
                no_date += 1
        else:
            no_date += 1
    
    print(f"\n📅 Date Distribution for {label}:")
    if by_month:
        for month in sorted(by_month.keys()):
            print(f"   {month}: {by_month[month]} articles")
    if no_date:
        print(f"   No date: {no_date} articles")
    
    return by_month, no_date


def check_existence_batch(ids: set, source: str, sample_size: int = 200):
    """Check if articles exist in the other system"""
    print(f"\n🔍 Checking {min(sample_size, len(ids))} {source} articles for existence...")
    
    exists = []
    missing = []
    sample = list(ids)[:sample_size]
    
    for i, aid in enumerate(sample):
        if source == "neo4j":
            # Check if exists in storage
            try:
                resp = requests.get(
                    f"{BACKEND_API_URL}/api/articles/{aid}",
                    headers={"X-API-Key": BACKEND_API_KEY},
                    timeout=5
                )
                if resp.status_code == 200:
                    exists.append(aid)
                else:
                    missing.append(aid)
            except:
                missing.append(aid)
        else:
            # Check if exists in Neo4j
            query = "MATCH (a:Article {id: $id}) RETURN a.id AS id LIMIT 1"
            result = run_cypher(query, {"id": aid})
            if result:
                exists.append(aid)
            else:
                missing.append(aid)
        
        if (i + 1) % 50 == 0:
            print(f"   Checked {i + 1}/{len(sample)}...")
    
    return exists, missing


def deep_sample_neo4j_articles(sample_size: int = 500):
    """Get a large random sample of Neo4j articles with full details"""
    print(f"\n🔬 Deep sampling {sample_size} Neo4j articles...")
    
    query = """
    MATCH (a:Article)
    WITH a, rand() AS r
    ORDER BY r
    LIMIT $limit
    OPTIONAL MATCH (a)-[about:ABOUT]->(t:Topic)
    RETURN a.id AS id, 
           a.pubDate AS pubDate, 
           a.title AS title,
           a.addedAt AS addedAt,
           a.source AS source,
           a.url AS url,
           count(about) AS about_count,
           collect(DISTINCT t.name)[0..3] AS topics
    """
    results = run_cypher(query, {"limit": sample_size})
    print(f"   Got {len(results)} articles")
    return results


def check_articles_in_storage_batch(article_ids: list):
    """Check which articles exist in storage (batch check)"""
    found = []
    missing = []
    
    for i, aid in enumerate(article_ids):
        try:
            resp = requests.get(
                f"{BACKEND_API_URL}/api/articles/{aid}",
                headers={"X-API-Key": BACKEND_API_KEY},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                # Check if it has actual content
                title = data.get("title") or data.get("data", {}).get("title", "")
                if title and title != "N/A":
                    found.append({"id": aid, "title": title[:50], "has_content": True})
                else:
                    found.append({"id": aid, "title": "N/A", "has_content": False})
            else:
                missing.append(aid)
        except:
            missing.append(aid)
        
        if (i + 1) % 100 == 0:
            print(f"   Checked {i + 1}/{len(article_ids)}... (found: {len(found)}, missing: {len(missing)})")
    
    return found, missing


def analyze_neo4j_article_properties():
    """Analyze what properties Neo4j articles have"""
    print("\n🔍 Analyzing Neo4j Article node properties...")
    
    # Check what properties exist
    query = """
    MATCH (a:Article)
    WITH a LIMIT 1
    RETURN keys(a) AS properties
    """
    result = run_cypher(query, {})
    if result:
        print(f"   Article properties: {result[0].get('properties', [])}")
    
    # Count articles with/without key properties
    queries = {
        "has pubDate": "MATCH (a:Article) WHERE a.pubDate IS NOT NULL RETURN count(a) AS c",
        "has addedAt": "MATCH (a:Article) WHERE a.addedAt IS NOT NULL RETURN count(a) AS c",
        "has title": "MATCH (a:Article) WHERE a.title IS NOT NULL RETURN count(a) AS c",
        "has url": "MATCH (a:Article) WHERE a.url IS NOT NULL RETURN count(a) AS c",
        "has source": "MATCH (a:Article) WHERE a.source IS NOT NULL RETURN count(a) AS c",
        "has ABOUT link": "MATCH (a:Article)-[:ABOUT]->() RETURN count(DISTINCT a) AS c",
        "no ABOUT link": "MATCH (a:Article) WHERE NOT (a)-[:ABOUT]->() RETURN count(a) AS c",
    }
    
    print("\n   Property coverage:")
    for label, q in queries.items():
        result = run_cypher(q, {})
        count = result[0]["c"] if result else 0
        print(f"   - {label}: {count:,}")
    
    # Check addedAt distribution (when were articles added to Neo4j?)
    print("\n📅 When were articles added to Neo4j (addedAt)?")
    query = """
    MATCH (a:Article)
    WHERE a.addedAt IS NOT NULL
    RETURN substring(a.addedAt, 0, 10) AS date, count(*) AS count
    ORDER BY date DESC
    LIMIT 30
    """
    results = run_cypher(query, {})
    for r in results[:15]:
        print(f"   {r['date']}: {r['count']} articles")
    if len(results) > 15:
        print(f"   ... and {len(results) - 15} more dates")


def analyze_topic_article_distribution():
    """See which topics have the most missing articles"""
    print("\n📊 Articles per topic (top 20)...")
    
    query = """
    MATCH (t:Topic)<-[:ABOUT]-(a:Article)
    RETURN t.name AS topic, t.id AS topic_id, count(a) AS article_count
    ORDER BY article_count DESC
    LIMIT 20
    """
    results = run_cypher(query, {})
    for r in results:
        print(f"   {r['topic']}: {r['article_count']} articles")


def main():
    print("\n" + "="*80)
    print("  COMPREHENSIVE ARTICLE SYNC DIAGNOSTIC")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*80)
    
    # ========== STEP 1: GET COUNTS ==========
    storage_ids = get_all_storage_ids()
    neo4j_all_ids = get_all_neo4j_article_ids()
    neo4j_about_ids = get_neo4j_articles_with_about()
    
    print("\n" + "="*80)
    print("  COUNTS SUMMARY")
    print("="*80)
    print(f"\n📦 Backend API Storage: {len(storage_ids):,} articles")
    print(f"🔷 Neo4j Article nodes: {len(neo4j_all_ids):,} articles")
    print(f"🔗 Neo4j with ABOUT links: {len(neo4j_about_ids):,} articles")
    print(f"🔗 Neo4j WITHOUT ABOUT links: {len(neo4j_all_ids - neo4j_about_ids):,} articles")
    
    # ========== STEP 2: NEO4J PROPERTY ANALYSIS ==========
    print("\n" + "="*80)
    print("  NEO4J ARTICLE PROPERTY ANALYSIS")
    print("="*80)
    analyze_neo4j_article_properties()
    
    # ========== STEP 3: TOPIC DISTRIBUTION ==========
    print("\n" + "="*80)
    print("  TOPIC ARTICLE DISTRIBUTION")
    print("="*80)
    analyze_topic_article_distribution()
    
    # ========== STEP 4: DEEP SAMPLE CHECK ==========
    print("\n" + "="*80)
    print("  DEEP SAMPLE: Check Neo4j articles against Storage")
    print("="*80)
    
    # Get random sample from Neo4j
    neo4j_sample = deep_sample_neo4j_articles(500)
    sample_ids = [a["id"] for a in neo4j_sample]
    
    # Check each against storage
    print(f"\n🔍 Checking {len(sample_ids)} Neo4j articles in Backend API storage...")
    found_in_storage, missing_from_storage = check_articles_in_storage_batch(sample_ids)
    
    found_pct = len(found_in_storage) / len(sample_ids) * 100 if sample_ids else 0
    print(f"\n📊 SAMPLE RESULTS ({len(sample_ids)} articles):")
    print(f"   ✅ Found in storage: {len(found_in_storage)} ({found_pct:.1f}%)")
    print(f"   ❌ Missing from storage: {len(missing_from_storage)} ({100-found_pct:.1f}%)")
    
    # Analyze the found vs missing
    found_ids = set(f["id"] for f in found_in_storage)
    missing_ids = set(missing_from_storage)
    
    # Check if missing articles have ABOUT links
    missing_with_about = [a for a in neo4j_sample if a["id"] in missing_ids and a["about_count"] > 0]
    missing_without_about = [a for a in neo4j_sample if a["id"] in missing_ids and a["about_count"] == 0]
    
    print(f"\n   Missing articles WITH ABOUT links: {len(missing_with_about)}")
    print(f"   Missing articles WITHOUT ABOUT links: {len(missing_without_about)}")
    
    # ========== STEP 5: PATTERN ANALYSIS ==========
    print("\n" + "="*80)
    print("  PATTERN ANALYSIS: What's different about missing articles?")
    print("="*80)
    
    # Check addedAt dates for found vs missing
    found_articles = [a for a in neo4j_sample if a["id"] in found_ids]
    missing_articles = [a for a in neo4j_sample if a["id"] in missing_ids]
    
    def get_date_stats(articles, field):
        dates = [a.get(field) for a in articles if a.get(field)]
        if not dates:
            return None, None, 0
        dates_sorted = sorted(dates)
        return dates_sorted[0], dates_sorted[-1], len(dates)
    
    print("\n📅 addedAt dates (when added to Neo4j):")
    f_min, f_max, f_count = get_date_stats(found_articles, "addedAt")
    m_min, m_max, m_count = get_date_stats(missing_articles, "addedAt")
    print(f"   Found articles: {f_count} have addedAt, range: {f_min} to {f_max}")
    print(f"   Missing articles: {m_count} have addedAt, range: {m_min} to {m_max}")
    
    print("\n📅 pubDate dates (article publication date):")
    f_min, f_max, f_count = get_date_stats(found_articles, "pubDate")
    m_min, m_max, m_count = get_date_stats(missing_articles, "pubDate")
    print(f"   Found articles: {f_count} have pubDate, range: {f_min} to {f_max}")
    print(f"   Missing articles: {m_count} have pubDate, range: {m_min} to {m_max}")
    
    # Sample of missing articles
    print("\n🔷 Sample of MISSING articles (not in storage):")
    for a in missing_articles[:10]:
        print(f"   {a['id']}: addedAt={a.get('addedAt', 'N/A')[:10] if a.get('addedAt') else 'N/A'} | {a.get('title', 'no title')[:40]}...")
    
    print("\n✅ Sample of FOUND articles (in storage):")
    for a in found_articles[:10]:
        print(f"   {a['id']}: addedAt={a.get('addedAt', 'N/A')[:10] if a.get('addedAt') else 'N/A'} | {a.get('title', 'no title')[:40]}...")
    
    # ========== STEP 6: ID FORMAT ANALYSIS ==========
    print("\n" + "="*80)
    print("  ID FORMAT ANALYSIS")
    print("="*80)
    
    found_id_lengths = set(len(x) for x in found_ids)
    missing_id_lengths = set(len(x) for x in missing_ids)
    
    print(f"\n📦 Found article ID lengths: {sorted(found_id_lengths)}")
    print(f"🔷 Missing article ID lengths: {sorted(missing_id_lengths)}")
    
    print(f"\n📦 Found ID samples: {list(found_ids)[:5]}")
    print(f"🔷 Missing ID samples: {list(missing_ids)[:5]}")
    
    # Check for patterns in IDs
    def analyze_id_chars(ids, label):
        if not ids:
            return
        # Check first char distribution
        first_chars = defaultdict(int)
        for id in ids:
            if id:
                first_chars[id[0]] += 1
        print(f"\n   {label} - First character distribution:")
        for char, count in sorted(first_chars.items(), key=lambda x: -x[1])[:10]:
            print(f"      '{char}': {count}")
    
    analyze_id_chars(found_ids, "Found IDs")
    analyze_id_chars(missing_ids, "Missing IDs")
    
    # ========== STEP 7: DIAGNOSIS ==========
    print("\n" + "="*80)
    print("  DIAGNOSIS")
    print("="*80)
    
    print(f"""
📊 SUMMARY:
  - Neo4j has {len(neo4j_all_ids):,} Article nodes
  - Storage API returned {len(storage_ids):,} article IDs
  - Sample check: {found_pct:.1f}% of Neo4j articles found in storage
  
🔍 KEY FINDINGS:
  - Articles WITH ABOUT links missing from storage: {len(missing_with_about)}
    (These cause 'Article not found' errors during analysis)
  - Articles WITHOUT ABOUT links missing from storage: {len(missing_without_about)}
    (These are orphan nodes, less critical)
""")
    
    if len(storage_ids) == 0:
        print("""
⚠️  STORAGE API RETURNED 0 IDs!
  But individual article fetches work (found {len(found_in_storage)} in sample).
  This suggests the /api/articles/ids endpoint is broken or paginating wrong.
  
  The actual storage likely has articles - check the endpoint implementation.
""")
    
    if found_pct < 50:
        print(f"""
🚨 CRITICAL: Only {found_pct:.1f}% of Neo4j articles exist in storage!

POSSIBLE CAUSES:
1. Neo4j was restored from backup that predates current storage
2. Storage was cleared and repopulated separately
3. Article IDs changed format at some point
4. Two different ingestion systems ran independently

LOOK AT THE DATES:
  - If missing articles have OLD addedAt dates → Neo4j has stale data
  - If missing articles have NEW addedAt dates → Storage isn't saving properly
  - If missing articles have NO addedAt → They're from before you tracked this
""")
    
    print("\n" + "="*80)
    print("  DIAGNOSTIC COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
