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
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision, TestResult
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.prompts.test_simple_long_context_llm import test_simple_long_context_llm_prompt
from src.llm.prompts.test_complex_llm import test_complex_llm_prompt
from src.llm.prompts.test_medium_llm import test_medium_llm_prompt
from src.llm.prompts.test_simple_llm import test_simple_llm_prompt


def test_simple_llm() -> None:
    """Test simple LLM with basic classification task."""
    print("🤖🔍 Testing SIMPLE LLM...")

    prompt = PromptTemplate.from_template(test_simple_llm_prompt).format()
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = llm | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Simple LLM result: {r.response}")


def test_medium_llm() -> None:
    """Test medium LLM with summarization task."""
    print("🤖📊 Testing MEDIUM LLM...")

    prompt = PromptTemplate.from_template(test_medium_llm_prompt).format()
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = llm | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Medium LLM result: {r.response}")


def test_complex_llm() -> None:
    """Test complex LLM with analysis task."""
    print("🤖🧠 Testing COMPLEX LLM...")

    prompt = PromptTemplate.from_template(test_complex_llm_prompt).format()
    llm = get_llm(ModelTier.COMPLEX)
    parser = JsonOutputParser()
    chain = llm | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Complex LLM result: {r.response}")


def test_simple_long_context_llm() -> None:
    """Test simple long context LLM with a basic long-context task."""
    print("🤖🧩 Testing SIMPLE_LONG_CONTEXT LLM...")
    prompt = PromptTemplate.from_template(test_simple_long_context_llm_prompt).format()
    llm = get_llm(ModelTier.SIMPLE_LONG_CONTEXT)
    parser = JsonOutputParser()
    chain = llm | parser

    r = run_llm_decision(chain=chain, prompt=prompt, model=TestResult)

    print(f"Simple Long Context LLM result: {r.response}")


def run_all_tests() -> None:
    """Run all LLM tier tests."""
    print("=" * 50)
    print("TESTING ALL LLM TIERS")
    print("=" * 50)

    try:
        test_simple_llm()
        test_medium_llm()
        test_complex_llm()
        test_simple_long_context_llm()
        print("✅ All LLM tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
