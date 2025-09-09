"""
Minimalistic test for all three LLM tiers: simple, medium, complex.
Tests basic LangChain functionality with string output.
"""
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from llm.llm_router import get_simple_llm, get_medium_llm, get_complex_llm, get_simple_long_context_llm
from langchain_core.prompts import PromptTemplate

def test_simple_llm():
    """Test simple LLM with basic classification task."""
    print("🤖🔍 Testing SIMPLE LLM...")
    
    prompt_template = """
    Classify this text as either "positive" or "negative":
    Text: {text}
    
    Answer with just one word: positive or negative
    """
    
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_simple_llm()
    chain = prompt | llm
    
    result = chain.invoke({"text": "The market is performing well today"})
    print(f"Simple LLM result: {result.content}")
    return result.content

def test_medium_llm():
    """Test medium LLM with summarization task."""
    print("🤖📊 Testing MEDIUM LLM...")
    
    prompt_template = """
    Summarize this text in one sentence:
    Text: {text}
    
    Summary:
    """
    
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_medium_llm()
    chain = prompt | llm
    
    result = chain.invoke({"text": "The Federal Reserve announced today that interest rates will remain unchanged at 5.25%. This decision comes after months of economic uncertainty and inflation concerns. Market analysts expect this to stabilize bond yields in the short term."})
    print(f"Medium LLM result: {result.content}")
    return result.content

def test_complex_llm():
    """Test complex LLM with analysis task."""
    print("🤖🧠 Testing COMPLEX LLM...")
    
    prompt_template = """
    Analyze the market implications of this news in 2-3 sentences:
    News: {news}
    
    Analysis:
    """
    
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_complex_llm()
    chain = prompt | llm
    
    result = chain.invoke({"news": "ECB raises interest rates by 0.5% citing persistent inflation concerns across eurozone economies"})
    print(f"Complex LLM result: {result.content}")
    return result.content

def test_simple_long_context_llm():
    """Test simple long context LLM with a basic long-context task."""
    print("🤖🧩 Testing SIMPLE_LONG_CONTEXT LLM...")
    prompt_template = """
    Repeat the following sentence exactly once: {text}
    """
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_simple_long_context_llm()
    chain = prompt | llm
    result = chain.invoke({"text": "This is a test for long context."})
    print(f"Simple Long Context LLM result: {result.content}")
    return result.content

def run_all_tests():
    """Run all LLM tier tests."""
    print("=" * 50)
    print("TESTING ALL LLM TIERS")
    print("=" * 50)
    
    try:
        test_simple_llm()
        print()
        test_medium_llm()
        print()
        test_complex_llm()
        print()
        test_simple_long_context_llm()
        print()
        print("✅ All LLM tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    run_all_tests()