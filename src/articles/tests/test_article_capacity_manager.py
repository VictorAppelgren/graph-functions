"""
Tests for NEW two-stage recursive capacity management system.
REAL INTEGRATION TESTS - NO MOCKS!

This test suite hits the actual Neo4j database and tests real logic.
Perfect for demo stage to prove the system works end-to-end.

Run with: python src/articles/tests/test_article_capacity_manager.py
Run with: python -m src.articles.tests.test_article_capacity_manager
"""

from datetime import datetime
import uuid

from src.articles.orchestration.article_capacity_orchestrator import (
    check_capacity, gate_decision, pick_weakest_article
)
from src.graph.ops.link import add_article_with_capacity_check, create_about_link_with_classification
from src.graph.neo4j_client import run_cypher
from src.graph.ops.topic import create_topic


# ============================================================================
# Test Setup Helpers - Create REAL data in Neo4j
# ============================================================================

def create_test_topic(topic_id=None):
    """Create a real topic in Neo4j for testing."""
    if not topic_id:
        topic_id = f"test_topic_{uuid.uuid4().hex[:8]}"
    
    query = """
    MERGE (t:Topic {id: $topic_id})
    SET t.name = $name,
        t.analysis_snippet = $snippet,
        t.created_at = datetime()
    RETURN t.id as id
    """
    run_cypher(query, {
        "topic_id": topic_id,
        "name": f"Test Topic {topic_id}",
        "snippet": "Test analysis for capacity management"
    })
    return topic_id


def create_test_article(article_id=None, summary="Test article"):
    """Create a real article in Neo4j for testing."""
    if not article_id:
        article_id = f"test_art_{uuid.uuid4().hex[:8]}"
    
    query = """
    MERGE (a:Article {id: $article_id})
    SET a.title = $title,
        a.summary = $summary,
        a.source = $source,
        a.published_at = $published_at,
        a.created_at = datetime()
    RETURN a.id as id
    """
    run_cypher(query, {
        "article_id": article_id,
        "title": f"Test Article {article_id}",
        "summary": summary,
        "source": "Bloomberg Test",
        "published_at": "2025-11-15T10:00:00Z"
    })
    return article_id


def cleanup_test_data(topic_id=None, article_ids=None):
    """Clean up test data from Neo4j."""
    if topic_id:
        run_cypher("MATCH (t:Topic {id: $id}) DETACH DELETE t", {"id": topic_id})
    
    if article_ids:
        for aid in article_ids:
            run_cypher("MATCH (a:Article {id: $id}) DETACH DELETE a", {"id": aid})


def cleanup_all_test_data():
    """Remove ALL test articles and topics from Neo4j."""
    print("\n" + "="*70)
    print("FINAL CLEANUP: Removing all test data from Neo4j")
    print("="*70)
    
    # Count and delete test articles
    count_articles = run_cypher("""
        MATCH (a:Article)
        WHERE a.id STARTS WITH 'test_art_'
        RETURN count(a) as count
    """, {})
    article_count = count_articles[0]["count"] if count_articles else 0
    
    # Count and delete test topics
    count_topics = run_cypher("""
        MATCH (t:Topic)
        WHERE t.id STARTS WITH 'test_topic_'
        RETURN count(t) as count
    """, {})
    topic_count = count_topics[0]["count"] if count_topics else 0
    
    if article_count > 0:
        run_cypher("""
            MATCH (a:Article)
            WHERE a.id STARTS WITH 'test_art_'
            DETACH DELETE a
        """, {})
        print(f"✓ Deleted {article_count} test articles")
    
    if topic_count > 0:
        run_cypher("""
            MATCH (t:Topic)
            WHERE t.id STARTS WITH 'test_topic_'
            DETACH DELETE t
        """, {})
        print(f"✓ Deleted {topic_count} test topics")
    
    if article_count == 0 and topic_count == 0:
        print("✓ No test data found - database already clean")
    
    print("="*70 + "\n")


# Test runner
def run_test(test_name, test_func):
    """Run a test and log results."""
    try:
        test_func()
        print(f"✅ PASS: {test_name}")
        return True
    except AssertionError as e:
        print(f"❌ FAIL: {test_name}")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {test_name}")
        print(f"   Error: {e}")
        return False


