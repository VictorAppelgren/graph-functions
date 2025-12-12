"""
Strategy Analysis Orchestrator

Chains all strategy agents together.

Usage:
    python -m src.strategy_agents.orchestrator username strategy_id
    python -m src.strategy_agents.orchestrator Victor 
    python -m src.strategy_agents.orchestrator all
"""

import random
from typing import Dict, Any, Optional
from utils import app_logging

from src.strategy_agents.topic_mapper import TopicMapperAgent
from src.strategy_agents.risk_assessor import RiskAssessorAgent
from src.strategy_agents.opportunity_finder import OpportunityFinderAgent
from src.strategy_agents.strategy_writer import StrategyWriterAgent
from src.strategy_agents.material_builder import build_material_package
from src.api.backend_client import (
    get_strategy,
    get_all_users,
    get_user_strategies,
    save_strategy_topics,
    save_strategy_analysis,
)

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
    position_text: str,
    save_to_backend: bool = True,
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
    
    # Check if user has active position or just monitoring (canonical boolean)
    has_position = bool(position_text and position_text.strip())
    if has_position:
        logger.info(f"Position: {position_text[:100]}..." if len(position_text) > 100 else f"Position: {position_text}")
        logger.info("📊 Mode: ACTIVE POSITION ANALYSIS")
    else:
        logger.info("Position: None (monitoring/outlook mode)")
        logger.info("📊 Mode: THESIS MONITORING (no active position)")
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
    
    # Save topic mapping to backend (optional)
    if save_to_backend:
        logger.info("\n💾 Saving topic mapping to backend...")
        topics_ok = save_strategy_topics(
            username=user_id,
            strategy_id=strategy_id,
            topics=topic_mapping,
        )
        if topics_ok:
            logger.info("✅ Topic mapping saved to backend")
        else:
            logger.warning("⚠️ Failed to save topic mapping to backend (see backend_client logs)")
    else:
        logger.info("\n💾 Skipping topic mapping save (save_to_backend=False)")
    
    # Step 2: Build complete material package (includes has_position flag)
    logger.info("\n" + "="*80)
    logger.info("STEP 2: BUILD MATERIAL PACKAGE")
    logger.info("="*80)
    material_package = build_material_package(
        user_strategy=strategy_text,
        position_text=position_text,
        topic_mapping=topic_mapping,
        has_position=has_position,
    )
    
    # Preview material package
    logger.info("\n📦 MATERIAL PACKAGE:")
    logger.info(f"   Strategy: {len(strategy_text)} chars")
    logger.info(f"   Position: {len(position_text)} chars")
    topic_analyses_str = material_package.get('topic_analyses', '')
    market_context_str = material_package.get('market_context', '')
    logger.info(f"   Topic Analyses (combined): {len(topic_analyses_str)} chars")
    logger.info(f"   Market Context (combined): {len(market_context_str)} chars")
    total_chars = len(strategy_text) + len(position_text) + len(topic_analyses_str) + len(market_context_str)
    logger.info(f"   TOTAL INPUT TO RISK/OPP/WRITER: {total_chars:,} chars (~{total_chars//1000}K)")
    logger.info(f"   has_position flag in material_package: {material_package.get('has_position')}")
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
    logger.info(f"   Scenarios & Catalysts: {len(final_analysis.scenarios_and_catalysts)} chars")
    logger.info(f"   Structuring & Risk Mgmt: {len(final_analysis.structuring_and_risk_management)} chars")
    logger.info(f"   Context & Alignment: {len(final_analysis.context_and_alignment)} chars")
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
        "final_analysis": final_analysis.model_dump(),
    }
    if save_to_backend:
        analysis_ok = save_strategy_analysis(
            username=user_id,
            strategy_id=strategy_id,
            analysis=analysis_dict,
        )
        if analysis_ok:
            logger.info("✅ Analysis saved to backend")
        else:
            logger.warning("⚠️ Failed to save analysis to backend (see backend_client logs)")
    else:
        logger.info("Skipping analysis save (save_to_backend=False)")
    logger.info("="*80)
    
    # Step 7: Generate dashboard question (only when saving to backend)
    if save_to_backend:
        logger.info("\n" + "="*80)
        logger.info("STEP 7: GENERATE DASHBOARD QUESTION")
        logger.info("="*80)
        try:
            from src.llm.prompts.generate_dashboard_question import generate_dashboard_question
            from src.api.backend_client import save_dashboard_question
            
            question = generate_dashboard_question(
                strategy_text=f"{strategy_text}\n\n{position_text}",
                analysis_dict=analysis_dict,
                asset_name=asset,
            )
            
            logger.info(f"\n💡 GENERATED QUESTION:")
            logger.info(f"   {question}")
            question_ok = save_dashboard_question(user_id, strategy_id, question)
            if question_ok:
                logger.info("✅ Question saved to backend")
            else:
                logger.warning("⚠️ Failed to save dashboard question to backend (see backend_client logs)")
        except Exception as e:
            logger.warning(f"⚠️  Failed to generate dashboard question: {e}")
    else:
        logger.info("\n" + "="*80)
        logger.info("STEP 7: GENERATE DASHBOARD QUESTION (SKIPPED - save_to_backend=False)")
        logger.info("="*80)
    
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
    
    # For default strategies, only the owner should trigger analysis; copies are updated via backend
    owner = strategy.get("owner_username", username)
    if strategy.get("is_default", False) and owner != username:
        logger.info(f"Skipping default copy {username}/{strategy_id} (owner={owner})")
        return {}

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


