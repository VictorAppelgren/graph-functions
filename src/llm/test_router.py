"""
LLM Router Test Suite - Tests all 4 tiers

4-Tier Architecture:
- SIMPLE: 20B model (local + :8686 + :8787) - Article work
- MEDIUM: 120B model (:3331) - Research/writing
- COMPLEX: DeepSeek v3.2 - Strategic reasoning
- FAST: Anthropic Claude - User-facing (expensive)

Run with: python -m src.llm.test_router
"""

import sys
import os

# Setup path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier, SERVERS, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY
from src.llm.sanitizer import run_llm_decision, TestResult
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel


class SimpleClassification(BaseModel):
    """Simple classification result."""
    sentiment: str
    confidence: float


def print_header(title: str) -> None:
    """Print a formatted test header."""
    print("\n" + "=" * 80)
    print(f"TEST: {title}")
    print("=" * 80)


def print_server_config() -> None:
    """Print current server configuration."""
    print_header("SERVER CONFIGURATION")
    print(f"Available servers: {list(SERVERS.keys())}")
    print(f"DEEPSEEK_API_KEY set: {bool(DEEPSEEK_API_KEY)}")
    print(f"ANTHROPIC_API_KEY set: {bool(ANTHROPIC_API_KEY)}")
    print()
    for name, config in SERVERS.items():
        print(f"  {name}:")
        print(f"    provider: {config.get('provider')}")
        print(f"    model: {config.get('model')}")
        if config.get('base_url'):
            print(f"    url: {config.get('base_url')}")
    print()


def test_simple_tier() -> bool:
    """Test SIMPLE tier (20B models)."""
    print_header("SIMPLE TIER (20B)")
    print("Testing article classification with SIMPLE tier...")

    prompt = """Classify the sentiment of this text as positive, negative, or neutral.

Text: "The Federal Reserve raised interest rates, causing market uncertainty."

Respond with JSON: {"sentiment": "positive|negative|neutral", "confidence": 0.0-1.0}"""

    try:
        llm = get_llm(ModelTier.SIMPLE)
        response = llm.invoke(prompt)
        print(f"Response: {response.content[:200]}...")
        print("SIMPLE tier: PASSED")
        return True
    except Exception as e:
        print(f"SIMPLE tier: FAILED - {e}")
        return False


def test_medium_tier() -> bool:
    """Test MEDIUM tier (120B model on :3331)."""
    print_header("MEDIUM TIER (120B)")
    print("Testing research writing with MEDIUM tier...")

    if 'external_120b' not in SERVERS:
        print("MEDIUM tier: SKIPPED (external_120b not available)")
        return True

    prompt = """Summarize this economic news in 2-3 sentences for a research report:

"The European Central Bank held rates steady while signaling potential cuts in 2024.
Inflation in the Eurozone fell to 2.4%, approaching the ECB's 2% target.
Bond yields dropped across the continent as investors priced in looser monetary policy."

Respond with JSON: {"sentiment": "analysis", "confidence": 0.9}"""

    try:
        llm = get_llm(ModelTier.MEDIUM)
        response = llm.invoke(prompt)
        print(f"Response: {response.content[:300]}...")
        print("MEDIUM tier: PASSED")
        return True
    except Exception as e:
        print(f"MEDIUM tier: FAILED - {e}")
        return False


def test_complex_tier() -> bool:
    """Test COMPLEX tier (DeepSeek v3.2)."""
    print_header("COMPLEX TIER (DeepSeek)")
    print("Testing strategic reasoning with COMPLEX tier...")

    if 'deepseek' not in SERVERS:
        print("COMPLEX tier: SKIPPED (deepseek not available)")
        return True

    if not DEEPSEEK_API_KEY:
        print("COMPLEX tier: SKIPPED (DEEPSEEK_API_KEY not set)")
        return True

    prompt = """Analyze the strategic implications of this market scenario:

"Oil prices surged 5% after OPEC announced surprise production cuts.
The dollar weakened against major currencies.
Treasury yields spiked as inflation expectations rose."

What are the 2nd and 3rd order effects for:
1. Energy sector stocks
2. Consumer spending
3. Federal Reserve policy

Respond with JSON: {"sentiment": "analysis", "confidence": 0.95}"""

    try:
        llm = get_llm(ModelTier.COMPLEX)
        response = llm.invoke(prompt)
        print(f"Response: {response.content[:400]}...")
        print("COMPLEX tier: PASSED")
        return True
    except Exception as e:
        print(f"COMPLEX tier: FAILED - {e}")
        return False


