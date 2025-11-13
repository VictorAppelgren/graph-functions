"""
Tests for article capacity management system.
Run with: python src/articles/tests/test_article_capacity_manager.py
Run with: python -m src.articles.tests.test_article_capacity_manager
"""

from unittest.mock import patch
from datetime import datetime

from src.articles.policies.article_capacity_manager import article_capacity_manager_llm
from src.articles.orchestration.article_capacity_orchestrator import make_room_for_article
from src.llm.sanitizer import ArticleCapacityDecision, ArticleCapacityAction


# Test data
def get_sample_classification():
    return {
        "timeframe": "current",
        "overall_importance": 3,
        "dominant_perspective": "risk",
        "importance_risk": 3,
        "importance_opportunity": 1,
        "importance_trend": 2,
        "importance_catalyst": 1
    }

def get_sample_existing_article():
    return {
        "id": "old123",
        "summary": "Old Fed article about rate hikes",
        "source": "Bloomberg",
        "published_at": "2025-11-01",
        "risk": 3,
        "opp": 1,
        "trend": 2,
        "cat": 1,
        "timeframe": "current",
        "motivation": "Fed signaling hawkish stance",
        "created_at": datetime(2025, 11, 1)
    }


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


# LLM Policy Tests
def test_test_mode_returns_reject():
    """Test mode returns reject without calling LLM."""
    decision = article_capacity_manager_llm(
        topic_name="Fed Policy",
        new_article_id="new123",
        new_article_summary="New article",
        new_article_source="Reuters",
        new_article_published="2025-11-11",
        new_article_classification=get_sample_classification(),
        existing_articles=[],
        capacity_status={"timeframe": "current", "importance_tier": 3, "current_count": 4, "max_allowed": 4},
        test=True
    )
    
    assert decision.action == ArticleCapacityAction.reject, f"Expected reject, got {decision.action}"
    assert decision.target_article_id is None, "Expected no target article"


def test_prompt_includes_article_details():
    """Prompt includes source, date, and scores."""
    with patch('src.articles.policies.article_capacity_manager.get_llm'), \
         patch('src.articles.policies.article_capacity_manager.run_llm_decision') as mock_run_llm:
        
        mock_run_llm.return_value = ArticleCapacityDecision(
            motivation="Test", action=ArticleCapacityAction.remove, 
            target_article_id="old123", new_importance=None
        )
        
        article_capacity_manager_llm(
            topic_name="Fed Policy", new_article_id="new123", new_article_summary="New article",
            new_article_source="Reuters", new_article_published="2025-11-11",
            new_article_classification=get_sample_classification(),
            existing_articles=[get_sample_existing_article()],
            capacity_status={"timeframe": "current", "importance_tier": 3, "current_count": 4, "max_allowed": 4},
            test=False
        )
        
        prompt = mock_run_llm.call_args[1]['prompt']
        required = ["old123", "Bloomberg", "2025-11-01", "Risk=3"]
        for item in required:
            assert item in prompt, f"Expected '{item}' in prompt"


def test_rejects_invalid_article_id():
    """Invalid target IDs are caught and rejected."""
    with patch('src.articles.policies.article_capacity_manager.get_llm'), \
         patch('src.articles.policies.article_capacity_manager.run_llm_decision') as mock_run_llm:
        
        mock_run_llm.return_value = ArticleCapacityDecision(
            motivation="Test", action=ArticleCapacityAction.remove,
            target_article_id="invalid999", new_importance=None
        )
        
        decision = article_capacity_manager_llm(
            topic_name="Fed Policy", new_article_id="new123", new_article_summary="New article",
            new_article_source="Reuters", new_article_published="2025-11-11",
            new_article_classification=get_sample_classification(),
            existing_articles=[get_sample_existing_article()],
            capacity_status={"timeframe": "current", "importance_tier": 3, "current_count": 4, "max_allowed": 4},
            test=False
        )
        
        assert decision.action == ArticleCapacityAction.reject, "Should reject invalid article ID"


# Orchestrator Tests
def test_accepts_when_no_existing():
    """Accepts when no existing articles."""
    with patch('src.articles.orchestration.article_capacity_orchestrator.run_cypher') as mock_cypher, \
         patch('src.articles.orchestration.article_capacity_orchestrator.article_capacity_manager_llm') as mock_llm:
        
        mock_cypher.return_value = []
        
        result = make_room_for_article(
            topic_id="fed_policy", new_article_id="new123", new_article_summary="New article",
            new_article_source="Reuters", new_article_published="2025-11-11",
            new_article_classification=get_sample_classification(), test=False
        )
        
        assert result["action"] == "accept", f"Expected accept, got {result['action']}"
        assert not mock_llm.called, "LLM should not be called"


