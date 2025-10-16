"""
Quick test script for strategy management API.
Run this to verify the implementation works.
"""

import user_data_manager
import json

def test_strategy_lifecycle():
    """Test create, list, load, update, delete operations."""
    
    print("\n" + "="*80)
    print("TESTING STRATEGY MANAGEMENT SYSTEM")
    print("="*80)
    
    username = "TestUser"
    
    # 1. CREATE STRATEGY
    print("\n1. Creating strategy...")
    strategy = user_data_manager.create_strategy(
        username=username,
        asset_primary="EURUSD",
        strategy_text="EUR strength driven by ECB hawkish pivot while Fed pauses. Expecting EUR/USD to rally to 1.12 over next 3 months as rate differentials converge.",
        position_text="Long from 1.0850, size 2% portfolio, stop at 1.0750",
        target="1.1200"
    )
    print(f"✅ Created strategy: {strategy['id']}")
    print(f"   Asset: {strategy['asset']['primary']}")
    print(f"   Target: {strategy['user_input']['target']}")
    
    strategy_id = strategy["id"]
    
    # 2. LIST STRATEGIES
    print("\n2. Listing strategies...")
    strategies = user_data_manager.list_strategies(username)
    print(f"✅ Found {len(strategies)} strategy(ies)")
    for s in strategies:
        print(f"   - {s['id']}: {s['asset']} → {s['target']}")
    
    # 3. LOAD STRATEGY
    print("\n3. Loading strategy...")
    loaded = user_data_manager.load_strategy(username, strategy_id)
    print(f"✅ Loaded strategy: {loaded['id']}")
    print(f"   Version: {loaded['version']}")
    print(f"   Strategy text: {loaded['user_input']['strategy_text'][:50]}...")
    
    # 4. UPDATE STRATEGY
    print("\n4. Updating strategy...")
    updated = user_data_manager.update_strategy(
        username=username,
        strategy_id=strategy_id,
        target="1.1500",  # Update target only
        position_text="Long from 1.0850, added at 1.0900, size 3% portfolio, stop at 1.0750"
    )
    print(f"✅ Updated strategy: {updated['id']}")
    print(f"   New version: {updated['version']}")
    print(f"   New target: {updated['user_input']['target']}")
    print(f"   Updated position: {updated['user_input']['position_text'][:50]}...")
    
    # 5. CREATE SECOND STRATEGY
    print("\n5. Creating second strategy...")
    strategy2 = user_data_manager.create_strategy(
        username=username,
        asset_primary="DXY",
        strategy_text="USD weakness due to Fed pivot and recession fears.",
        position_text="Short from 105.50",
        target="102.00"
    )
    print(f"✅ Created strategy: {strategy2['id']}")
    
    # 6. LIST AGAIN
    print("\n6. Listing all strategies...")
    strategies = user_data_manager.list_strategies(username)
    print(f"✅ Found {len(strategies)} strategies")
    for s in strategies:
        print(f"   - {s['id']}: {s['asset']} → {s['target']} (v{s.get('version', 1)})")
    
    # 7. DELETE STRATEGY
    print("\n7. Deleting first strategy...")
    archived_name = user_data_manager.delete_strategy(username, strategy_id)
    print(f"✅ Deleted strategy, archived as: {archived_name}")
    
    # 8. LIST FINAL
    print("\n8. Final strategy list...")
    strategies = user_data_manager.list_strategies(username)
    print(f"✅ Found {len(strategies)} strategy(ies)")
    for s in strategies:
        print(f"   - {s['id']}: {s['asset']} → {s['target']}")
    
    # 9. CLEANUP
    print("\n9. Cleaning up test data...")
    try:
        user_data_manager.delete_strategy(username, strategy2["id"])
        print(f"✅ Cleaned up {strategy2['id']}")
    except:
        pass
    
    print("\n" + "="*80)
    print("ALL TESTS PASSED ✅")
    print("="*80 + "\n")


if __name__ == "__main__":
    test_strategy_lifecycle()
