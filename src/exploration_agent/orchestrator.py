"""
Exploration Agent - Orchestrator & Entry Point

Usage:
    # Explore a topic for risks
    python -m src.exploration_agent.orchestrator eurusd risk
    
    # Explore a topic for opportunities
    python -m src.exploration_agent.orchestrator eurusd opportunity
    
    # Explore a specific strategy (picks a starting topic from strategy mapping)
    python -m src.exploration_agent.orchestrator --strategy STRATEGY_ID risk

    # Explore a random strategy for a given user (auto-fetch from backend)
    python -m src.exploration_agent.orchestrator --random-strategy-user victor risk
    
    # Test mode with verbose output
    python -m src.exploration_agent.orchestrator eurusd risk --verbose
"""

import argparse
import sys
import json
import random
from typing import Optional

from src.exploration_agent.explorer.agent import ExplorationAgent
from src.exploration_agent.models import ExplorationMode, ExplorationResult
from src.exploration_agent.normalizer import normalize_confidence
from src.exploration_agent.final_critic.agent import FinalCriticAgent
from src.exploration_agent.final_critic.models import FinalCriticInput, FinalVerdict
from src.api.backend_client import get_user_strategies
from src.observability.stats_client import track
from utils import app_logging
from utils.env_loader import load_env

logger = app_logging.get_logger(__name__)

# Ensure environment variables (e.g., BACKEND_API_URL) are loaded once
load_env()


def fetch_random_strategy_for_user(username: str) -> Optional[str]:
    """Fetch a random strategy ID for the given user from the backend API."""
    strategies = get_user_strategies(username)
    if not strategies:
        logger.error("No strategies returned for user %s", username)
        return None
    valid = [s for s in strategies if s.get("id")]
    if not valid:
        logger.error("Strategies returned for user %s but none have IDs", username)
        return None
    chosen = random.choice(valid)
    strategy_id = chosen["id"]
    logger.info("🎲 Selected strategy %s for user %s", strategy_id, username)
    strategy_name = chosen.get("name") or chosen.get("title")
    if strategy_name:
        print(f"🎲 Selected strategy '{strategy_name}' ({strategy_id}) for user {username}")
    else:
        print(f"🎲 Selected strategy {strategy_id} for user {username}")
    return strategy_id


def explore_topic(
    topic_id: str,
    mode: str,
    max_steps: int = 20,
    skip_critic: bool = False,
) -> tuple[ExplorationResult, FinalVerdict | None]:
    """
    Run exploration for a topic, then validate with critic.
    If critic rejects, gives explorer ONE retry with feedback.

    Args:
        topic_id: Topic to explore for
        mode: "risk" or "opportunity"
        max_steps: Maximum exploration steps
        skip_critic: If True, skip critic validation

    Returns:
        (ExplorationResult, FinalVerdict or None)
    """
    # Track exploration start
    track("exploration_started", f"topic={topic_id} mode={mode}")

    # Phase 1: Explore
    agent = ExplorationAgent(max_steps=max_steps)
    exploration_mode = ExplorationMode(mode)
    result = agent.explore_topic(topic_id, exploration_mode)

    if not result.success or skip_critic:
        return result, None

    # Phase 2: Critic validation
    verdict = run_critic(result, mode, topic_id)

    # Phase 3: ONE retry if rejected
    if not verdict.accepted and result.success:
        logger.info("🔄 Critic rejected - giving explorer ONE retry with feedback")
        track("exploration_retry", f"topic={topic_id} mode={mode}")

        # Continue exploration with critic feedback (5 more steps)
        result = agent.continue_with_feedback(
            critic_feedback=verdict.reasoning,
            rejection_reasons=verdict.rejection_reasons,
            max_retry_steps=5
        )

        if result.success:
            # Re-run critic on revised finding
            verdict = run_critic(result, mode, topic_id)

    return result, verdict


