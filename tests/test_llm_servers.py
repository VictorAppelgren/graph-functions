"""
Test all LLM servers to verify connectivity and response.
"""
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env file FIRST
from utils.env_loader import load_env
load_env()

from src.llm.config import SERVERS, _build_llm
from utils.app_logging import get_logger

logger = get_logger(__name__)


def test_server(server_id: str) -> dict:
    """Test a single LLM server with a simple prompt."""
    config = SERVERS.get(server_id)
    if not config:
        return {
            'server_id': server_id,
            'status': 'NOT_CONFIGURED',
            'error': 'Server not found in SERVERS config'
        }
    
    print(f"\n{'='*80}")
    print(f"Testing: {server_id}")
    print(f"  Provider: {config['provider']}")
    print(f"  Model: {config['model']}")
    print(f"  URL: {config.get('base_url', 'N/A')}")
    print(f"{'='*80}")
    
    try:
        # Build LLM client
        llm = _build_llm(server_id)
        
        # Use different prompts based on server type
        # For external servers (ONLY a and b now: 8686 and 8787) - generate substantial text to test GPU load
        if server_id in ['external_a', 'external_b']:
            test_prompt = """Write a detailed 500-word analysis of the current state of artificial intelligence 
and its impact on financial markets. Include discussion of:
1. Machine learning applications in trading
2. Natural language processing for market sentiment
3. Risk management and AI
4. Future trends and predictions
5. Regulatory considerations

Be comprehensive and detailed."""
            print(f"Sending LONG test prompt (500 words) to stress-test GPU...")
        else:
            # For local and nano - keep it simple
            test_prompt = "Say 'OK' if you can read this."
            print(f"Sending simple test prompt...")
        
        # Invoke with timeout
        import time
        start_time = time.time()
        response = llm.invoke(test_prompt)
        elapsed = time.time() - start_time
        
        response_text = response.content if hasattr(response, 'content') else str(response)
        word_count = len(response_text.split())
        
        print(f"✅ SUCCESS")
        print(f"Response time: {elapsed:.2f}s")
        print(f"Response length: {len(response_text)} chars, {word_count} words")
        print(f"Response preview: {response_text[:200]}...")
        
        return {
            'server_id': server_id,
            'status': 'SUCCESS',
            'response': response_text[:500],
            'response_time': elapsed,
            'word_count': word_count,
            'char_count': len(response_text),
            'provider': config['provider'],
            'model': config['model'],
            'url': config.get('base_url', 'N/A')
        }
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        print(f"❌ FAILED: {error_type}")
        print(f"Error: {error_msg[:200]}")
        
        return {
            'server_id': server_id,
            'status': 'FAILED',
            'error_type': error_type,
            'error': error_msg[:500],
            'provider': config['provider'],
            'model': config['model'],
            'url': config.get('base_url', 'N/A')
        }


def test_all_servers():
    """Test all configured LLM servers."""
    
    print("\n" + "="*80)
    print("LLM SERVER CONNECTIVITY TEST")
    print("="*80)
    print(f"Testing {len(SERVERS)} configured servers...")
    
    results = []
    
    # Test each server
    for server_id in SERVERS.keys():
        result = test_server(server_id)
        results.append(result)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    failed_count = sum(1 for r in results if r['status'] == 'FAILED')
    
    print(f"\nTotal Servers: {len(results)}")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {failed_count}")
    
    # Show performance stats for external servers
    external_results = [r for r in results if r['server_id'].startswith('external_') and r['status'] == 'SUCCESS']
    if external_results:
        print(f"\n{'='*80}")
        print("EXTERNAL SERVER PERFORMANCE (GPU Load Test):")
        print(f"{'='*80}")
        for r in external_results:
            print(f"\n{r['server_id']:15s} - {r['response_time']:.2f}s")
            print(f"   Generated: {r['word_count']} words ({r['char_count']} chars)")
            print(f"   Speed: {r['word_count']/r['response_time']:.1f} words/sec")
    
    if failed_count > 0:
        print(f"\n{'='*80}")
        print("FAILED SERVERS:")
        print(f"{'='*80}")
        for r in results:
            if r['status'] == 'FAILED':
                print(f"\n❌ {r['server_id']}")
                print(f"   URL: {r['url']}")
                print(f"   Error: {r['error_type']}")
                print(f"   Message: {r['error'][:200]}")
    
    print(f"\n{'='*80}")
    print("DETAILED RESULTS:")
    print(f"{'='*80}")
    
    for r in results:
        status_icon = "✅" if r['status'] == 'SUCCESS' else "❌"
        print(f"\n{status_icon} {r['server_id']:15s} - {r['status']}")
        print(f"   Provider: {r.get('provider', 'N/A')}")
        print(f"   Model: {r.get('model', 'N/A')}")
        print(f"   URL: {r.get('url', 'N/A')}")
        if r['status'] == 'FAILED':
            print(f"   Error: {r.get('error_type', 'Unknown')}")
    
    print(f"\n{'='*80}\n")
    
    return results


if __name__ == "__main__":
    try:
        results = test_all_servers()
        
        # Exit with error code if any server failed
        failed = any(r['status'] == 'FAILED' for r in results)
        sys.exit(1 if failed else 0)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
