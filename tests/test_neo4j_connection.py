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

uri = os.environ.get('NEO4J_URI', 'neo4j://127.0.0.1:7687')
user = os.environ.get('NEO4J_USER', 'neo4j')
password = os.environ.get('NEO4J_PASSWORD', 'password')
database = os.environ.get('NEO4J_DATABASE', 'neo4j')

print(f"\nTesting connection to Neo4j:")
print(f"  URI: {uri}")
print(f"  User: {user}")
print(f"  Target Database: {database}")
print()

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # List all databases
    print("Available databases:")
    with driver.session(database="system") as session:
        result = session.run("SHOW DATABASES")
        for record in result:
            db_name = record["name"]
            status = record.get("currentStatus", "unknown")
            default = " (DEFAULT)" if record.get("default", False) else ""
            print(f"  - {db_name}: {status}{default}")
    
    print(f"\nTrying to connect to '{database}':")
    with driver.session(database=database) as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"  ✅ Connected! Found {count:,} nodes")
        
        if count > 0:
            result = session.run("MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC LIMIT 5")
            print(f"\n  Top node types:")
            for record in result:
                print(f"    - {record['type']}: {record['count']:,}")
    
    driver.close()
    
except Exception as e:
    print(f"  ❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()