def explore_strategy(
    strategy_user: str,
    strategy_id: str,
    mode: str,
    max_steps: int = 20,
    skip_critic: bool = False,
) -> tuple[ExplorationResult, FinalVerdict | None]:
    """
    Run exploration for a strategy, then validate with critic.
    If critic rejects, gives explorer ONE retry with feedback.

    Args:
        strategy_user: Username who owns the strategy
        strategy_id: Strategy to explore for
        mode: "risk" or "opportunity"
        max_steps: Maximum exploration steps
        skip_critic: If True, skip critic validation

    Returns:
        (ExplorationResult, FinalVerdict or None)
    """
    # Track exploration start
    track("exploration_started", f"strategy={strategy_id} user={strategy_user} mode={mode}")

    # Phase 1: Explore
    agent = ExplorationAgent(max_steps=max_steps)
    exploration_mode = ExplorationMode(mode)
    result = agent.explore_strategy(strategy_user, strategy_id, exploration_mode)

    if not result.success or skip_critic:
        return result, None

    # Phase 2: Critic validation (with strategy context for fetching/saving findings)
    verdict = run_critic(
        result, mode, result.target_topic_id,
        strategy_user=strategy_user, strategy_id=strategy_id
    )

    # Phase 3: ONE retry if rejected
    if not verdict.accepted and result.success:
        logger.info("🔄 Critic rejected - giving explorer ONE retry with feedback")
        track("exploration_retry", f"strategy={strategy_id} user={strategy_user} mode={mode}")

        # Continue exploration with critic feedback (5 more steps)
        result = agent.continue_with_feedback(
            critic_feedback=verdict.reasoning,
            rejection_reasons=verdict.rejection_reasons,
            max_retry_steps=5
        )

        if result.success:
            # Re-run critic on revised finding
            verdict = run_critic(
                result, mode, result.target_topic_id,
                strategy_user=strategy_user, strategy_id=strategy_id
            )

    return result, verdict


def run_critic(
    result: ExplorationResult,
    mode: str,
    target_topic: str,
    strategy_user: Optional[str] = None,
    strategy_id: Optional[str] = None,
) -> FinalVerdict:
    """
    Run critic validation on an exploration result.

    Gathers all source material and existing items, then evaluates.
    If strategy context is provided, fetches existing findings and saves accepted ones.

    Args:
        result: The exploration result to validate
        mode: "risk" or "opportunity"
        target_topic: The topic this finding is for
        strategy_user: Optional - username for fetching/saving findings
        strategy_id: Optional - strategy ID for fetching/saving findings
    """
    from src.exploration_agent.explorer.tools import get_topic_snapshot, ANALYSIS_SECTIONS
    from src.graph.ops.topic import get_topic_analysis_field
    from src.api.backend_client import get_strategy_findings, save_strategy_finding

    logger.info("")
    logger.info("=" * 80)
    logger.info("🎯 STARTING CRITIC EVALUATION")
    logger.info("=" * 80)

    # Gather articles cited in evidence
    articles = {}
    for exc in result.evidence:
        if exc.source_id.startswith("art_"):
            # Fetch full article text
            try:
                # Extract article ID (remove 'art_' prefix)
                article_id = exc.source_id[4:]
                # For now, use the excerpt as placeholder
                # TODO: Fetch full article from graph
                articles[exc.source_id] = exc.excerpt
            except Exception as e:
                logger.warning("Failed to fetch article %s: %s", exc.source_id, e)

    # Gather topic analyses from visited topics (target + saved_at_topic)
    topic_analyses = {}
    topic_ids_for_context = set([target_topic])
    topic_ids_for_context.update(
        exc.saved_at_topic for exc in result.evidence if exc.saved_at_topic
    )
    for topic_id in topic_ids_for_context:
        if not topic_id:
            continue
        sections = {}
        for section in ANALYSIS_SECTIONS:
            try:
                value = get_topic_analysis_field(topic_id, section)
            except Exception as e:
                logger.warning("Failed to fetch section %s.%s: %s", topic_id, section, e)
                continue
            if value:
                sections[section] = value
        # Always include executive summary via snapshot for context
        if "executive_summary" not in sections:
            try:
                snapshot = get_topic_snapshot(topic_id)
                if snapshot.executive_summary:
                    sections["executive_summary"] = snapshot.executive_summary
            except Exception as e:
                logger.warning("Failed to fetch snapshot executive_summary for %s: %s", topic_id, e)
        if sections:
            topic_analyses[topic_id] = sections

    # Get existing risks/opportunities for strategy (if strategy context provided)
    existing_items = []
    if strategy_user and strategy_id:
        existing_items = get_strategy_findings(strategy_user, strategy_id, mode)
        logger.info("📊 Fetched %d existing %s(s) for comparison", len(existing_items), mode)

    # Build critic input
    critic_input = FinalCriticInput(
        finding=result,
        articles=articles,
        topic_analyses=topic_analyses,
        existing_items=existing_items,
        mode=mode,
        target_topic=target_topic,
    )

    # Run final critic
    final_critic = FinalCriticAgent()
    verdict = final_critic.evaluate(critic_input)

    # Track exploration outcome
    if verdict.accepted:
        track("exploration_accepted", f"mode={mode} topic={target_topic}")
    else:
        track("exploration_rejected", f"mode={mode} topic={target_topic}")

    # Save accepted findings
    if verdict.accepted:
        # Normalize confidence for frontend compatibility (must be "high", "medium", or "low")
        normalized_conf = normalize_confidence(verdict.confidence)
        finding_data = {
            "headline": result.headline,
            "rationale": result.rationale,
            "flow_path": result.flow_path,
            "evidence": [e.model_dump() for e in result.evidence],
            "confidence": normalized_conf,
            "target_topic": target_topic,
            "exploration_steps": result.exploration_steps,
        }

        if strategy_user and strategy_id:
            # Save to strategy (backend API)
            success = save_strategy_finding(
                strategy_user, strategy_id, mode,
                finding_data,
                replaces=verdict.replaces
            )
            if success:
                logger.info("💾 Saved accepted %s to strategy %s/%s", mode, strategy_user, strategy_id)
                print(f"\n💾 SAVED: {mode} finding saved to strategy '{strategy_user}/{strategy_id}'")
            else:
                logger.warning("⚠️ Failed to save %s to strategy", mode)
                print(f"\n⚠️ FAILED: Could not save {mode} to strategy '{strategy_user}/{strategy_id}'")
        else:
            # Save to topic (Neo4j) - topic-only exploration
            from src.graph.ops.topic_findings import save_topic_finding
            success = save_topic_finding(
                target_topic, mode,
                finding_data,
                replaces=verdict.replaces
            )
            if success:
                logger.info("💾 Saved accepted %s to topic %s", mode, target_topic)
                print(f"\n💾 SAVED: {mode} finding saved to topic '{target_topic}' in Neo4j")
            else:
                logger.warning("⚠️ Failed to save %s to topic", mode)
                print(f"\n⚠️ FAILED: Could not save {mode} to topic '{target_topic}'")

    return verdict