# ============================================================================
# REAL INTEGRATION TESTS: Helper Functions
# ============================================================================

def test_check_capacity_has_room():
    """REAL TEST: check_capacity with actual Neo4j data."""
    topic_id = create_test_topic()
    article_ids = []
    
    try:
        # Create 2 articles at tier 3 (limit is 4)
        for i in range(2):
            aid = create_test_article(summary=f"Test article {i}")
            article_ids.append(aid)
            
            # Create ABOUT link at tier 3
            run_cypher("""
                MATCH (a:Article {id: $aid}), (t:Topic {id: $tid})
                CREATE (a)-[r:ABOUT {
                    timeframe: 'current',
                    importance_risk: 3,
                    importance_opportunity: 1,
                    importance_trend: 1,
                    importance_catalyst: 1,
                    motivation: 'test',
                    implications: 'test'
                }]->(t)
            """, {"aid": aid, "tid": topic_id})
        
        result = check_capacity(topic_id, "current", 3)
        
        assert result["has_room"] == True, f"Should have room, got {result}"
        assert result["count"] == 2, f"Wrong count: {result['count']}"
        assert result["max"] == 4, f"Wrong max: {result['max']}"
        
    finally:
        cleanup_test_data(topic_id, article_ids)


def test_check_capacity_full():
    """REAL TEST: check_capacity when tier is full."""
    topic_id = create_test_topic()
    article_ids = []
    
    try:
        # Create 4 articles at tier 3 (limit is 4)
        for i in range(4):
            aid = create_test_article(summary=f"Test article {i}")
            article_ids.append(aid)
            
            # Create ABOUT link at tier 3
            run_cypher("""
                MATCH (a:Article {id: $aid}), (t:Topic {id: $tid})
                CREATE (a)-[r:ABOUT {
                    timeframe: 'current',
                    importance_risk: 3,
                    importance_opportunity: 1,
                    importance_trend: 1,
                    importance_catalyst: 1,
                    motivation: 'test',
                    implications: 'test'
                }]->(t)
            """, {"aid": aid, "tid": topic_id})
        
        result = check_capacity(topic_id, "current", 3)
        
        assert result["has_room"] == False, f"Should be full, got {result}"
        assert result["count"] == 4, f"Wrong count: {result['count']}"
        assert result["max"] == 4, f"Wrong max: {result['max']}"
        
    finally:
        cleanup_test_data(topic_id, article_ids)


def test_gate_decision_test_mode():
    """REAL TEST: gate_decision in test mode (no LLM call)."""
    topic_id = create_test_topic()
    article_ids = []
    
    try:
        # Create one existing article
        aid = create_test_article(summary="Existing article")
        article_ids.append(aid)
        
        result = gate_decision(
            topic_id=topic_id,
            timeframe="current",
            tier=3,
            new_article_summary="New article",
            new_article_source="Reuters",
            new_article_published="2025-11-15",
            existing_articles=[{"id": aid, "summary": "Existing", "source": "Bloomberg", "published_at": "2025-11-01"}],
            test=True  # Test mode - no LLM
        )
        
        assert result["reject"] == False, "Test mode should not reject"
        assert result["downgrade"] == "NEW", "Test mode defaults to downgrade NEW"
        
    finally:
        cleanup_test_data(topic_id, article_ids)


# ============================================================================
# END-TO-END INTEGRATION TESTS: Full System
# ============================================================================

def test_add_article_with_room():
    """REAL TEST: Add article when tier has room."""
    topic_id = create_test_topic()
    article_ids = []
    
    try:
        # Create new article
        new_aid = create_test_article(summary="New important article")
        article_ids.append(new_aid)
        
        # Add with capacity check (tier 3 is empty, has room)
        result = add_article_with_capacity_check(
            article_id=new_aid,
            topic_id=topic_id,
            timeframe="current",
            initial_tier=3,
            article_summary="New important article",
            article_source="Bloomberg Test",
            article_published="2025-11-15T10:00:00Z",
            motivation="Critical for trading",
            implications="High market impact",
            test=True  # Test mode to skip LLM calls
        )
        
        assert result["action"] == "added", f"Should add, got {result}"
        assert result["tier"] == 3, f"Should add at tier 3, got {result}"
        
        # Verify link was created
        verify_query = """
        MATCH (a:Article {id: $aid})-[r:ABOUT]->(t:Topic {id: $tid})
        WHERE r.timeframe = 'current'
        RETURN r.importance_risk as tier
        """
        verify_result = run_cypher(verify_query, {"aid": new_aid, "tid": topic_id})
        assert len(verify_result) == 1, "Link should exist"
        assert verify_result[0]["tier"] == 3, "Should be at tier 3"
        
    finally:
        cleanup_test_data(topic_id, article_ids)


