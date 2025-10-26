"""
Test Custom User Analysis System - Uses Backend API

Minimal test: Get random user + strategy, rewrite it.
"""

import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from src.custom_user_analysis.strategy_analyzer import generate_custom_user_analysis
from src.api.backend_client import get_all_users, get_user_strategies, get_strategy


def test_rewrite_random_strategy():
    """
    Minimal test: Get random user + strategy from Backend API and rewrite it.
    """
    
    print("\n" + "="*80)
    print("TESTING CUSTOM USER ANALYSIS - Backend API")
    print("="*80)
    
    # 1. Get random user from Backend API
    print(f"\n1. Getting users from Backend API...")
    usernames = get_all_users()
    
    if not usernames:
        print(f"❌ No users found in Backend API")
        return
    
    username = usernames[0]  # Use first user
    print(f"✅ Using user: {username}")
    
    # 2. Get random strategy
    print(f"\n2. Getting strategies for {username}...")
    strategies = get_user_strategies(username)
    
    if not strategies:
        print(f"❌ No strategies found for {username}")
        return
    
    strategy_id = strategies[0]["id"]  # Use first strategy
    print(f"✅ Using strategy: {strategy_id}")
    print(f"   Asset: {strategies[0].get('asset', 'Unknown')}")
    
    # 3. Load full strategy
    print(f"\n3. Loading strategy details...")
    strategy = get_strategy(username, strategy_id)
    print(f"✅ Strategy loaded:")
    print(f"   Asset: {strategy['asset']['primary']}")
    print(f"   Thesis: {strategy['user_input']['strategy_text'][:100]}...")
    
    # 4. Rewrite it
    print(f"\n4. Rewriting strategy with full Neo4j material...")
    print("   This will take 60-90 seconds...")
    
    try:
        generate_custom_user_analysis(
            username=username,
            strategy_id=strategy_id,
            test=False  # Use full COMPLEX model
        )
        
        print("\n✅ Analysis generation complete!")
        
        # 5. Verify
        print(f"\n5. Verifying analysis...")
        updated = get_strategy(username, strategy_id)
        analysis = updated["analysis"]
        
        print(f"   ✅ Generated at: {analysis['generated_at']}")
        print(f"   ✅ Fundamental: {len(analysis['fundamental'])} chars")
        print(f"   ✅ Current: {len(analysis['current'])} chars")
        print(f"   ✅ Risks: {len(analysis['risks'])} chars")
        print(f"   ✅ Drivers: {len(analysis['drivers'])} chars")
        
        print("\n" + "="*80)
        print("TEST PASSED ✅")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_rewrite_random_strategy()
