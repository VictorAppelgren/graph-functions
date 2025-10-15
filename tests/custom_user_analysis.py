"""
Test Custom User Analysis System

Tests the complete pipeline with Victor's actual strategy.
"""

import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from src.custom_user_analysis.strategy_analyzer import generate_custom_user_analysis

# Add API to path
API_DIR = os.path.join(PROJECT_ROOT, "API")
sys.path.append(API_DIR)
import user_data_manager


def test_custom_analysis_with_victor_strategy():
    """
    Test custom analysis generation with Victor's actual strategy.
    Uses strategy_001 which contains real user input.
    """
    
    print("\n" + "="*80)
    print("TESTING CUSTOM USER ANALYSIS SYSTEM")
    print("="*80)
    
    username = "Victor"
    
    # Get Victor's strategies
    print(f"\n1. Loading {username}'s strategies...")
    strategies = user_data_manager.list_strategies(username)
    
    if not strategies:
        print(f"❌ No strategies found for {username}")
        print("   Please create a strategy first via the API")
        return
    
    print(f"✅ Found {len(strategies)} strategy(ies):")
    for s in strategies:
        print(f"   - {s['id']}: {s['asset']} → {s['target']}")
    
    # Use first strategy
    strategy_id = strategies[0]["id"]
    
    print(f"\n2. Loading strategy details...")
    strategy = user_data_manager.load_strategy(username, strategy_id)
    print(f"✅ Strategy loaded:")
    print(f"   ID: {strategy['id']}")
    print(f"   Asset: {strategy['asset']['primary']}")
    print(f"   Target: {strategy['user_input']['target']}")
    print(f"   Thesis: {strategy['user_input']['strategy_text'][:100]}...")
    
    # Check if analysis already exists
    if strategy["analysis"]["generated_at"]:
        print(f"\n⚠️  Analysis already exists (generated at {strategy['analysis']['generated_at']})")
        print("   This test will regenerate and archive the old version.")
    
    print(f"\n3. Generating custom analysis...")
    print("   This will take 60-90 seconds...")
    print("   Steps: Topic Discovery → Material Collection → LLM Generation → Evidence Classification")
    
    try:
        # Generate analysis
        generate_custom_user_analysis(
            username=username,
            strategy_id=strategy_id,
            test=False  # Use full COMPLEX model for quality
        )
        
        print("\n✅ Analysis generation complete!")
        
        # Load updated strategy
        print(f"\n4. Verifying analysis...")
        updated_strategy = user_data_manager.load_strategy(username, strategy_id)
        
        analysis = updated_strategy["analysis"]
        
        # Verify all sections populated
        checks = {
            "Generated timestamp": analysis["generated_at"] is not None,
            "Executive summary": len(analysis.get("executive_summary", "")) > 0,
            "Fundamental analysis": len(analysis["fundamental"]) > 0,
            "Current analysis": len(analysis["current"]) > 0,
            "Risks analysis": len(analysis["risks"]) > 0,
            "Drivers analysis": len(analysis["drivers"]) > 0,
            "Related topics": len(updated_strategy["asset"]["related"]) > 0,
            "Supporting evidence": len(analysis["supporting_evidence"]) > 0,
            "Contradicting evidence": len(analysis["contradicting_evidence"]) > 0
        }
        
        all_passed = True
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
            if not passed:
                all_passed = False
        
        # Show summary
        print(f"\n5. Analysis Summary:")
        print(f"   Generated at: {analysis['generated_at']}")
        print(f"   Related topics: {len(updated_strategy['asset']['related'])} topics")
        print(f"   Supporting evidence: {len(analysis['supporting_evidence'])} items")
        print(f"   Contradicting evidence: {len(analysis['contradicting_evidence'])} items")
        print(f"   Executive summary: {len(analysis.get('executive_summary', ''))} chars")
        print(f"   Fundamental analysis: {len(analysis['fundamental'])} chars")
        print(f"   Current analysis: {len(analysis['current'])} chars")
        print(f"   Risks analysis: {len(analysis['risks'])} chars")
        print(f"   Drivers analysis: {len(analysis['drivers'])} chars")
        
        # Show sample content
        print(f"\n6. Sample Analysis Content:")
        print(f"\n   【Executive Summary】")
        print(f"   {analysis.get('executive_summary', 'Not generated')}")
        print(f"\n   【Fundamental Analysis】(first 300 chars)")
        print(f"   {analysis['fundamental'][:300]}...")
        
        print(f"\n   【Supporting Evidence】(top 3)")
        for i, evidence in enumerate(analysis['supporting_evidence'][:3], 1):
            print(f"   {i}. {evidence}")
        
        print(f"\n   【Contradicting Evidence】(top 3)")
        for i, evidence in enumerate(analysis['contradicting_evidence'][:3], 1):
            print(f"   {i}. {evidence}")
        
        print("\n" + "="*80)
        if all_passed:
            print("ALL TESTS PASSED ✅")
        else:
            print("SOME TESTS FAILED ❌")
        print("="*80 + "\n")
        
        print(f"📄 Full analysis saved to: API/users/{username}/{strategy_id}.json")
        print(f"📁 Old version archived to: API/users/{username}/archive/")
        
    except Exception as e:
        print(f"\n❌ Analysis generation failed!")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_custom_analysis_with_victor_strategy()