def print_result(result: ExplorationResult) -> None:
    """Pretty print an exploration result."""
    print("\n" + "=" * 80)
    print("🔍 EXPLORATION RESULT")
    print("=" * 80)
    
    status = "✅ SUCCESS" if result.success else "❌ FAILED"
    print(f"\nStatus: {status}")
    print(f"Mode: {result.mode.value.upper()}")
    print(f"Target: {result.target_topic_id}")
    if result.target_strategy_id:
        print(f"Strategy: {result.target_strategy_id}")
    print(f"Steps: {result.exploration_steps}")
    
    if result.error:
        print(f"\n⚠️ Error: {result.error}")
    
    print("\n" + "-" * 80)
    print(f"📌 HEADLINE: {result.headline}")
    print("-" * 80)
    
    print(f"\n📝 RATIONALE:\n{result.rationale}")
    
    flow_display = result.flow_path or "(not set)"
    print(f"\n🔗 FLOW PATH:\n{flow_display}")
    
    if result.evidence:
        print(f"\n📚 EVIDENCE ({len(result.evidence)} items):")
        for i, evidence in enumerate(result.evidence, 1):
            print(f"  {i}. {evidence}")
    
    print("\n" + "=" * 80)
    print("🔚 END OF RESEARCH RUN LOGS")
    print("=" * 80)


