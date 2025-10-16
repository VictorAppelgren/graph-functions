"""
Test the unified perspective classifier
"""
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.llm.classify_article import classify_article_complete


def test_classifier():
    """Test classifier with various article types"""
    
    tests = [
        ("Pure Risk", 
         "Fed emergency hikes could crash markets 15%. Hawkish surprise threatens equities."),
        
        ("Risk + Opportunity", 
         "Fed cuts boost growth but risk inflation reacceleration. Dual-edged policy move."),
        
        ("All 4 Perspectives!", 
         "BREAKING: Fed cuts NOW (catalyst), boosting risk assets (opportunity), "
         "but inflation risk (risk) signals regime shift (trend)."),
        
        ("Trend", 
         "Deglobalization reshaping trade for decades. Structural shift in supply chains."),
        
        ("Invalid", 
         "Celebrity gossip. No financial relevance.")
    ]
    
    print("\n" + "="*80)
    print("TESTING UNIFIED PERSPECTIVE CLASSIFIER")
    print("="*80)
    
    for name, text in tests:
        print(f"\n{'─'*80}")
        print(f"TEST: {name}")
        print(f"TEXT: {text[:100]}...")
        print(f"{'─'*80}")
        
        try:
            result = classify_article_complete(text)
            
            print(f"✅ Horizon: {result.temporal_horizon}")
            print(f"✅ Category: {result.category}")
            print(f"✅ Scores: R:{result.importance_risk} | O:{result.importance_opportunity} | "
                  f"T:{result.importance_trend} | C:{result.importance_catalyst}")
            print(f"✅ Primary Perspectives: {result.primary_perspectives}")
            print(f"✅ Dominant: {result.dominant_perspective}")
            print(f"✅ Overall Importance: {result.overall_importance}")
            print(f"✅ Motivation: {result.motivation}")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    test_classifier()
