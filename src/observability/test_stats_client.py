"""
Quick test for stats tracking client.
Run this to verify the backend API is reachable before starting the main pipeline.

Usage:
    python -m src.observability.test_stats_client
"""
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.observability.stats_client import track, BACKEND_URL, API_KEY


def test_stats_connection():
    """Test if stats backend is reachable"""
    print("=" * 60)
    print("🧪 TESTING STATS CLIENT CONNECTION")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Key configured: {'Yes' if API_KEY else 'No'}")
    print()
    
    # Test 1: Simple event tracking
    print("Test 1: Sending test event...")
    try:
        track("test_event", "Testing stats client connection")
        print("✅ SUCCESS: Event tracked successfully!")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check if saga-be is running: docker ps | grep saga-be")
        print("2. Check BACKEND_API_URL in .env file")
        print("3. Check BACKEND_API_KEY in .env file (if NGINX requires it)")
        print("4. Test backend directly: curl http://localhost:8000/api/stats/today")
        sys.exit(1)
    
    print()
    
    # Test 2: Event with message
    print("Test 2: Sending event with message...")
    try:
        track("test_event_with_message", "This is a test message with details")
        print("✅ SUCCESS: Event with message tracked!")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✅ ALL TESTS PASSED - Stats client is working!")
    print("=" * 60)
    print()
    print("You can now run main.py safely.")


if __name__ == "__main__":
    test_stats_connection()