def analyze_all_user_strategies() -> None:
    """Analyze all strategies for all users via Backend API."""
    logger.info("=" * 80)
    logger.info("BULK STRATEGY ANALYSIS | ALL USERS / ALL STRATEGIES")
    logger.info("=" * 80)

    users = get_all_users()
    logger.info(f"Found {len(users)} users")

    for username in users:
        strategies = get_user_strategies(username)
        logger.info(f"User {username}: {len(strategies)} strategies")

        for s in strategies:
            strategy_id = s.get("id")
            if not strategy_id:
                continue

            try:
                logger.info("-" * 80)
                logger.info(f"Running analysis for {username}/{strategy_id}")
                analyze_user_strategy(username, strategy_id)
            except Exception as e:
                logger.warning(f"⚠️  Failed analysis for {username}/{strategy_id}: {e}")


def _run_topic_discovery(strategy: Dict, strategy_text: str, position_text: str) -> Dict:
    """Run TopicMapperAgent to discover topics for a strategy."""
    mapper = TopicMapperAgent()
    return mapper.run(
        asset_text=strategy["asset"]["primary"],
        strategy_text=strategy_text,
        position_text=position_text
    )


def rewrite_single_section(
    username: str,
    strategy_id: str,
    section: str,
    feedback: str,
    current_content: str,
) -> str:
    """
    Rewrite a single section of strategy analysis based on user feedback.
    
    Args:
        username: User's username
        strategy_id: Strategy ID
        section: Section key (e.g., "risk_analysis")
        feedback: User's feedback/instructions
        current_content: Existing section content
    
    Returns:
        Rewritten section content
    """
    logger.info("="*80)
    logger.info(f"🔄 SECTION REWRITE | {username}/{strategy_id} | {section}")
    logger.info("="*80)
    logger.info(f"Feedback: {feedback[:200]}...")
    
    # 1. Load strategy from Backend API
    strategy = get_strategy(username, strategy_id)
    if not strategy:
        raise ValueError(f"Strategy not found: {username}/{strategy_id}")
    
    # Extract strategy text early (needed for topic remapping)
    strategy_text = strategy["user_input"]["strategy_text"]
    position_text = strategy["user_input"]["position_text"]
    
    # 2. Validate topic mapping - re-run if empty or any invalid IDs
    topic_mapping = strategy.get("topics", {})
    primary_ids = topic_mapping.get("primary", [])
    
    if not primary_ids:
        logger.info("No topics found - running topic discovery")
        topic_mapping = _run_topic_discovery(strategy, strategy_text, position_text)
        save_strategy_topics(username, strategy_id, topic_mapping)
    else:
        # Check all topic IDs exist in Neo4j
        from src.graph.ops.topic import check_if_topic_exists
        invalid = [tid for tid in primary_ids if not check_if_topic_exists(tid)]
        if invalid:
            logger.warning(f"⚠️ Invalid topic IDs: {invalid} - re-running discovery")
            topic_mapping = _run_topic_discovery(strategy, strategy_text, position_text)
            save_strategy_topics(username, strategy_id, topic_mapping)
    
    # 3. Build material package
    has_position = bool(position_text and position_text.strip())
    
    material_package = build_material_package(
        user_strategy=strategy_text,
        position_text=position_text,
        topic_mapping=topic_mapping,
        has_position=has_position,
    )
    
    # Check if we have any topic material (rewrite can still work without it)
    if not material_package.get("topics"):
        logger.warning("⚠️  No valid topics found - rewrite will use feedback and current content only")
    
    # 4. Rewrite the section
    writer = StrategyWriterAgent()
    new_content = writer.rewrite_section(
        section=section,
        current_content=current_content,
        feedback=feedback,
        material_package=material_package,
    )
    
    # 5. Save updated section to backend
    # Get current analysis, update the section, save back
    current_analysis = strategy.get("latest_analysis", {})
    if current_analysis and "final_analysis" in current_analysis:
        current_analysis["final_analysis"][section] = new_content
        save_strategy_analysis(username, strategy_id, current_analysis)
        logger.info(f"✅ Saved updated {section} to backend")
    else:
        logger.warning(f"⚠️ No existing analysis to update for {username}/{strategy_id}")
    
    logger.info("="*80)
    logger.info(f"✅ SECTION REWRITE COMPLETE | {section} | {len(new_content)} chars")
    logger.info("="*80)
    
    return new_content


