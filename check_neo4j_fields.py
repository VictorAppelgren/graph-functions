"""
Quick script to check what analysis fields exist in Neo4j for a topic
"""
from src.graph.neo4j_client import run_cypher
from utils.env_loader import load_env

load_env()

topic_id = "eurusd"

query = """
MATCH (t:Topic {id: $topic_id})
RETURN keys(t) as all_fields
"""

result = run_cypher(query, {"topic_id": topic_id})

if result:
    fields = result[0]["all_fields"]
    
    # Filter for analysis fields
    analysis_fields = [f for f in fields if "analysis" in f or "chain" in f or "threat" in f or "risk" in f or "catalyst" in f or "scenario" in f or "quantification" in f or "summary" in f]
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS FIELDS IN NEO4J FOR: {topic_id}")
    print(f"{'='*80}\n")
    
    print(f"Total fields: {len(fields)}")
    print(f"Analysis-related fields: {len(analysis_fields)}\n")
    
    for field in sorted(analysis_fields):
        # Check if field has content
        check_query = f"""
        MATCH (t:Topic {{id: $topic_id}})
        RETURN t.{field} as content
        """
        content_result = run_cypher(check_query, {"topic_id": topic_id})
        content = content_result[0]["content"] if content_result else None
        
        has_content = "✅" if content and len(str(content).strip()) > 0 else "❌"
        length = len(str(content)) if content else 0
        
        print(f"{has_content} {field:40s} ({length:,} chars)")
    
    print(f"\n{'='*80}\n")
else:
    print(f"❌ Topic '{topic_id}' not found in Neo4j")
