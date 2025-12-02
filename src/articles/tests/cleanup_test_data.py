"""
Cleanup script to remove ALL test data from Neo4j.
Removes all test_art_* articles and test_topic_* topics.

Run with: python src/articles/tests/cleanup_test_data.py
Run with: python -m src.articles.tests.cleanup_test_data
"""

from src.graph.neo4j_client import run_cypher


def cleanup_all_test_data():
    """Remove all test articles and topics from Neo4j."""
    
    print("\n" + "="*70)
    print("CLEANING UP TEST DATA FROM NEO4J")
    print("="*70 + "\n")
    
    # Count test articles
    count_articles = run_cypher("""
        MATCH (a:Article)
        WHERE a.id STARTS WITH 'test_art_'
        RETURN count(a) as count
    """, {})
    article_count = count_articles[0]["count"] if count_articles else 0
    
    # Count test topics
    count_topics = run_cypher("""
        MATCH (t:Topic)
        WHERE t.id STARTS WITH 'test_topic_'
        RETURN count(t) as count
    """, {})
    topic_count = count_topics[0]["count"] if count_topics else 0
    
    print(f"Found {article_count} test articles")
    print(f"Found {topic_count} test topics")
    
    if article_count == 0 and topic_count == 0:
        print("\n✅ No test data found. Database is clean!")
        return
    
    print("\nDeleting test data...")
    
    # Delete test articles (DETACH DELETE removes relationships too)
    if article_count > 0:
        run_cypher("""
            MATCH (a:Article)
            WHERE a.id STARTS WITH 'test_art_'
            DETACH DELETE a
        """, {})
        print(f"✓ Deleted {article_count} test articles")
    
    # Delete test topics
    if topic_count > 0:
        run_cypher("""
            MATCH (t:Topic)
            WHERE t.id STARTS WITH 'test_topic_'
            DETACH DELETE t
        """, {})
        print(f"✓ Deleted {topic_count} test topics")
    
    print("\n" + "="*70)
    print("✅ CLEANUP COMPLETE!")
    print("="*70 + "\n")


if __name__ == "__main__":
    cleanup_all_test_data()