def test_removes_article():
    """Removes article when LLM decides."""
    with patch('src.articles.orchestration.article_capacity_orchestrator.run_cypher') as mock_cypher, \
         patch('src.articles.orchestration.article_capacity_orchestrator.get_topic_by_id') as mock_get_topic, \
         patch('src.articles.orchestration.article_capacity_orchestrator.article_capacity_manager_llm') as mock_llm, \
         patch('src.articles.orchestration.article_capacity_orchestrator.master_statistics') as mock_stats:
        
        mock_cypher.return_value = [get_sample_existing_article()]
        mock_get_topic.return_value = {"name": "Fed Policy"}
        mock_llm.return_value = ArticleCapacityDecision(
            motivation="Fresher", action=ArticleCapacityAction.remove,
            target_article_id="old123", new_importance=None
        )
        
        result = make_room_for_article(
            topic_id="fed_policy", new_article_id="new123", new_article_summary="New article",
            new_article_source="Reuters", new_article_published="2025-11-11",
            new_article_classification=get_sample_classification(), test=False
        )
        
        assert result["action"] == "remove", f"Expected remove, got {result['action']}"
        assert any('DELETE r' in str(call) for call in mock_cypher.call_args_list), "DELETE query not executed"
        assert mock_stats.call_args[1]['about_links_removed'] == 1, "Stats not tracked"


def test_downgrades_article():
    """Downgrades article when LLM decides."""
    with patch('src.articles.orchestration.article_capacity_orchestrator.run_cypher') as mock_cypher, \
         patch('src.articles.orchestration.article_capacity_orchestrator.get_topic_by_id') as mock_get_topic, \
         patch('src.articles.orchestration.article_capacity_orchestrator.article_capacity_manager_llm') as mock_llm, \
         patch('src.articles.orchestration.article_capacity_orchestrator.master_statistics') as mock_stats:
        
        mock_cypher.return_value = [get_sample_existing_article()]
        mock_get_topic.return_value = {"name": "Fed Policy"}
        mock_llm.return_value = ArticleCapacityDecision(
            motivation="Overrated", action=ArticleCapacityAction.downgrade,
            target_article_id="old123", new_importance=2
        )
        
        result = make_room_for_article(
            topic_id="fed_policy", new_article_id="new123", new_article_summary="New article",
            new_article_source="Reuters", new_article_published="2025-11-11",
            new_article_classification=get_sample_classification(), test=False
        )
        
        assert result["action"] == "downgrade", f"Expected downgrade, got {result['action']}"
        assert result["new_importance"] == 2, "Wrong importance"
        assert any('SET' in str(call) for call in mock_cypher.call_args_list), "SET query not executed"


def test_skips_db_in_test_mode():
    """Skips DB operations in test mode."""
    with patch('src.articles.orchestration.article_capacity_orchestrator.run_cypher') as mock_cypher, \
         patch('src.articles.orchestration.article_capacity_orchestrator.get_topic_by_id') as mock_get_topic, \
         patch('src.articles.orchestration.article_capacity_orchestrator.article_capacity_manager_llm') as mock_llm:
        
        mock_cypher.return_value = [get_sample_existing_article()]
        mock_get_topic.return_value = {"name": "Fed Policy"}
        mock_llm.return_value = ArticleCapacityDecision(
            motivation="Test", action=ArticleCapacityAction.remove,
            target_article_id="old123", new_importance=None
        )
        
        make_room_for_article(
            topic_id="fed_policy", new_article_id="new123", new_article_summary="New article",
            new_article_source="Reuters", new_article_published="2025-11-11",
            new_article_classification=get_sample_classification(), test=True
        )
        
        assert not any('DELETE r' in str(call) for call in mock_cypher.call_args_list), "DELETE should be skipped in test mode"


# Main test runner
if __name__ == "__main__":
    print("\n" + "="*60)
    print("ARTICLE CAPACITY MANAGER TESTS")
    print("="*60 + "\n")
    
    tests = [
        ("Test mode returns reject", test_test_mode_returns_reject),
        ("Prompt includes article details", test_prompt_includes_article_details),
        ("Rejects invalid article ID", test_rejects_invalid_article_id),
        ("Accepts when no existing articles", test_accepts_when_no_existing),
        ("Removes article", test_removes_article),
        ("Downgrades article", test_downgrades_article),
        ("Skips DB in test mode", test_skips_db_in_test_mode),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        if run_test(test_name, test_func):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    exit(0 if failed == 0 else 1)
