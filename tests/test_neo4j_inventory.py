"""
Neo4j Database Inventory Test
Explores what's actually in the database to understand the data structure.
"""

import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env file manually
env_file = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key] = value

from src.graph.neo4j_client import run_cypher, NEO4J_DATABASE


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")


def count_all_node_types():
    """Count all nodes by label/type"""
    print_section("NODE COUNTS BY TYPE")
    
    query = """
    MATCH (n)
    RETURN labels(n)[0] as NodeType, count(n) as Count
    ORDER BY Count DESC
    """
    
    results = run_cypher(query, {})
    
    if results:
        total = sum(r['Count'] for r in results)
        print(f"Total Nodes: {total}\n")
        for r in results:
            print(f"  {r['NodeType']:20s}: {r['Count']:,}")
    else:
        print("No nodes found!")


def count_all_relationships():
    """Count all relationships by type"""
    print_section("RELATIONSHIP COUNTS BY TYPE")
    
    query = """
    MATCH ()-[r]->()
    RETURN type(r) as RelType, count(r) as Count
    ORDER BY Count DESC
    """
    
    results = run_cypher(query, {})
    
    if results:
        total = sum(r['Count'] for r in results)
        print(f"Total Relationships: {total}\n")
        for r in results:
            print(f"  {r['RelType']:30s}: {r['Count']:,}")
    else:
        print("No relationships found!")


def list_all_topics():
    """List all topics with their properties"""
    print_section("ALL TOPICS (52)")
    
    query = """
    MATCH (t:Topic)
    RETURN t.id as id, 
           t.name as name, 
           t.type as type,
           t.importance as importance,
           t.last_queried as last_queried,
           t.last_analyzed as last_analyzed
    ORDER BY t.importance DESC, t.name ASC
    """
    
    results = run_cypher(query, {})
    
    if results:
        print(f"Found {len(results)} topics:\n")
        for i, t in enumerate(results, 1):
            importance = t.get('importance', 'N/A')
            last_queried = str(t.get('last_queried', 'Never'))[:19] if t.get('last_queried') else 'Never'
            last_analyzed = str(t.get('last_analyzed', 'Never'))[:19] if t.get('last_analyzed') else 'Never'
            
            print(f"{i:2d}. [{importance}] {t['name']}")
            print(f"    ID: {t['id']}")
            print(f"    Type: {t.get('type', 'N/A')}")
            print(f"    Last Queried: {last_queried}")
            print(f"    Last Analyzed: {last_analyzed}")
            print()
    else:
        print("No topics found!")


def sample_articles():
    """Show sample articles with properties"""
    print_section("SAMPLE ARTICLES (First 10)")
    
    query = """
    MATCH (a:Article)
    RETURN a.id as id,
           a.title as title,
           a.published_at as published_at,
           a.source as source,
           a.importance_risk as risk,
           a.importance_opportunity as opportunity,
           a.importance_trend as trend,
           a.importance_catalyst as catalyst
    ORDER BY a.published_at DESC
    LIMIT 10
    """
    
    results = run_cypher(query, {})
    
    if results:
        print(f"Showing 10 of {len(results)} articles:\n")
        for i, a in enumerate(results, 1):
            pub_date = str(a.get('published_at', 'N/A'))[:19] if a.get('published_at') else 'N/A'
            scores = f"R{a.get('risk', '?')}/O{a.get('opportunity', '?')}/T{a.get('trend', '?')}/C{a.get('catalyst', '?')}"
            
            print(f"{i}. {a.get('title', 'No title')[:60]}")
            print(f"   ID: {a['id']}")
            print(f"   Source: {a.get('source', 'N/A')}")
            print(f"   Published: {pub_date}")
            print(f"   Scores: {scores}")
            print()
    else:
        print("No articles found!")


def analyze_topic_article_connections():
    """Analyze how topics connect to articles"""
    print_section("TOPIC-ARTICLE CONNECTIONS")
    
    # Count articles per topic
    query = """
    MATCH (t:Topic)
    OPTIONAL MATCH (t)-[r:HAS_ARTICLE]->(a:Article)
    RETURN t.name as topic, 
           t.id as topic_id,
           count(a) as article_count
    ORDER BY article_count DESC
    LIMIT 20
    """
    
    results = run_cypher(query, {})
    
    if results:
        print("Top 20 topics by article count:\n")
        for i, r in enumerate(results, 1):
            print(f"{i:2d}. {r['topic']:40s} - {r['article_count']:,} articles")
    else:
        print("No topic-article connections found!")


def check_database_properties():
    """Check what properties exist on nodes"""
    print_section("ARTICLE NODE PROPERTIES")
    
    query = """
    MATCH (a:Article)
    WITH a LIMIT 1
    RETURN keys(a) as properties
    """
    
    results = run_cypher(query, {})
    
    if results and results[0]:
        props = results[0]['properties']
        print(f"Article nodes have {len(props)} properties:\n")
        for prop in sorted(props):
            print(f"  - {prop}")
    else:
        print("No articles found to check properties!")
    
    print_section("TOPIC NODE PROPERTIES")
    
    query = """
    MATCH (t:Topic)
    WITH t LIMIT 1
    RETURN keys(t) as properties
    """
    
    results = run_cypher(query, {})
    
    if results and results[0]:
        props = results[0]['properties']
        print(f"Topic nodes have {len(props)} properties:\n")
        for prop in sorted(props):
            print(f"  - {prop}")
    else:
        print("No topics found to check properties!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("NEO4J DATABASE INVENTORY")
    print("="*80)
    print(f"Database: {NEO4J_DATABASE}")
    print(f"URI: {os.environ.get('NEO4J_URI', 'neo4j://127.0.0.1:7687')}")
    print("="*80)
    
    try:
        # Run all diagnostic queries
        count_all_node_types()
        count_all_relationships()
        check_database_properties()
        sample_articles()
        analyze_topic_article_connections()
        list_all_topics()
        
        print("\n" + "="*80)
        print("✅ INVENTORY COMPLETE")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error during inventory: {e}\n")
        import traceback
        traceback.print_exc()
