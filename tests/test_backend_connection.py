#!/usr/bin/env python3
"""
Test Backend API Connection
Tests backend endpoints and routing
"""
import sys
import os
import requests

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed - env vars must be set manually
    pass

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.api.backend_client import ingest_article, get_article
from datetime import datetime

# Backend URL
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("BACKEND_API_KEY", "")


def test_backend_connection():
    """Test basic backend connectivity and endpoints"""
    
    print("=" * 80)
    print("🧪 BACKEND API CONNECTION TEST")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Key: {'✅ Set' if API_KEY else '❌ Missing'}")
    print()
    
    # Test 1: Health check
    print("📊 Test 1: Health Check")
    print("-" * 80)
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        print(f"✅ GET /health - Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    print()
    
    # Test 2: Check available routes
    print("📋 Test 2: Available Routes")
    print("-" * 80)
    test_routes = [
        ("GET", "/"),
        ("GET", "/health"),
        ("POST", "/api/articles/ingest"),  # Article ingestion
        ("GET", "/api/articles/test123"),  # Article retrieval
        ("GET", "/api/users"),  # User list
    ]
    
    for method, path in test_routes:
        try:
            if method == "GET":
                response = requests.get(
                    f"{BACKEND_URL}{path}",
                    headers={"X-API-Key": API_KEY} if API_KEY else {},
                    timeout=5
                )
            else:  # POST
                response = requests.post(
                    f"{BACKEND_URL}{path}",
                    json={},
                    headers={"X-API-Key": API_KEY} if API_KEY else {},
                    timeout=5
                )
            
            if response.status_code == 404:
                print(f"❌ {method} {path} - NOT FOUND (404)")
            elif response.status_code == 405:
                print(f"⚠️  {method} {path} - Method Not Allowed (405) - endpoint exists but wrong method")
            elif response.status_code < 500:
                print(f"✅ {method} {path} - Status: {response.status_code}")
            else:
                print(f"⚠️  {method} {path} - Server Error: {response.status_code}")
        except Exception as e:
            print(f"❌ {method} {path} - Error: {e}")
    print()
    
    # Test 3: Try /ingest endpoint
    print("📤 Test 3: Article Ingestion (/articles/ingest)")
    print("-" * 80)
    test_article = {
        "title": "Test Article - Backend Connection Test",
        "url": f"https://test.example.com/article-{datetime.now().timestamp()}",
        "pubDate": datetime.now().strftime("%Y-%m-%d"),
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "publishedAt": datetime.now().isoformat(),
        "description": "This is a test article to verify backend connectivity",
        "content": "Full test article content goes here. This is just a test.",
        "source": {"name": "Test Source", "url": "https://test.example.com"},
        "argos_summary": "Test summary for backend connection verification",
        "argos_topic": "Test Topic"
    }
    
    print(f"Testing URL: {test_article['url']}")
    print()
    
    try:
        result = ingest_article(test_article)
        
        print("✅ Ingest successful!")
        print(f"   Article ID: {result['argos_id']}")
        print(f"   Status: {result['status']}")
        print()
        
        article_id = result['argos_id']
        
        # Test 4: Deduplication
        print("📤 Test 4: Deduplication")
        print("-" * 80)
        result2 = ingest_article(test_article)
        
        dedup_passed = result2['status'] == 'existing' and result2['argos_id'] == article_id
        if dedup_passed:
            print("✅ Deduplication works!")
            print(f"   Returned same ID: {result2['argos_id']}")
        else:
            print("❌ Deduplication failed!")
            print(f"   First ID: {article_id}, Second ID: {result2['argos_id']}")
        print()
        
        # Test 5: Retrieval
        print("📥 Test 5: Article Retrieval")
        print("-" * 80)
        retrieved = get_article(article_id)
        
        retrieval_passed = retrieved is not None
        if retrieval_passed:
            print("✅ Retrieval successful!")
            print(f"   Title: {retrieved.get('title', 'N/A')}")
        else:
            print("❌ Failed to retrieve article")
        print()
        
        # Final summary
        all_passed = dedup_passed and retrieval_passed
        
        print("=" * 80)
        if all_passed:
            print("✅ ALL TESTS PASSED!")
        else:
            print("⚠️  SOME TESTS FAILED!")
        print("=" * 80)
        print()
        print("Summary:")
        print("  ✅ Backend is running")
        print("  ✅ /api/articles/ingest endpoint works")
        print(f"  {'✅' if dedup_passed else '❌'} Deduplication works")
        print(f"  {'✅' if retrieval_passed else '❌'} Article retrieval works")
        
        return all_passed
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Backend test failed!")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check backend is running: curl http://localhost:8000/health")
        print("  2. Check BACKEND_API_URL in .env")
        print("  3. Check BACKEND_API_KEY in .env")
        print("  4. Check backend logs: docker compose logs saga-apis")
        return False
    
    return True


if __name__ == "__main__":
    success = test_backend_connection()
    sys.exit(0 if success else 1)