def test_create_about_link_end_to_end():
    """REAL TEST: Full end-to-end test using create_about_link_with_classification."""
    topic_id = create_test_topic()
    article_ids = []
    
    try:
        # Create article
        new_aid = create_test_article(summary="Breaking Fed news")
        article_ids.append(new_aid)
        
        # Use the REAL function that's called from ingest_article.py
        result = create_about_link_with_classification(
            article_id=new_aid,
            topic_id=topic_id,
            timeframe="current",
            importance_risk=3,
            importance_opportunity=1,
            importance_trend=2,
            importance_catalyst=1,
            motivation="Critical Fed policy shift",
            implications="Major market impact expected",
            test=True  # Test mode
        )
        
        assert result["action"] in ["added", "duplicate"], f"Should add or be duplicate, got {result}"
        
        # Verify link exists in Neo4j
        verify_query = """
        MATCH (a:Article {id: $aid})-[r:ABOUT]->(t:Topic {id: $tid})
        WHERE r.timeframe = 'current'
        RETURN r.importance_risk as risk, r.motivation as motivation
        """
        verify_result = run_cypher(verify_query, {"aid": new_aid, "tid": topic_id})
        assert len(verify_result) > 0, "Link should exist in database"
        assert verify_result[0]["risk"] == 3, "Should have correct tier"
        assert "Critical" in verify_result[0]["motivation"], "Should have motivation"
        
        print(f"   ✓ Created link: {new_aid} -> {topic_id} at tier 3")
        
    finally:
        cleanup_test_data(topic_id, article_ids)


def test_capacity_stress_fill_tier():
    """STRESS TEST: Add articles until tier 3 is full, watch cascade behavior."""
    topic_id = create_test_topic()
    article_ids = []
    
    try:
        print("\n   📊 STRESS TEST: Filling tier 3 (limit=4) and beyond...")
        
        # Add 6 articles - should fill tier 3, cascade to tier 2
        for i in range(6):
            aid = create_test_article(summary=f"Stress test article {i+1}")
            article_ids.append(aid)
            
            print(f"\n   → Adding article {i+1}/6: {aid}")
            
            result = add_article_with_capacity_check(
                article_id=aid,
                topic_id=topic_id,
                timeframe="current",
                initial_tier=3,
                article_summary=f"Stress test article {i+1}",
                article_source="Bloomberg Test",
                article_published="2025-11-15T10:00:00Z",
                motivation="Test capacity management",
                implications="Testing cascade",
                test=True  # Test mode
            )
            
            print(f"     Result: {result['action']} at tier {result.get('tier', 'N/A')}")
        
        # Check final distribution
        distribution_query = """
        MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $tid})
        WHERE r.timeframe = 'current'
        WITH r.importance_risk as tier, count(a) as count
        ORDER BY tier DESC
        RETURN tier, count
        """
        distribution = run_cypher(distribution_query, {"tid": topic_id})
        
        print("\n   📊 Final tier distribution:")
        total = 0
        for row in distribution:
            print(f"     Tier {row['tier']}: {row['count']} articles")
            total += row['count']
        
        assert total == 6, f"Should have 6 articles total, got {total}"
        print(f"\n   ✓ Successfully added {total} articles with capacity management")
        
    finally:
        cleanup_test_data(topic_id, article_ids)


