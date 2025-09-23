"""
Test script for Argos API v2
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_login():
    """Test user authentication"""
    print("=== Testing Login ===")
    
    # Test valid login
    response = requests.post(f"{BASE_URL}/login", json={
        "username": "Victor",
        "password": "v123"
    })
    
    if response.status_code == 200:
        print("✅ Victor login successful")
        print(f"Response: {response.json()}")
    else:
        print(f"❌ Victor login failed: {response.status_code}")
    
    # Test invalid login
    response = requests.post(f"{BASE_URL}/login", json={
        "username": "Victor",
        "password": "wrong"
    })
    
    if response.status_code == 401:
        print("✅ Invalid login correctly rejected")
    else:
        print(f"❌ Invalid login should be rejected: {response.status_code}")
    
    print()

def test_interests():
    """Test getting user interests"""
    print("=== Testing Interests ===")
    
    response = requests.get(f"{BASE_URL}/interests?username=Victor")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Victor has {len(data['interests'])} interests")
        for interest in data['interests'][:3]:  # Show first 3
            print(f"  - {interest['id']}: {interest['name']}")
    else:
        print(f"❌ Failed to get interests: {response.status_code}")
    
    print()

def test_articles():
    """Test getting articles for a topic"""
    print("=== Testing Articles ===")
    
    # Use first topic from Victor's list
    response = requests.get(f"{BASE_URL}/articles?topic_id=brent&limit=3")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data['articles'])} articles for brent")
        for article in data['articles']:
            print(f"  - {article['id']}: {article['title'][:50]}...")
    else:
        print(f"❌ Failed to get articles: {response.status_code}")
    
    print()

def test_reports():
    """Test getting reports for a topic"""
    print("=== Testing Reports ===")
    
    # Test Markdown format (default)
    response = requests.get(f"{BASE_URL}/reports/brent")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Got Markdown report for {data['topic_name']} (default)")
        print("📄 Markdown Preview (first 300 chars):")
        print("-" * 60)
        print(data['markdown'][:300] + "...")
        print("-" * 60)
    else:
        print(f"❌ Failed to get Markdown report: {response.status_code}")
        print(f"Response: {response.text}")
    
    # Test JSON format (alternative)
    response_json = requests.get(f"{BASE_URL}/reports/brent?format=json")
    
    if response_json.status_code == 200:
        data_json = response_json.json()
        print(f"✅ Got JSON report for {data_json['topic_name']}")
        print(f"  Sections: {list(data_json['sections'].keys())}")
    else:
        print(f"❌ Failed to get JSON report: {response_json.status_code}")
    
    print()

def test_chat():
    """Test chat functionality with enhanced god-tier prompt"""
    print("=== Testing Enhanced Chat (Articles → Reports Structure) ===")
    
    # Test 1: Market outlook question
    print("📊 Question 1: Market Outlook")
    response1 = requests.post(f"{BASE_URL}/chat", json={
        "message": "What's the most likely direction for Brent over the next 2 weeks?",
        "topic_id": "brent",
        "history": []
    })
    
    if response1.status_code == 200:
        data1 = response1.json()
        print("✅ Chat response received")
        print("=" * 80)
        print(data1['response'])
        print("=" * 80)
        
        # Test 2: Risk analysis follow-up
        print("\n📈 Question 2: Risk Analysis Follow-up")
        response2 = requests.post(f"{BASE_URL}/chat", json={
            "message": "What's the biggest risk to this view?",
            "topic_id": "brent",
            "history": [
                {"role": "user", "content": "What's the most likely direction for Brent over the next 2 weeks?"},
                {"role": "assistant", "content": data1['response']}
            ]
        })
        
        if response2.status_code == 200:
            data2 = response2.json()
            print("✅ Follow-up response received")
            print("=" * 80)
            print(data2['response'])
            print("=" * 80)
        else:
            print(f"❌ Follow-up failed: {response2.status_code}")
            
    else:
        print(f"❌ Chat failed: {response1.status_code}")
        print(f"Response: {response1.text}")
    
    print()

def test_health():
    """Test health check"""
    print("=== Testing Health ===")
    
    response = requests.get(f"{BASE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Health check: {data['status']}")
        print(f"Neo4j: {data['neo4j']}")
    else:
        print(f"❌ Health check failed: {response.status_code}")
    
    print()

if __name__ == "__main__":
    print("🚀 Testing Argos API v2")
    print("Make sure the API server is running: python api_main_v2.py\n")
    
    try:
        # Test basic connectivity
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ API server not responding. Start it with: python api_main_v2.py")
            exit(1)
        
        print(f"✅ API server is running: {response.json()}\n")
        
        # Run all tests
        test_health()
        test_login()
        test_interests()
        test_articles()
        test_reports()
        test_chat()
        
        print("🎉 All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server. Start it with: python api_main_v2.py")
    except Exception as e:
        print(f"❌ Test error: {e}")
