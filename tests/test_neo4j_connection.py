"""Test Neo4j connection and list all databases"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env
env_file = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip('"').strip("'")
                os.environ[key] = value

from neo4j import GraphDatabase

# ============================================
# CHANGE THIS IP TO TEST DIFFERENT SERVERS
# ============================================
SERVER_IP = "167.172.185.204"  # Change to test different server, or use "localhost" for local
# ============================================

uri = f'bolt://{SERVER_IP}:7687'
user = os.environ.get('NEO4J_USER', 'neo4j')
password = os.environ.get('NEO4J_PASSWORD', 'password')
database = os.environ.get('NEO4J_DATABASE', 'neo4j')

print(f"\n{'='*60}")
print("NEO4J CONNECTION TEST")
print(f"{'='*60}")
print(f"URI: {uri}")
print(f"User: {user}")
print(f"Database: {database}")
print()

# ============================================
# TEST 1: Bad credentials (should fail)
# ============================================
print("TEST 1: Bad credentials (should fail)")
print("-" * 60)
try:
    bad_driver = GraphDatabase.driver(uri, auth=(user, "wrong_password"))
    with bad_driver.session(database=database) as session:
        session.run("RETURN 1")
    print("  ❌ UNEXPECTED: Bad credentials accepted!")
    bad_driver.close()
except Exception as e:
    print(f"  ✅ EXPECTED: Bad credentials rejected")
    print(f"     Error: {str(e)[:80]}")
print()

# ============================================
# TEST 2: Good credentials (should work)
# ============================================
print("TEST 2: Good credentials (should work)")
print("-" * 60)
try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # List databases
    with driver.session(database="system") as session:
        result = session.run("SHOW DATABASES")
        print("  Available databases:")
        for record in result:
            db_name = record["name"]
            status = record.get("currentStatus", "unknown")
            default = " (DEFAULT)" if record.get("default", False) else ""
            print(f"    - {db_name}: {status}{default}")
    
    # Count nodes
    with driver.session(database=database) as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"\n  ✅ Connected! Found {count:,} nodes")
        
        if count > 0:
            result = session.run("MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC LIMIT 5")
            print(f"\n  Top node types:")
            for record in result:
                print(f"    - {record['type']}: {record['count']:,}")
    
    driver.close()
    print()
    
    # ============================================
    # TEST 3: Use actual get_all_topics() function
    # ============================================
    print("TEST 3: Use get_all_topics() function")
    print("-" * 60)
    from src.graph.ops.topic import get_all_topics
    
    topics = get_all_topics(fields=["id", "name", "importance", "last_updated"])
    print(f"  ✅ Fetched {len(topics)} topics using get_all_topics()")
    
    if topics:
        print(f"\n  Sample topics (first 5):")
        for topic in topics[:5]:
            name = topic.get('name', 'N/A')
            importance = topic.get('importance', 'N/A')
            print(f"    - {name} (importance: {importance})")
    
    print()
    print(f"{'='*60}")
    print("✅ ALL TESTS PASSED!")
    print(f"{'='*60}")
    
except Exception as e:
    print(f"  ❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()