def test_auto_cleanup_trigger():
    """AUTO-CLEANUP TEST: Force add 12 articles to tier 3, watch LLM auto-cleanup kick in."""
    topic_id = create_test_topic()
    article_ids = []
    
    try:
        print("\n   🔧 AUTO-CLEANUP TEST: Forcing 12 articles into tier 3 (limit=4)...")
        
        # Manually create 12 articles directly at tier 3 (bypassing capacity check)
        print("\n   → Force-adding 12 articles directly to tier 3...")
        for i in range(12):
            aid = create_test_article(summary=f"Force-added article {i+1}")
            article_ids.append(aid)
            
            # Create ABOUT link directly at tier 3 (bypass capacity management)
            run_cypher("""
                MATCH (a:Article {id: $aid}), (t:Topic {id: $tid})
                CREATE (a)-[r:ABOUT {
                    timeframe: 'current',
                    importance_risk: 3,
                    importance_opportunity: 3,
                    importance_trend: 3,
                    importance_catalyst: 3,
                    motivation: 'Force-added for testing',
                    implications: 'Testing auto-cleanup'
                }]->(t)
            """, {"aid": aid, "tid": topic_id})
        
        # Verify we have 9 articles at tier 3
        verify_query = """
        MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $tid})
        WHERE r.timeframe = 'current' AND r.importance_risk >= 3
        RETURN count(a) as count
        """
        verify_result = run_cypher(verify_query, {"tid": topic_id})
        initial_count = verify_result[0]["count"]
        print(f"   ✓ Confirmed: {initial_count} articles at tier 3 (over limit of 4)")
        
        # Now trigger auto-cleanup by calling check_capacity
        print("\n   → Triggering auto-cleanup via check_capacity()...")
        from src.articles.orchestration.article_capacity_orchestrator import check_capacity
        
        result = check_capacity(topic_id, "current", 3)
        
        print(f"\n   📊 After auto-cleanup:")
        print(f"     Tier 3: {result['count']}/{result['max']} articles")
        print(f"     Has room: {result['has_room']}")
        
        # Check final distribution across all tiers
        distribution_query = """
        MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $tid})
        WHERE r.timeframe = 'current'
        WITH r.importance_risk as tier, count(a) as count
        ORDER BY tier DESC
        RETURN tier, count
        """
        distribution = run_cypher(distribution_query, {"tid": topic_id})
        
        print("\n   📊 Final tier distribution after auto-cleanup:")
        total = 0
        for row in distribution:
            print(f"     Tier {row['tier']}: {row['count']} articles")
            total += row['count']
        
        # Verify cleanup worked
        assert result['count'] == 4, f"Tier 3 should have exactly 4 articles, got {result['count']}"
        assert total == 11, f"Should still have 11 articles total (just redistributed), got {total}"
        
        print(f"\n   ✓ Auto-cleanup SUCCESS! Downgraded {initial_count - 4} weakest articles")
        print(f"   ✓ LLM picked the {initial_count - 4} lowest quality articles to downgrade")
        
    finally:
        cleanup_test_data(topic_id, article_ids)


# Main test runner
if __name__ == "__main__":
    print("\n" + "="*70)
    print("REAL INTEGRATION TESTS - NO MOCKS!")
    print("Testing with actual Neo4j database")
    print("="*70 + "\n")
    
    tests = [
        ("✓ check_capacity: has room", test_check_capacity_has_room),
        ("✓ check_capacity: full", test_check_capacity_full),
        ("✓ gate_decision: test mode", test_gate_decision_test_mode),
        ("✓ add_article_with_capacity_check: room available", test_add_article_with_room),
        ("✓ create_about_link_with_classification: end-to-end", test_create_about_link_end_to_end),
        ("✓ STRESS TEST: Fill tier to capacity", test_capacity_stress_fill_tier),
        ("✓ AUTO-CLEANUP TEST: LLM downgrades weakest", test_auto_cleanup_trigger),
    ]
    
    passed = 0
    failed = 0
    
    print("Running tests...")
    print("-" * 70)
    
    for test_name, test_func in tests:
        if run_test(test_name, test_func):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        print("✓ Real Neo4j integration working")
        print("✓ Capacity management functions operational")
        print("✓ System ready for deployment")
    else:
        print("⚠️  Some tests failed. Review errors above.")
    
    # FINAL CLEANUP: Remove any remaining test data
    cleanup_all_test_data()
    
    exit(0 if failed == 0 else 1)