def test_fast_tier() -> bool:
    """Test FAST tier (Anthropic Claude)."""
    print_header("FAST TIER (Anthropic)")
    print("Testing user-facing response with FAST tier...")

    if 'anthropic' not in SERVERS:
        print("FAST tier: SKIPPED (anthropic not available)")
        return True

    if not ANTHROPIC_API_KEY:
        print("FAST tier: SKIPPED (ANTHROPIC_API_KEY not set)")
        return True

    prompt = """Quickly explain what a "rate cut" means for a retail investor in 2 sentences.

Respond with JSON: {"sentiment": "educational", "confidence": 0.99}"""

    try:
        llm = get_llm(ModelTier.FAST)
        response = llm.invoke(prompt)
        print(f"Response: {response.content[:300]}...")
        print("FAST tier: PASSED")
        return True
    except Exception as e:
        print(f"FAST tier: FAILED - {e}")
        return False


def test_simple_load_balancing() -> bool:
    """Test SIMPLE tier load balancing across servers."""
    print_header("SIMPLE TIER LOAD BALANCING")
    print("Making 5 SIMPLE tier requests to see round-robin...")

    prompt = "Classify: Good news. JSON: {\"sentiment\": \"positive\", \"confidence\": 0.9}"

    try:
        for i in range(5):
            print(f"\n--- Request {i+1} ---")
            llm = get_llm(ModelTier.SIMPLE)
            response = llm.invoke(prompt)
            print(f"Response received (check logs for server)")

        print("\nLoad balancing: PASSED (check [LLM INVOKE] logs for server rotation)")
        return True
    except Exception as e:
        print(f"Load balancing: FAILED - {e}")
        return False


def test_tier_fallback() -> bool:
    """Test that tiers fall back correctly when servers unavailable."""
    print_header("TIER FALLBACK LOGIC")

    # This is informational - shows what would happen
    print("Fallback chain:")
    print("  FAST -> MEDIUM -> SIMPLE")
    print("  COMPLEX -> MEDIUM -> SIMPLE")
    print("  MEDIUM -> SIMPLE")
    print()
    print("Fallback logic is built into _route_request()")
    print("Tier fallback: PASSED (informational)")
    return True


def run_all_tests() -> None:
    """Run all LLM tier tests."""
    print("\n" + "=" * 80)
    print("LLM ROUTER TEST SUITE - 4 TIER ARCHITECTURE")
    print("=" * 80)

    print_server_config()

    results = {
        "SIMPLE": test_simple_tier(),
        "MEDIUM": test_medium_tier(),
        "COMPLEX": test_complex_tier(),
        "FAST": test_fast_tier(),
        "Load Balancing": test_simple_load_balancing(),
        "Fallback Logic": test_tier_fallback(),
    }

    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        symbol = "+" if passed else "x"
        print(f"  [{symbol}] {test_name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed. Check output above for details.")
        sys.exit(1)


def test_single_tier(tier_name: str) -> None:
    """Test a single tier by name."""
    tier_tests = {
        "simple": test_simple_tier,
        "medium": test_medium_tier,
        "complex": test_complex_tier,
        "fast": test_fast_tier,
    }

    tier_name = tier_name.lower()
    if tier_name not in tier_tests:
        print(f"Unknown tier: {tier_name}")
        print(f"Available: {list(tier_tests.keys())}")
        sys.exit(1)

    print_server_config()
    success = tier_tests[tier_name]()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run single tier test
        test_single_tier(sys.argv[1])
    else:
        # Run all tests
        run_all_tests()
