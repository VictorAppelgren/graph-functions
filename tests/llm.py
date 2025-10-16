"""
Minimalistic test for all three LLM tiers: simple, medium, complex.
Tests basic LangChain functionality with string output.
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier, SERVERS
from src.llm.sanitizer import run_llm_decision, TestResult
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.prompts.test_simple_long_context_llm import test_simple_long_context_llm_prompt
from src.llm.prompts.test_complex_llm import test_complex_llm_prompt
from src.llm.prompts.test_medium_llm import test_medium_llm_prompt
from src.llm.prompts.test_simple_llm import test_simple_llm_prompt


def test_router_short_vs_long() -> None:
    """Verify router sends short requests to local and very long to external."""
    print("\n" + "=" * 80)
    print("TEST: ROUTER SHORT VS LONG")
    print("=" * 80)
    
    # Test SIMPLE tier with short text (should go local with TOKEN_THRESHOLD=100)
    print("Testing SIMPLE tier with short text...")
    simple_llm = get_llm(ModelTier.SIMPLE)
    short_text = "Hello world!"  # ~3 tokens, well under threshold
    try:
        response = simple_llm.invoke(short_text)
        print("✅ SIMPLE tier short text invoked successfully (check logs for routing)")
    except Exception as e:
        print(f"❌ SIMPLE tier short text failed: {e}")

    # Test COMPLEX tier (should always go external regardless of text size)
    print("Testing COMPLEX tier...")
    complex_llm = get_llm(ModelTier.COMPLEX)
    test_text = "Analyze this market data."  # Any text
    try:
        response = complex_llm.invoke(test_text)
        print("✅ COMPLEX tier invoked successfully (check logs for external routing)")
    except Exception as e:
        print(f"❌ COMPLEX tier failed: {e}")
    
    print("✅ Router routing tested (check [LLM INVOKE] logs for actual server selection)")


def _coerce_to_runnable(llm):
    """Return an actual LangChain Runnable (no unwrapping needed with new router)."""
    return llm


def test_round_robin_external() -> None:
    """Issue multiple COMPLEX-tier requests and ACTUALLY INVOKE them to see alternation in logs.
    This will show [LLM INVOKE] logs switching between 8686 and 8787 URLs.
    """
    print("\n" + "=" * 80)
    print("TEST: ROUND ROBIN EXTERNAL (COMPLEX) - ACTUAL INVOCATIONS")
    print("=" * 80)
    
    # Simple prompt for quick testing
    test_prompt = "Classify this as positive or negative: This is great!"
    
    print("Making 5 COMPLEX tier requests to see round-robin alternation...")
    for i in range(5):
        print(f"\n--- Request {i+1} ---")
        llm = get_llm(ModelTier.COMPLEX)
        
        # Actually invoke the LLM to trigger routing and [LLM INVOKE] log
        try:
            response = llm.invoke(test_prompt)
            print(f"✅ Request {i+1} completed successfully")
            print(f"Response preview: {response.content[:50]}...")
        except Exception as e:
            print(f"❌ Request {i+1} failed: {e}")
    
    print("\n✅ Round-robin test completed - check [LLM INVOKE] logs above for alternation between:")
    print("   - external_a (8686)")
    print("   - external_b (8787)")
    print("COMPLEX tier should alternate between these two servers.")


def test_simple_llm() -> None:
    """Test simple LLM with basic classification task."""
    print("\n" + "=" * 80)
    print("TEST: SIMPLE LLM")
    print("=" * 80)
    print("🤖🔍 Testing SIMPLE LLM...")

    prompt = PromptTemplate.from_template(test_simple_llm_prompt).format(text="This is a great day!")
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = _coerce_to_runnable(llm) | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Simple LLM result: {r.response}")
    print("-" * 80)


def test_medium_llm() -> None:
    """Test medium LLM with summarization task."""
    print("\n" + "=" * 80)
    print("TEST: MEDIUM LLM")
    print("=" * 80)
    print("🤖📊 Testing MEDIUM LLM...")
    prompt = PromptTemplate.from_template(test_medium_llm_prompt).format(text="The Federal Reserve announced a 25 basis point rate cut today, citing concerns about economic growth and inflation targets.")
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = _coerce_to_runnable(llm) | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Medium LLM result: {r.response}")
    print("-" * 80)


def test_complex_llm() -> None:
    """Test complex LLM with analysis task."""
    print("\n" + "=" * 80)
    print("TEST: COMPLEX LLM")
    print("=" * 80)
    print("🤖🧠 Testing COMPLEX LLM...")
    prompt = PromptTemplate.from_template(test_complex_llm_prompt).format(news="Oil prices surged 5% after OPEC announced surprise production cuts, while the dollar weakened against major currencies.")
    llm = get_llm(ModelTier.COMPLEX)
    parser = JsonOutputParser()
    chain = _coerce_to_runnable(llm) | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Complex LLM result: {r.response}")
    print("-" * 80)


def test_simple_long_context_llm() -> None:
    """Test simple long context LLM with a basic long-context task."""
    print("\n" + "=" * 80)
    print("TEST: SIMPLE LONG CONTEXT LLM")
    print("=" * 80)
    print("🤖🧩 Testing SIMPLE_LONG_CONTEXT LLM...")
    prompt = PromptTemplate.from_template(test_simple_long_context_llm_prompt).format(text="Hello, this is a test sentence for the simple long context LLM.")
    llm = get_llm(ModelTier.SIMPLE_LONG_CONTEXT)
    parser = JsonOutputParser()
    chain = _coerce_to_runnable(llm) | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Simple Long Context LLM result: {r.response}")
    print("-" * 80)


def run_all_tests() -> None:
    """Run all LLM tier tests."""
    print("=" * 50)
    print("TESTING ALL LLM TIERS")
    print("=" * 50)

    try:
        # Routing verification before functional tests
        test_router_short_vs_long()
        test_round_robin_external()
        test_simple_llm()
        test_medium_llm()
        test_complex_llm()
        test_simple_long_context_llm()
        print("✅ All LLM tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    print('About to run all LLM tests.')
    run_all_tests()

def test_router_short_vs_long() -> None:
    """Verify router sends short requests to local and very long to external."""
    print("\n" + "=" * 80)
    print("TEST: ROUTER SHORT VS LONG")
    print("=" * 80)
    
    # Test short input - should go to local when invoked
    short_text = "Hello world!"
    llm_short = get_llm(ModelTier.SIMPLE)
    print(f"Testing short text routing...")
    try:
        response_short = llm_short.invoke(short_text)
        print(f"Short text routed successfully (check logs for server)")
    except Exception as e:
        print(f"Short text invoke failed: {e}")

    # Test very long input - should exceed TOKEN_THRESHOLD and go external
    long_text = ("markets analysis economic indicators financial data ") * 100  # ~500 words → ~650 tokens
    llm_long = get_llm(ModelTier.SIMPLE)
    print(f"Testing long text routing...")
    try:
        response_long = llm_long.invoke(long_text)
        print(f"Long text routed successfully (check logs for server)")
    except Exception as e:
        print(f"Long text invoke failed: {e}")
    
    print("✅ Router routing tested (check [LLM INVOKE] logs for actual server selection)")
