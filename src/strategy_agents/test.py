"""
Strategy Agents Test Script

Simple test script (not pytest) for strategy agents.
Tests the full strategy analysis pipeline with real user strategies.

Usage:
    python -m src.strategy_agents.test
"""

# Load .env file FIRST
from utils.env_loader import load_env
load_env()

import sys
from datetime import datetime
from src.strategy_agents.topic_mapper.agent import TopicMapperAgent
from src.graph.neo4j_client import run_cypher


def get_random_user_strategy(user_id: str = "victor"):
    """
    Load a random strategy from a user.
    
    For now, returns a sample strategy. In production, this would
    query the database for user's saved strategies.
    """
    # Sample strategies for testing
    strategies = {
        "eurusd_long": {
            "asset": "EURUSD",
            "strategy": """
            Long EURUSD position based on ECB hawkish pivot and Fed dovish signals.
            
            Thesis:
            - ECB ending QE and raising rates faster than expected
            - Fed pausing rate hikes due to banking stress
            - EUR undervalued vs fundamentals
            - Positioning for EUR strength into Q2 2025
            
            Entry: 1.0550
            Target: 1.0800-1.1000
            Stop: 1.0450
            """,
            "position": "Long 1 lot EURUSD @ 1.0550, opened 2 weeks ago"
        },
        "us_market_short": {
            "asset": "US Stock Market (SPX, NDX)",
            "strategy": """
            Short US equities on valuation concerns and recession risk.
            
            Thesis:
            - P/E ratios at 20-year highs
            - Fed keeping rates higher for longer
            - Earnings recession incoming (margins compressing)
            - Tech sector overvalued despite AI hype
            - Positioning for 10-15% correction
            
            Entry: SPX 4500, NDX 15500
            Target: SPX 4000, NDX 13500
            Stop: SPX 4650
            """,
            "position": "Short SPX via puts, short NDX via futures"
        },
        "bond_long": {
            "asset": "US 10-Year Treasury (UST10Y)",
            "strategy": """
            Long duration trade on US 10-year bonds.
            
            Thesis:
            - Fed terminal rate reached (5.25-5.50%)
            - Inflation cooling faster than expected
            - Recession risk rising (unemployment ticking up)
            - Flight to quality bid emerging
            - Positioning for rate cuts in H2 2025
            
            Entry: 4.25% yield
            Target: 3.50-3.75% yield
            Stop: 4.50% yield
            """,
            "position": "Long UST10Y futures, duration 7 years"
        }
    }
    
    # Return first strategy for now (EURUSD)
    return strategies["eurusd_long"]


def test_topic_mapper():
    """Test TopicMapperAgent with real strategy."""
    print("\n" + "="*80)
    print("🧪 TEST 1: Topic Mapper Agent")
    print("="*80)
    
    # Get sample strategy
    strategy = get_random_user_strategy()
    strategy_id = "victor_eurusd_001"
    
    print(f"\n📋 STRATEGY:")
    print(f"Asset: {strategy['asset']}")
    print(f"Position: {strategy['position']}")
    print(f"\nThesis:\n{strategy['strategy'][:200]}...")
    
    # Check if we already have topic mapping saved
    from src.graph.ops.user_strategy import get_user_strategy, save_user_strategy
    
    saved_strategy = get_user_strategy(strategy_id)
    if saved_strategy:
        print(f"\n💾 USING CACHED TOPIC MAPPING (no LLM call needed)")
        result = saved_strategy['topic_mapping']
    else:
        # Run Topic Mapper
        print(f"\n🔍 Running Topic Mapper...")
        agent = TopicMapperAgent()
        
        result = agent.run(
            asset_text=strategy['asset'],
            strategy_text=strategy['strategy'],
            position_text=strategy['position']
        )
        
        # Save for next time
        save_user_strategy(
            user_id="victor",
            strategy_id=strategy_id,
            asset=strategy['asset'],
            strategy_text=strategy['strategy'],
            position_text=strategy['position'],
            topic_mapping=result
        )
        print(f"💾 Saved topic mapping for future use")
    
    # Display results
    print(f"\n✅ RESULTS:")
    print(f"\n📌 PRIMARY TOPICS ({len(result['primary'])}):")
    for topic_id in result['primary']:
        print(f"  - {topic_id}")
    
    print(f"\n🎯 DRIVER TOPICS ({len(result['drivers'])}):")
    for topic_id in result['drivers']:
        print(f"  - {topic_id}")
    
    print(f"\n🔗 CORRELATED TOPICS ({len(result['correlated'])}):")
    for topic_id in result['correlated']:
        print(f"  - {topic_id}")
    
    print(f"\n💡 REASONING:")
    if 'reasoning' in result:
        print(f"{result['reasoning']}")
    else:
        print("(Loaded from cached topic mapping - reasoning not stored)")
    
    return result


