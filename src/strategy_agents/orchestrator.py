"""
Strategy Analysis Orchestrator

Chains all strategy agents together.

Usage:
    python -m src.strategy_agents.orchestrator username strategy_id
    python -m src.strategy_agents.orchestrator Victor strategy_001
"""

from typing import Dict, Any, Optional
from utils import app_logging

from src.strategy_agents.topic_mapper import TopicMapperAgent
from src.strategy_agents.risk_assessor import RiskAssessorAgent
from src.strategy_agents.opportunity_finder import OpportunityFinderAgent
from src.strategy_agents.strategy_writer import StrategyWriterAgent
from src.strategy_agents.material_builder import build_material_package
from src.api.backend_client import get_strategy, save_strategy_topics, save_strategy_analysis

logger = app_logging.get_logger(__name__)

# =============================================================================
# TOKEN LIMITS
# =============================================================================
MAX_INPUT_TOKENS = 30000
MAX_OUTPUT_TOKENS = 4000


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token"""
    return len(text) // 4


def check_token_limit(text: str, label: str) -> None:
    """Check if text exceeds token limit and warn"""
    tokens = estimate_tokens(text)
    if tokens > MAX_INPUT_TOKENS:
        logger.warning(f"{label} exceeds token limit! {tokens:,} tokens (max: {MAX_INPUT_TOKENS:,})")


def run_strategy_analysis(
    user_id: str,
    strategy_id: str,
    asset: str,
    strategy_text: str,
    position_text: str
) -> Dict[str, Any]:
    """
    Run complete strategy analysis pipeline.
    
    Simple, clean, minimal. One function does everything.
    
    Args:
        user_id: User ID
        strategy_id: Unique strategy ID
        asset: Asset name (e.g., "EURUSD")
        strategy_text: User's strategy description
        position_text: User's position details
    
    Returns:
        {
            "topic_mapping": {...},
            "risk_assessment": {...},
            "opportunity_assessment": {...},
            "final_analysis": {...}
        }
    """
    logger.info("="*80)
    logger.info(f"🚀 STRATEGY ANALYSIS PIPELINE | {user_id}/{strategy_id}")
    logger.info("="*80)
    logger.info(f"Asset: {asset}")
    logger.info(f"Strategy: {strategy_text[:200]}..." if len(strategy_text) > 200 else f"Strategy: {strategy_text}")
    logger.info(f"Position: {position_text[:100]}..." if len(position_text) > 100 else f"Position: {position_text}")
    logger.info("="*80)
    
    # Step 1: Map topics (always run - topics may change)
    logger.info("\n" + "="*80)
    logger.info("STEP 1: TOPIC MAPPING")
    logger.info("="*80)
    mapper = TopicMapperAgent()
    topic_mapping = mapper.run(
        asset_text=asset,
        strategy_text=strategy_text,
        position_text=position_text
    )
    
    # Preview topic mapping
    logger.info("\n📋 TOPIC MAPPING RESULT:")
    if isinstance(topic_mapping, dict):
        primary = topic_mapping.get('primary', 'N/A')
        drivers = topic_mapping.get('drivers', [])
        correlated = topic_mapping.get('correlated', [])
        logger.info(f"   Primary: {primary}")
        logger.info(f"   Drivers: {drivers}")
        logger.info(f"   Correlated: {correlated}")
        logger.info(f"   Total Topics: {1 + len(drivers) + len(correlated)}")
    logger.info("="*80)
    
    # Save topic mapping to backend
    logger.info("\n💾 Saving topic mapping to backend...")
    save_strategy_topics(
        username=user_id,
        strategy_id=strategy_id,
        topics=topic_mapping
    )
    
    # Step 2: Build complete material package
    logger.info("\n" + "="*80)
    logger.info("STEP 2: BUILD MATERIAL PACKAGE")
    logger.info("="*80)
    material_package = build_material_package(
        user_strategy=strategy_text,
        position_text=position_text,
        topic_mapping=topic_mapping
    )
    
    # Preview material package
    logger.info("\n📦 MATERIAL PACKAGE:")
    logger.info(f"   Strategy: {len(strategy_text)} chars")
    logger.info(f"   Position: {len(position_text)} chars")
    logger.info(f"   Topic Analyses: {len(material_package.get('topic_analyses', ''))} chars")
    logger.info(f"   Market Context: {len(material_package.get('market_context', ''))} chars")
    total_chars = len(strategy_text) + len(position_text) + len(material_package.get('topic_analyses', '')) + len(material_package.get('market_context', ''))
    logger.info(f"   TOTAL: {total_chars:,} chars (~{total_chars//1000}K)")
    logger.info("="*80)
    
    # Step 3: Assess risks
    logger.info("\n" + "="*80)
    logger.info("STEP 3: RISK ASSESSMENT")
    logger.info("="*80)
    risk_assessor = RiskAssessorAgent()
    risk_assessment = risk_assessor.run(material_package)
    
    # Preview risk assessment
    logger.info("\n⚠️  RISK ASSESSMENT RESULT:")
    logger.info(f"   Overall Risk Level: {risk_assessment.overall_risk_level}")
    logger.info(f"   Position Risks: {len(risk_assessment.position_risks)}")
    logger.info(f"   Market Risks: {len(risk_assessment.market_risks)}")
    logger.info(f"   Thesis Risks: {len(risk_assessment.thesis_risks)}")
    logger.info(f"   Execution Risks: {len(risk_assessment.execution_risks)}")
    summary_preview = risk_assessment.key_risk_summary[:150] + "..." if len(risk_assessment.key_risk_summary) > 150 else risk_assessment.key_risk_summary
    logger.info(f"   Summary: {summary_preview}")
    logger.info("="*80)
    
    # Step 4: Find opportunities
    logger.info("\n" + "="*80)
    logger.info("STEP 4: OPPORTUNITY ASSESSMENT")
    logger.info("="*80)
    opportunity_finder = OpportunityFinderAgent()
    opportunity_assessment = opportunity_finder.run(material_package)
    
    # Preview opportunity assessment
    logger.info("\n💡 OPPORTUNITY ASSESSMENT RESULT:")
    logger.info(f"   Overall Opportunity Level: {opportunity_assessment.overall_opportunity_level}")
    logger.info(f"   Position Optimization: {len(opportunity_assessment.position_optimization)}")
    logger.info(f"   Strategy Enhancement: {len(opportunity_assessment.strategy_enhancement)}")
    logger.info(f"   Related Opportunities: {len(opportunity_assessment.related_opportunities)}")
    logger.info(f"   Tactical Opportunities: {len(opportunity_assessment.tactical_opportunities)}")
    summary_preview = opportunity_assessment.key_opportunity_summary[:150] + "..." if len(opportunity_assessment.key_opportunity_summary) > 150 else opportunity_assessment.key_opportunity_summary
    logger.info(f"   Summary: {summary_preview}")
    logger.info("="*80)
    
    # Step 5: Write final analysis
    logger.info("\n" + "="*80)
    logger.info("STEP 5: FINAL ANALYSIS")
    logger.info("="*80)
    writer = StrategyWriterAgent()
    final_analysis = writer.run(
        material_package=material_package,
        risk_assessment=risk_assessment,
        opportunity_assessment=opportunity_assessment
    )
    
    # Preview final analysis
    logger.info("\n📝 FINAL ANALYSIS RESULT:")
    logger.info(f"   Executive Summary: {len(final_analysis.executive_summary)} chars")
    logger.info(f"   Position Analysis: {len(final_analysis.position_analysis)} chars")
    logger.info(f"   Risk Analysis: {len(final_analysis.risk_analysis)} chars")
    logger.info(f"   Opportunity Analysis: {len(final_analysis.opportunity_analysis)} chars")
    logger.info(f"   Recommendation: {len(final_analysis.recommendation)} chars")
    exec_preview = final_analysis.executive_summary[:200] + "..." if len(final_analysis.executive_summary) > 200 else final_analysis.executive_summary
    logger.info(f"   Preview: {exec_preview}")
    logger.info("="*80)
    
    # Step 6: Save analysis to backend
    logger.info("\n" + "="*80)
    logger.info("STEP 6: SAVE TO BACKEND")
    logger.info("="*80)
    analysis_dict = {
        "risk_level": risk_assessment.overall_risk_level,
        "opportunity_level": opportunity_assessment.overall_opportunity_level,
        "risk_assessment": risk_assessment.model_dump(),
        "opportunity_assessment": opportunity_assessment.model_dump(),
        "final_analysis": final_analysis.model_dump()
    }
    save_strategy_analysis(
        username=user_id,
        strategy_id=strategy_id,
        analysis=analysis_dict
    )
    
    logger.info("✅ Analysis saved to backend")
    logger.info("="*80)
    
    # Step 7: Generate dashboard question
    logger.info("\n" + "="*80)
    logger.info("STEP 7: GENERATE DASHBOARD QUESTION")
    logger.info("="*80)
    try:
        from src.llm.prompts.generate_dashboard_question import generate_dashboard_question
        from src.api.backend_client import save_dashboard_question
        
        question = generate_dashboard_question(
            strategy_text=f"{strategy_text}\n\n{position_text}",
            analysis_dict=analysis_dict,
            asset_name=asset
        )
        
        logger.info(f"\n💡 GENERATED QUESTION:")
        logger.info(f"   {question}")
        save_dashboard_question(user_id, strategy_id, question)
        logger.info("✅ Question saved to backend")
    except Exception as e:
        logger.warning(f"⚠️  Failed to generate dashboard question: {e}")
    
    logger.info("="*80)
    logger.info("\n" + "="*80)
    logger.info("✅ STRATEGY ANALYSIS COMPLETE")
    logger.info("="*80)
    
    return {
        "topic_mapping": topic_mapping,
        "risk_assessment": risk_assessment,
        "opportunity_assessment": opportunity_assessment,
        "final_analysis": final_analysis
    }


# =============================================================================
# MAIN ENTRY POINT - Simple & Clean
# =============================================================================

def analyze_user_strategy(
    username: str,
    strategy_id: str
) -> Dict[str, Any]:
    """
    Analyze a user's strategy.
    
    Simple entry point - just provide username and strategy_id.
    Loads strategy, runs analysis, saves results.
    
    Args:
        username: User's username
        strategy_id: Strategy ID (e.g., "strategy_001")
    
    Returns:
        Dict with analysis results
    """
    logger.info("="*80)
    logger.info(f"STRATEGY ANALYSIS | {username}/{strategy_id}")
    logger.info("="*80)
    
    # Track start
    from src.observability.stats_client import track
    track("strategy_analysis_triggered", f"{username}/{strategy_id}")
    
    # 1. Load strategy from Backend API
    logger.info("Loading strategy from Backend API")
    strategy = get_strategy(username, strategy_id)
    
    if not strategy:
        raise ValueError(f"Strategy not found: {username}/{strategy_id}")
    
    logger.info(f"Strategy loaded | asset={strategy['asset']['primary']}")
    
    # 2. Extract inputs
    asset = strategy["asset"]["primary"]
    strategy_text = strategy["user_input"]["strategy_text"]
    position_text = strategy["user_input"]["position_text"]
    
    # 3. Run analysis pipeline
    results = run_strategy_analysis(
        user_id=username,
        strategy_id=strategy_id,
        asset=asset,
        strategy_text=strategy_text,
        position_text=position_text
    )
    
    logger.info("="*80)
    logger.info(f"✅ STRATEGY ANALYSIS COMPLETE | {username}/{strategy_id}")
    logger.info("="*80)
    
    # Track completion
    track("strategy_analysis_completed", f"{username}/{strategy_id}")
    
    return results


if __name__ == "__main__":
    # Load .env FIRST
    from utils.env_loader import load_env
    load_env()
    
    import sys
    
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        strategy_id = sys.argv[2]
        
        logger.info(f"Running strategy analysis for {username}/{strategy_id}")
        results = analyze_user_strategy(username, strategy_id)
        
        logger.info("\n" + "="*80)
        logger.info("RESULTS SUMMARY")
        logger.info("="*80)
        logger.info(f"Topics mapped: {len(results['topic_mapping'])}")
        logger.info(f"Risk level: {results['risk_assessment'].overall_risk_level}")
        logger.info(f"Opportunity level: {results['opportunity_assessment'].overall_opportunity_level}")
        logger.info("="*80)
    else:
        print("="*80)
        print("STRATEGY ANALYSIS ORCHESTRATOR")
        print("="*80)
        print("\nUsage:")
        print("  python -m src.strategy_agents.orchestrator <username> <strategy_id>")
        print("\nExample:")
        print("  python -m src.strategy_agents.orchestrator testuser strategy_001")
        print("="*80)