def print_research_summary(result: ExplorationResult) -> None:
    """Provide a clean summary between research and critic phases."""
    print("\n" * 3 + "=" * 80)
    print("📚 RESEARCH SUMMARY (HANDOFF PACKAGE)")
    print("=" * 80)
    print(f"Headline: {result.headline}")
    print(f"Rationale: {result.rationale if result.rationale else '(none)'}")
    print(f"Flow Path: {result.flow_path if result.flow_path else '(none)'}")
    
    print("\nEvidence:")
    if result.evidence:
        for idx, evidence in enumerate(result.evidence, 1):
            excerpt = (evidence.excerpt or "").replace("\n", " ").strip()
            if len(excerpt) > 200:
                excerpt = excerpt[:197] + "..."
            why = evidence.why_relevant or ""
            print(f"  {idx}. [{evidence.source_id}] {excerpt}")
            if why:
                print(f"       ↳ Why: {why}")
            if evidence.saved_at_topic:
                print(f"       ↳ Topic: {evidence.saved_at_topic} (step {evidence.saved_at_step})")
    else:
        print("  (no evidence saved)")
    print("=" * 80)
    print("⬆️ END RESEARCH SUMMARY — CRITIC REVIEW NEXT")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Exploration Agent - Find unseen risks and opportunities"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Topic ID to explore (e.g., 'eurusd')"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["risk", "opportunity"],
        default="risk",
        help="What to hunt for: 'risk' or 'opportunity'"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        help="Strategy ID to explore for (instead of topic)"
    )
    parser.add_argument(
        "--strategy-user",
        type=str,
        help="Username owner of the strategy (required when using --strategy)"
    )
    parser.add_argument(
        "--random-strategy-user",
        type=str,
        help="User ID to pull a random strategy from backend"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=20,
        help="Maximum exploration steps (default: 20)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    parser.add_argument(
        "--skip-critic",
        action="store_true",
        help="Skip critic validation (exploration only)"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # Validate inputs
    if not args.target and not args.strategy and not args.random_strategy_user:
        print("Error: Must provide a topic ID, --strategy, or --random-strategy-user")
        parser.print_help()
        sys.exit(1)
    if args.strategy and not args.strategy_user:
        print("Error: --strategy-user is required when using --strategy")
        parser.print_help()
        sys.exit(1)
    
    # Run exploration
    try:
        if args.random_strategy_user:
            print(f"🔍 Exploring random strategy for user '{args.random_strategy_user}' ({args.mode}s)...")
            strategy_id = fetch_random_strategy_for_user(args.random_strategy_user)
            if not strategy_id:
                print("❌ No strategy available for user")
                sys.exit(1)
            result, verdict = explore_strategy(args.random_strategy_user, strategy_id, args.mode, args.max_steps, args.skip_critic)
        elif args.strategy:
            print(f"🔍 Exploring strategy '{args.strategy}' for {args.mode}s (user={args.strategy_user})...")
            result, verdict = explore_strategy(args.strategy_user, args.strategy, args.mode, args.max_steps, args.skip_critic)
        else:
            print(f"🔍 Exploring topic '{args.target}' for {args.mode}s...")
            result, verdict = explore_topic(args.target, args.mode, args.max_steps, args.skip_critic)
        
        # Output result
        if args.json:
            output = {
                "exploration": result.model_dump(),
                "verdict": verdict.__dict__ if verdict else None
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            print_result(result)
            print_research_summary(result)
            if verdict:
                print_verdict(verdict)
            
    except Exception as e:
        logger.error(f"Exploration failed: {e}", exc_info=True)
        print(f"\n❌ Exploration failed: {e}")
        sys.exit(1)


# =============================================================================
# TEST EXAMPLES
# =============================================================================

def print_verdict(verdict: FinalVerdict) -> None:
    """Pretty print a critic verdict."""
    print("\n" * 3 + "=" * 80)
    print("⚖️ GOD-TIER CRITIC FEEDBACK")
    print("=" * 80)
    
    if verdict.accepted:
        print(f"\n✅ ACCEPTED (confidence: {verdict.confidence:.2f})")
        if verdict.replaces:
            print(f"   📍 Replaces existing #{verdict.replaces}")
        else:
            print("   📍 Will be added as new")
    else:
        print(f"\n❌ REJECTED (confidence: {verdict.confidence:.2f})")
        print("\n⚠️ Rejection reasons:")
        for reason in verdict.rejection_reasons:
            print(f"   • {reason}")
    
    print(f"\n📝 Reasoning: {verdict.reasoning}")
    print("\n" + "=" * 80)


def test_eurusd_risk():
    """Test exploration for EURUSD risks."""
    print("\n" + "=" * 80)
    print("TEST: EURUSD Risk Exploration")
    print("=" * 80)
    
    result, verdict = explore_topic("eurusd", "risk", max_steps=10)
    print_result(result)
    if verdict:
        print_verdict(verdict)
    return result, verdict


def test_eurusd_opportunity():
    """Test exploration for EURUSD opportunities."""
    print("\n" + "=" * 80)
    print("TEST: EURUSD Opportunity Exploration")
    print("=" * 80)
    
    result, verdict = explore_topic("eurusd", "opportunity", max_steps=10)
    print_result(result)
    if verdict:
        print_verdict(verdict)
    return result, verdict


def test_random_strategy():
    """Test exploration for a random strategy."""
    import os
    import requests
    
    print("\n" + "=" * 80)
    print("TEST: Random Strategy Risk Exploration")
    print("=" * 80)
    
    # Get strategies for user 'victor'
    backend_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
    api_key = os.getenv("BACKEND_API_KEY", "")
    
    try:
        headers = {"X-API-Key": api_key} if api_key else {}
        response = requests.get(
            f"{backend_url}/api/strategies/victor",
            headers=headers,
            timeout=10
        )
        
        if response.ok:
            strategies = response.json()
            if strategies:
                import random
                strategy = random.choice(strategies)
                strategy_id = strategy.get("id")
                print(f"Selected strategy: {strategy_id}")
                
                result, verdict = explore_strategy(strategy_id, "risk", max_steps=10)
                print_result(result)
                if verdict:
                    print_verdict(verdict)
                return result, verdict
            else:
                print("No strategies found for user 'victor'")
        else:
            print(f"Failed to fetch strategies: {response.status_code}")
            
    except Exception as e:
        print(f"Failed to fetch strategies: {e}")
    
    return None


if __name__ == "__main__":
    # If no args, run test
    if len(sys.argv) == 1:
        print("No arguments provided. Running test exploration...")
        print("\nUsage: python -m src.exploration_agent.orchestrator <topic_id> <risk|opportunity>")
        print("       python -m src.exploration_agent.orchestrator --strategy <strategy_id> <risk|opportunity>")
        print("\nRunning test with 'eurusd' and 'risk'...\n")
        test_eurusd_risk()
    else:
        main()