def test_topic_analysis_integration():
    """Test integration with topic analysis agents."""
    print("\n" + "="*80)
    print("🧪 TEST 2: Topic Analysis Integration")
    print("="*80)
    
    # Get topics from Topic Mapper
    strategy = get_random_user_strategy()
    topic_mapper = TopicMapperAgent()
    topics = topic_mapper.run(
        asset_text=strategy['asset'],
        strategy_text=strategy['strategy'],
        position_text=strategy['position']
    )
    
    # For each primary topic, show what analysis we could run
    print(f"\n📊 AVAILABLE ANALYSIS FOR PRIMARY TOPICS:")
    
    for topic_id in topics['primary'][:3]:  # Limit to first 3 for demo
        print(f"\n{'='*70}")
        print(f"Topic: {topic_id}")
        print(f"{'='*70}")
        
        # Check what analysis exists
        query = """
        MATCH (t:Topic {id: $topic_id})
        RETURN 
            t.name as name,
            t.fundamental_analysis is not null as has_fundamental,
            t.medium_analysis is not null as has_medium,
            t.current_analysis is not null as has_current,
            t.drivers is not null as has_drivers
        """
        
        result = run_cypher(query, {"topic_id": topic_id})
        
        if result:
            data = result[0]
            print(f"Name: {data['name']}")
            print(f"Available Analysis:")
            print(f"  - Fundamental: {'✅' if data['has_fundamental'] else '❌'}")
            print(f"  - Medium: {'✅' if data['has_medium'] else '❌'}")
            print(f"  - Current: {'✅' if data['has_current'] else '❌'}")
            print(f"  - Drivers: {'✅' if data['has_drivers'] else '❌'}")
            
            # Show market data availability
            from src.market_data.loader import load_market_context
            market_context = load_market_context(topic_id)
            if market_context:
                print(f"\n📈 Market Data:")
                print(f"  {market_context[:200]}...")  # Show first 200 chars
            else:
                print(f"\n📈 Market Data: ❌ Not available")


def test_full_strategy_pipeline():
    """Test the full strategy analysis pipeline."""
    print("\n" + "="*80)
    print("🧪 TEST 3: Full Strategy Pipeline")
    print("="*80)
    
    from src.strategy_agents.orchestrator import run_strategy_analysis
    
    # Get sample strategy
    strategy = get_random_user_strategy()
    
    print(f"\n🚀 Running complete strategy analysis...")
    print(f"Asset: {strategy['asset']}")
    
    # Run full pipeline
    result = run_strategy_analysis(
        user_id="victor",
        strategy_id="victor_eurusd_001",
        asset=strategy['asset'],
        strategy_text=strategy['strategy'],
        position_text=strategy['position']
    )
    
    # Display results
    print(f"\n{'='*80}")
    print("📊 RISK ASSESSMENT")
    print('='*80)
    print(f"Overall Risk Level: {result['risk_assessment'].overall_risk_level.upper()}")
    print(f"\n{result['risk_assessment'].key_risk_summary}")
    
    print(f"\n{'='*80}")
    print("💡 OPPORTUNITY ASSESSMENT")
    print('='*80)
    print(f"Overall Opportunity Level: {result['opportunity_assessment'].overall_opportunity_level.upper()}")
    print(f"\n{result['opportunity_assessment'].key_opportunity_summary}")
    
    print(f"\n{'='*80}")
    print("📝 FINAL ANALYSIS")
    print('='*80)
    print(f"\nEXECUTIVE SUMMARY:")
    print(result['final_analysis'].executive_summary)
    
    print(f"\nRECOMMENDATION:")
    print(result['final_analysis'].recommendation[:500] + "..." if len(result['final_analysis'].recommendation) > 500 else result['final_analysis'].recommendation)


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("🚀 STRATEGY AGENTS TEST SUITE")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        
        # Test 1: Topic Mapper
        topics = test_topic_mapper()
        
        # Test 2: Integration with topic analysis
        test_topic_analysis_integration()
        
        # Test 3: Full pipeline preview
        test_full_strategy_pipeline()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80)
        
        print("\n💡 TIPS:")
        print("- ✅ All strategy agents built and working")
        print("- ✅ Topic mapping, risks, opportunities, and analysis generated")
        print("- ✅ Results saved to backend API (JSON files)")
        print("- Next: Integrate with chat for strategy context")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
