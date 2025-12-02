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
    logger.info(f"Running strategy analysis | user={user_id} strategy={strategy_id}")
    
    # Step 1: Map topics (always run - topics may change)
    logger.info("Mapping strategy to topics")
    mapper = TopicMapperAgent()
    topic_mapping = mapper.run(
        asset_text=asset,
        strategy_text=strategy_text,
        position_text=position_text
    )
    
    # Save topic mapping to backend (optional - won't crash if backend unavailable)
    try:
        logger.info("Saving topic mapping to backend")
        save_strategy_topics(
            username=user_id,
            strategy_id=strategy_id,
            topics=topic_mapping
        )
    except Exception as e:
        logger.warning(f"Failed to save topics to backend: {e}")
    
    # Step 2: Build complete material package
    logger.info("Building material package")
    material_package = build_material_package(
        user_strategy=strategy_text,
        position_text=position_text,
        topic_mapping=topic_mapping
    )
    
    # Step 3: Assess risks
    logger.info("Assessing risks")
    risk_assessor = RiskAssessorAgent()
    risk_assessment = risk_assessor.run(material_package)
    
    # Step 4: Find opportunities
    logger.info("Finding opportunities")
    opportunity_finder = OpportunityFinderAgent()
    opportunity_assessment = opportunity_finder.run(material_package)
    
    # Step 5: Write final analysis
    logger.info("Writing final analysis")
    writer = StrategyWriterAgent()
    final_analysis = writer.run(
        material_package=material_package,
        risk_assessment=risk_assessment,
        opportunity_assessment=opportunity_assessment
    )
    
    # Step 6: Save analysis to backend (optional - won't crash if backend unavailable)
    try:
        logger.info("Saving analysis to backend")
        save_strategy_analysis(
            username=user_id,
            strategy_id=strategy_id,
            analysis={
                "risk_level": risk_assessment.overall_risk_level,
                "opportunity_level": opportunity_assessment.overall_opportunity_level,
                "risk_assessment": risk_assessment.dict(),
                "opportunity_assessment": opportunity_assessment.dict(),
                "final_analysis": final_analysis.dict()
            }
        )
    except Exception as e:
        logger.warning(f"Failed to save analysis to backend: {e}")
    
    logger.info("Strategy analysis complete")
    
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
    strategy_id: str,
    test: bool = False
) -> Dict[str, Any]:
    """
    Analyze a user's strategy.
    
    Simple entry point - just provide username and strategy_id.
    Loads strategy, runs analysis, saves results.
    
    Args:
        username: User's username
        strategy_id: Strategy ID (e.g., "strategy_001")
        test: If True, use test mode (currently unused, for future)
    
    Returns:
        Dict with analysis results
    """
    logger.info("="*80)
    logger.info(f"STRATEGY ANALYSIS | {username}/{strategy_id}")
    logger.info("="*80)
    
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
    
    return results


if __name__ == "__main__":
    # Load .env FIRST
    from utils.env_loader import load_env
    load_env()
    
    import sys
    
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        strategy_id = sys.argv[2]
        
        logger.info(f"Testing strategy analysis for {username}/{strategy_id}")
        results = analyze_user_strategy(username, strategy_id, test=True)
        
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