if __name__ == "__main__":
    # Load .env FIRST
    from utils.env_loader import load_env
    load_env()
    
    import sys
    
    if len(sys.argv) >= 2 and sys.argv[1] == "all":
        analyze_all_user_strategies()
    elif len(sys.argv) >= 2:
        username = sys.argv[1]
        if len(sys.argv) >= 3:
            strategy_id = sys.argv[2]
        else:
            strategies = get_user_strategies(username)
            if not strategies:
                raise ValueError(f"No strategies found for user: {username}")
            chosen_strategy = random.choice(strategies)
            strategy_id = chosen_strategy.get("id")
            if not strategy_id:
                raise ValueError(f"Randomly selected strategy missing ID for user: {username}")
            logger.info(
                f"Randomly selected strategy '{strategy_id}' for user {username}"
            )

        logger.info(f"Running strategy analysis for {username}/{strategy_id}")
        results = analyze_user_strategy(username, strategy_id)

        logger.info("\n" + "=" * 80)
        logger.info("RESULTS SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Topics mapped: {len(results['topic_mapping'])}")
        logger.info(f"Risk level: {results['risk_assessment'].overall_risk_level}")
        logger.info(f"Opportunity level: {results['opportunity_assessment'].overall_opportunity_level}")
        logger.info("=" * 80)
    else:
        print("=" * 80)
        print("STRATEGY ANALYSIS ORCHESTRATOR")
        print("=" * 80)
        print("\nUsage:")
        print("  python -m src.strategy_agents.orchestrator <username> <strategy_id>")
        print("  python -m src.strategy_agents.orchestrator <username>  # picks random strategy")
        print("  python -m src.strategy_agents.orchestrator all")
        print("\nExample:")
        print("  python -m src.strategy_agents.orchestrator testuser strategy_001")
        print("  python -m src.strategy_agents.orchestrator all")
        print("=" * 80)
