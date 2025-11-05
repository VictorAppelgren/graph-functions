"""
Orchestrator: loops over all analysis sections for a topic, calls rewrite_analysis_llm for each, formats and saves results.
No prompt logic here.
"""

from typing import Optional, Dict, List, Set, Any
from dataclasses import dataclass
from src.analysis.writing.analysis_rewriter import rewrite_analysis_llm
from src.analysis.persistance.analysis_saver import save_analysis
from src.analysis.utils.driver_aggregator import aggregate_driver_analyses
from src.analysis.material.article_material import build_material_for_synthesis_section
from utils import app_logging
from src.observability.pipeline_logging import (
    master_log,
    problem_log,
    ProblemDetailsModel,
    Problem,
)
from src.graph.neo4j_client import run_cypher
from src.graph.ops.topic import get_topic_analysis_field
from src.market_data.neo4j_updater import load_market_data_from_neo4j
from src.market_data.formatter import format_market_data_display
from src.market_data.models import MarketSnapshot, AssetClass
from datetime import date
import time

logger = app_logging.get_logger(__name__)

MIN_ARTICLES_FOR_SECTION = 1  # Minimum articles required to attempt analysis
IDEAL_ARTICLES_FOR_SECTION = 5  # Trigger enrichment if below this threshold

SECTION_FOCUS = {
    "fundamental": (
        "HORIZON: Multi-year structural analysis (6+ months). "
        "CONTENT: Derive first-principles anchors for primary asset through perspective synthesis. "
        "**SYNERGY MANDATE: What do risk articles + opportunity articles + trend articles reveal TOGETHER? "
        "Build causal chains showing how structural risks create opportunities, how trends amplify catalysts. "
        "1+1=3 synthesis: combine perspectives to generate insights impossible from single-perspective view.** "
        "FORMAT: 2-3 authoritative paragraphs, maximum insight density. "
        "STRUCTURE: Base case (first principles) → Risk transmission → Opportunity mechanisms → "
        "Trend durability → Catalyst triggers → Synthesis (what X+Y means for asset). "
        "**PERSPECTIVE INTEGRATION: Balance risks/opportunities/trends based on article scores. "
        "Ask: 'What does THIS risk combined with THAT opportunity mean for asset performance?'** "
        "CITATIONS: Only 9-character IDs (ABC123DEF). "
        "FOCUS: Primary asset performance through multi-perspective lens. "
        "AUTHORITY: Conviction-based, zero hedging, surgical precision."
    ),
    "medium": (
        "HORIZON: 3-6 months tactical scenario analysis. "
        "CONTENT: Build integrated scenario map for primary asset across all perspectives. "
        "**SYNERGY MANDATE: Synthesize risk scenarios + opportunity scenarios + trend shifts + upcoming catalysts. "
        "Map causal chains: How does risk A interact with opportunity B? What triggers trend C? "
        "Compound scenarios: Risk materializes → creates opportunity → accelerates trend → triggers catalyst.** "
        "FORMAT: 2-3 compact paragraphs, scenario-focused. "
        "STRUCTURE: Scenario matrix (bull/bear/base) → Risk paths → Opportunity paths → "
        "Trend inflections → Catalyst timing → Cross-scenario synthesis. "
        "**PERSPECTIVE BALANCE: Emphasize risk/opportunity interplay, note trend context, flag catalysts. "
        "Ask: 'If risk X happens AND opportunity Y emerges, what's the net asset impact?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset tactical positioning through scenario synthesis. "
        "AUTHORITY: Decisive, probability-weighted, actionable."
    ),
    "current": (
        "HORIZON: 0-3 weeks immediate intelligence. "
        "CONTENT: Synthesize immediate drivers across all perspectives for primary asset. "
        "**SYNERGY MANDATE: Combine near-term risks + immediate opportunities + trend shifts + active catalysts. "
        "Real-time synthesis: What are markets missing? Where do perspectives conflict/reinforce? "
        "Contrarian edge: If everyone sees risk, where's the hidden opportunity? If consensus is bullish, what's the tail risk?** "
        "FORMAT: 1-2 paragraphs, urgent tone, maximum density. "
        "STRUCTURE: Immediate drivers (by perspective) → Catalyst triggers → Risk/opportunity interplay → "
        "Trend context → Positioning implications → Next 72-hour monitors. "
        "**PERSPECTIVE BALANCE: Lead with catalysts, integrate risks/opportunities, note trend context. "
        "Ask: 'What does catalyst X + risk Y + opportunity Z mean for asset RIGHT NOW?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset immediate price action through multi-perspective synthesis. "
        "AUTHORITY: Urgent, conviction-driven, trade-ready. "
        "MANDATORY: Always generate - core real-time intelligence function."
    ),
    "drivers": (
        "HORIZON: Cross-topic, cross-perspective synthesis. "
        "CONTENT: Synthesize material drivers affecting primary asset across ALL perspectives. "
        "**FIRST-PRINCIPLES DRIVER SYNTHESIS: Build causal chains from root drivers to asset impact. "
        "Multi-perspective integration: Organize by perspective (risk drivers, opportunity drivers, trend drivers, catalyst drivers). "
        "Synergy detection: Which drivers reinforce? Which offset? What's the net vector? "
        "Transmission mechanisms: Map explicit paths from driver → intermediate variables → asset performance.** "
        "FORMAT: Concise synthesis, maximum insight density, shortest possible text. "
        "STRUCTURE: Key drivers (by perspective) → Causal chains → Transmission paths → "
        "Synergies/offsets → Net assessment → Watch signals. "
        "**PERSPECTIVE INTEGRATION: Group drivers by risk/opportunity/trend/catalyst, show interactions.** "
        "**SYNERGY QUESTION: 'What do risk drivers + opportunity drivers + trend drivers reveal TOGETHER?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset impact through integrated driver framework. "
        "AUTHORITY: Surgical precision, causal clarity, maximum density."
    ),
    "executive_summary": (
        "HORIZON: Integrated house view across all timeframes and perspectives. "
        "CONTENT: Synthesize fundamental + medium + current analysis across all 4 perspectives into unified view. "
        "**FIRST-PRINCIPLES HOUSE VIEW: Build conviction from ground truth, not consensus. "
        "Multi-perspective synthesis: Balance key risks + top opportunities + structural trends + immediate catalysts. "
        "Synergy intelligence: What does the COMBINATION of perspectives reveal? Where do they reinforce/conflict? "
        "Contrarian edge: Where is consensus wrong? What's the market missing? What's the asymmetric bet?** "
        "FORMAT: Executive brief, authoritative tone, decision-ready. "
        "STRUCTURE: House view (conviction call) → Fundamental anchor → Medium-term scenarios → "
        "Current drivers → Key risks → Top opportunities → Structural trends → Immediate catalysts → "
        "Net assessment → Positioning → Watch items. "
        "**PERSPECTIVE INTEGRATION: Balance all 4 perspectives, show how they interact to form house view.** "
        "**SYNERGY QUESTION: 'What does the TOTALITY of perspectives reveal about asset trajectory?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset performance through complete perspective synthesis. "
        "AUTHORITY: Maximum conviction, zero hedging, trade-executable, world-class."
    ),
    "movers_scenarios": (
        "HORIZON: Forward-looking scenarios for primary asset. "
        "CONTENT: Exactly 4 scenarios (2 Up, 2 Down) that could move the primary asset. "
        "FORMAT: Simple text lines, NO tables, NO formatting. Each line: Up/Down | Time window | Driver/Mechanism | What to watch | Probability %. "
        "STRUCTURE: Concrete triggers and probabilities based on evidence. "
        "CITATIONS: Only 9-character IDs for specific facts. FOCUS: All scenarios about primary asset movement only."
    ),
    "swing_trade_or_outlook": (
        "HORIZON: Actionable trading/investment view for primary asset. "
        "CONTENT: 1) Scenarios: 4 lines (2 Up, 2 Down) for primary asset. 2) Trade/Outlook: Specific directional view with levels. "
        "FORMAT: Simple text lines, NO tables, NO formatting. Consistent line structure throughout. "
        "SCENARIOS: Up/Down | Time window | Driver/Mechanism | What to watch | Probability %. "
        "TRADE: Direction | Horizon | Entry | Stop | Target | R/R | Invalidation | Trigger | Probability % | Confidence. "
        "OUTLOOK: Direction | Horizon | Expected path/levels | Decision signals | Invalidation | Trigger | Probability % | Confidence. "
        "CITATIONS: Only 9-character IDs for specific facts. FOCUS: All analysis about primary asset performance only."
    ),
    "risk_analysis": (
        "HORIZON: Cross-timeframe risk synthesis (fundamental + medium + current risks). "
        "CONTENT: Synthesize ALL downside scenarios, threats, vulnerabilities for primary asset. "
        "**FIRST-PRINCIPLES RISK SYNTHESIS: Build causal chains from root causes to asset impact. "
        "Multi-article integration: What does risk A + risk B reveal about systemic vulnerability? "
        "Transmission mechanisms: How does geopolitical risk → policy risk → market risk → asset impact? "
        "Probability trees: Which risks are independent? Which compound? What's the tail scenario?** "
        "FORMAT: 2-3 authoritative paragraphs, risk-focused intelligence. "
        "STRUCTURE: Critical risks (by timeframe) → Causal chains → Transmission paths → "
        "Probability/magnitude assessment → Compounding scenarios → Mitigation/hedges → Watch signals. "
        "**ARTICLE SELECTION: Use ONLY articles with importance_risk ≥ 2.** "
        "**SYNERGY QUESTION: 'What do these risk articles reveal TOGETHER that none show alone?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset downside through integrated risk framework. "
        "AUTHORITY: Unflinching, probability-weighted, defensible."
    ),
    "opportunity_analysis": (
        "HORIZON: Cross-timeframe opportunity synthesis (structural + tactical + immediate). "
        "CONTENT: Synthesize ALL upside scenarios, catalysts, bullish drivers for primary asset. "
        "**FIRST-PRINCIPLES OPPORTUNITY SYNTHESIS: Build causal chains from catalyst to asset upside. "
        "Multi-article integration: What does opportunity A + opportunity B reveal about asymmetric upside? "
        "Transmission mechanisms: How does policy shift → liquidity flow → positioning change → asset rally? "
        "Conviction framework: Which opportunities are high-probability? Which are high-magnitude? Which are both?** "
        "FORMAT: 2-3 authoritative paragraphs, opportunity-focused intelligence. "
        "STRUCTURE: Key opportunities (by timeframe) → Causal chains → Transmission paths → "
        "Probability/magnitude assessment → Compounding scenarios → Catalyst timing → Entry points → Watch signals. "
        "**ARTICLE SELECTION: Use ONLY articles with importance_opportunity ≥ 2.** "
        "**SYNERGY QUESTION: 'What do these opportunity articles reveal TOGETHER about asymmetric upside?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset upside through integrated opportunity framework. "
        "AUTHORITY: Conviction-driven, magnitude-focused, trade-ready."
    ),
    "trend_analysis": (
        "HORIZON: Structural trend synthesis (secular shifts, regime changes). "
        "CONTENT: Synthesize secular/structural shifts affecting primary asset across all timeframes. "
        "**FIRST-PRINCIPLES TREND SYNTHESIS: Identify regime changes from first principles. "
        "Multi-article integration: What do trend A + trend B reveal about structural transformation? "
        "Durability assessment: Is this cyclical noise or secular shift? What's the half-life? "
        "Inflection detection: Are we at trend start, middle, or exhaustion? What signals reversal?** "
        "FORMAT: 2 paragraphs, trend-focused intelligence. "
        "STRUCTURE: Structural shifts (identify) → First-principles drivers → Durability evidence → "
        "Asset transmission → Inflection signals → Positioning implications → Reversal monitors. "
        "**ARTICLE SELECTION: Use ONLY articles with importance_trend ≥ 2.** "
        "**SYNERGY QUESTION: 'What do these trend articles reveal TOGETHER about regime change?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset structural drivers through integrated trend framework. "
        "AUTHORITY: Secular conviction, regime-aware, contrarian when warranted."
    ),
    "catalyst_analysis": (
        "HORIZON: Immediate catalyst synthesis (0-7 days, forcing functions). "
        "CONTENT: Synthesize immediate triggers forcing price action in primary asset RIGHT NOW. "
        "**FIRST-PRINCIPLES CATALYST SYNTHESIS: Identify forcing functions from first principles. "
        "Multi-article integration: What do catalyst A + catalyst B reveal about immediate pressure? "
        "Timing precision: Which catalysts are hours away? Days? Which are certain vs. probabilistic? "
        "Market positioning: Is catalyst priced? Ignored? Misunderstood? Where's the edge?** "
        "FORMAT: 1-2 paragraphs, urgent catalyst intelligence. "
        "STRUCTURE: Immediate catalysts (by timing) → Forcing mechanisms → Market positioning → "
        "Expected impact → Contrarian angles → Next 24-48h triggers → Real-time monitors. "
        "**ARTICLE SELECTION: Use ONLY articles with importance_catalyst ≥ 2.** "
        "**SYNERGY QUESTION: 'What do these catalyst articles reveal TOGETHER about immediate forcing functions?'** "
        "CITATIONS: Only 9-character IDs. "
        "FOCUS: Primary asset immediate action through integrated catalyst framework. "
        "AUTHORITY: Urgent, timing-precise, trade-executable."
    ),
}

SECTIONS = [
    # Timeframe sections (perspective-balanced)
    "fundamental",
    "medium",
    "current",
    
    # Synthesis sections (perspective-aware)
    "drivers",
    "movers_scenarios",
    "swing_trade_or_outlook",
    "executive_summary",
    
    # NEW: Perspective-focused sections
    "risk_analysis",
    "opportunity_analysis",
    "trend_analysis",
    "catalyst_analysis",
]

# =============================================================================
# DEPENDENCY-AWARE ANALYSIS SYSTEM
# =============================================================================

@dataclass
class SectionUpdate:
    """Represents a section that needs to be updated and why."""
    section: str
    reason: str  # "missing_text", "dependency_updated", "new_articles"
    triggered_by: str  # Which section/event triggered this update

# Dependency mapping - defines which sections depend on which other sections
# This creates a cascading update system where changes flow through the dependency chain
#
# FLOW LOGIC:
# 1. CORE SECTIONS (fundamental, medium, current) are independent base analysis
#    - These contain the raw research and first-principles thinking
#    - Updated when new articles arrive or existing analysis needs refresh
#
# 2. DRIVERS section synthesizes cross-topic influences from all core sections
#    - Depends on: fundamental, medium, current
#    - Updated when ANY core section changes (macro themes span all timeframes)
#
# 3. FORWARD-LOOKING SECTIONS (movers_scenarios, swing_trade_or_outlook) predict future
#    - Depend on: fundamental (structural drivers), medium (catalyst map), current (immediate triggers), drivers (cross-topic influences)
#    - These answer "what could move it" and "where it could move"
#    - Updated when core analysis or drivers change
#
# 4. EXECUTIVE SUMMARY synthesizes everything into decision-useful brief
#    - Depends on: ALL other sections
#    - Always updated last to reflect the complete, current view
#
# CASCADING EXAMPLE:
# New current article → current section updated → movers_scenarios updated → executive_summary updated
# New fundamental article → fundamental updated → drivers updated → movers_scenarios + swing_trade_or_outlook updated → executive_summary updated
SECTION_DEPENDENCIES: Dict[str, List[str]] = {
    # Core sections - independent, contain base research
    "fundamental": [],  # Multi-year structural analysis
    "medium": [],       # 3-6 month scenario/catalyst mapping  
    "current": [],      # 0-3 week immediate drivers
    
    # Synthesis section - depends on all core timeframes
    "drivers": ["fundamental", "medium", "current"],  # Cross-topic macro influences
    
    # Forward-looking sections - depend on core + drivers for predictions
    "movers_scenarios": ["fundamental", "medium", "current", "drivers"],      # "What could move it"
    "swing_trade_or_outlook": ["fundamental", "medium", "current", "drivers"], # "Where it could move"
    
    # Executive summary - depends on everything for complete synthesis
    "executive_summary": ["fundamental", "medium", "current", "drivers", 
                         "movers_scenarios", "swing_trade_or_outlook"]
}

# Execution order - topological sort ensuring dependencies are updated before dependents
# This order guarantees that when we update a section, all its dependencies are already current
EXECUTION_ORDER: List[str] = [
    # Phase 1: Core sections (can run in parallel - no interdependencies)
    "fundamental", "medium", "current",
    
    # Phase 2: Cross-topic synthesis (depends on all core sections)
    "drivers",
    
    # Phase 3: Forward-looking analysis (depends on core + drivers, can run in parallel)
    "movers_scenarios", "swing_trade_or_outlook",
    
    # Phase 4: Executive synthesis (depends on everything, runs last)
    "executive_summary"
]


def get_all_analysis_sections(topic_id: str) -> Dict[str, str]:
    """
    Get ALL analysis sections for a topic. Fail fast if topic not found.
    
    Returns a dictionary with all analysis fields, using the database field names:
    - fundamental_analysis, medium_analysis, current_analysis (core timeframe sections)
    - drivers, executive_summary, movers_scenarios, swing_trade_or_outlook (derived sections)
    - name (topic name for context)
    
    Raises ValueError if topic doesn't exist.
    """
    query = """
    MATCH (t:Topic {id: $topic_id})
    RETURN t.fundamental_analysis as fundamental_analysis,
           t.medium_analysis as medium_analysis, 
           t.current_analysis as current_analysis,
           t.drivers as drivers,
           t.executive_summary as executive_summary,
           t.movers_scenarios as movers_scenarios,
           t.swing_trade_or_outlook as swing_trade_or_outlook,
           t.risk_analysis as risk_analysis,
           t.opportunity_analysis as opportunity_analysis,
           t.trend_analysis as trend_analysis,
           t.catalyst_analysis as catalyst_analysis,
           t.name as name
    """
    result = run_cypher(query, {"topic_id": topic_id})
    if not result:
        raise ValueError(f"Topic {topic_id} not found")
    
    return result[0]


def determine_sections_to_update(
    existing_sections: Dict[str, str], 
    trigger_section: str,
    updated_sections: Set[str] = None
) -> List[SectionUpdate]:
    """
    Determine which sections need updating based on dependency cascade.
    
    Logic:
    1. Always update if section text is missing/empty
    2. Update if any dependency was updated in this cascade
    3. For core sections triggered by new articles, use existing should_rewrite_llm logic
    
    Args:
        existing_sections: Current analysis sections from database
        trigger_section: Which section triggered this update ("fundamental", "medium", "current")
        updated_sections: Set of sections already updated in this cascade
    
    Returns:
        List of SectionUpdate objects in execution order
        
    Fails fast - no fallbacks.
    """
    if updated_sections is None:
        updated_sections = set()
    
    updates: List[SectionUpdate] = []
    
    for section in EXECUTION_ORDER:
        should_update = False
        reason = ""
        
        # Get current text for this section
        # Core sections use "_analysis" suffix, others use section name directly
        field_name = f"{section}_analysis" if section in ["fundamental", "medium", "current"] else section
        current_text = existing_sections.get(field_name, "")
        
        # Always update if missing text
        if not current_text or current_text.strip() == "":
            should_update = True
            reason = "missing_text"
        
        # Update if any dependency was updated in this cascade
        elif any(dep in updated_sections for dep in SECTION_DEPENDENCIES[section]):
            should_update = True
            reason = "dependency_updated"
            
        # For core sections matching the trigger, assume new articles warrant update
        # (This would integrate with existing should_rewrite_llm logic in full implementation)
        elif section in ["fundamental", "medium", "current"] and section == trigger_section:
            should_update = True
            reason = "new_articles"
        
        if should_update:
            updates.append(SectionUpdate(
                section=section,
                reason=reason,
                triggered_by=trigger_section
            ))
            updated_sections.add(section)
    
    return updates


def analysis_rewriter(
    topic_id: str, test: bool = False, analysis_type: Optional[str] = None
) -> None:
    """
    Orchestrates the full analysis pipeline for a topic node.
    If analysis_type is given, only that section is run. Otherwise, all sections are run in order.
    Logs every input, output, and error. Fails fast and loud.
    Now also emits tracker events for full run and per-section, capturing all LLM outputs/feedback.
    """
    logger.info(f"Starting analysis_rewriter for topic_id={topic_id}")
    
    # Analysis rewriter tracking removed (not in new stats structure)
    from src.observability.pipeline_logging import master_statistics
    
    run_id = f"{topic_id}__analysis_run__{int(time.time())}"
    sections_to_run = [analysis_type] if analysis_type else SECTIONS

    # Get topic name for asset focus
    try:
        topic_info = get_all_analysis_sections(topic_id)
        topic_name = topic_info.get("name", topic_id)
    except Exception:
        topic_name = topic_id  # Fallback to ID if name not available
    
    analysis_results: dict[str, str] = {}
    total_chars = 0
    for section in sections_to_run:
        section_focus = SECTION_FOCUS[section]
        # Fail fast: section_focus must always be present and non-empty per contract
        if (
            not section_focus
            or not isinstance(section_focus, str)
            or not section_focus.strip()
        ):
            raise ValueError(
                f"Missing section_focus for section '{section}' on topic {topic_id}"
            )
        if section == "executive_summary":
            logger.info(f"writing executive_summary for topic_id={topic_id}")
            prior_sections = []
            for s in ["fundamental", "medium", "current", "drivers"]:
                if analysis_results.get(s):
                    prior_sections.append(s)
                else:
                    field_name = f"{s}_analysis" if s != "drivers" else "drivers"
                    val = get_topic_analysis_field(topic_id, field_name)
                    if val:
                        analysis_results[s] = val
                        prior_sections.append(s)
                    else:
                        logger.info(
                            f"No analysis found for section '{s}' on topic {topic_id} (in-memory or DB)"
                        )
            logger.info(
                f"Writing executive_summary for topic {topic_id} using sections: {prior_sections}"
            )
            material = "\n\n".join([analysis_results[s] for s in prior_sections])
            logger.info(f"Aggregated material length: {len(material)}")
            if not material.strip():
                logger.info(
                    f"Skipping rewrite for section 'executive_summary' on node {topic_id}: no prior section material available."
                )
                continue
            logger.info(
                f"Invoking rewrite_analysis_llm for executive_summary on topic {topic_id} with material from sections: {prior_sections}"
            )
# REMOVED: drivers special case - now uses unified material builder
        else:
            # Check if we should enrich BEFORE attempting to build material
            # This ensures we have enough articles for quality analysis
            if section in ["fundamental", "medium", "current"]:
                cnt_q = """
                MATCH (a:Article)-[r:ABOUT]->(t:Topic {id:$topic_id})
                WHERE r.timeframe = $section
                RETURN count(a) AS c
                """
                cnt_res = run_cypher(cnt_q, {"topic_id": topic_id, "section": section}) or [{"c": 0}]
                current_cnt = int(cnt_res[0]["c"] or 0)
                
                # Trigger enrichment if below ideal threshold (but above minimum)
                if MIN_ARTICLES_FOR_SECTION <= current_cnt < IDEAL_ARTICLES_FOR_SECTION:
                    from worker.workflows.topic_enrichment import backfill_topic_from_storage
                    
                    logger.info(
                        f"Enriching before analysis | {topic_id} | section={section} | "
                        f"current={current_cnt} < ideal={IDEAL_ARTICLES_FOR_SECTION}"
                    )
                    master_log(
                        f"Enrich for quality | {topic_id} | section={section} | cnt={current_cnt} < {IDEAL_ARTICLES_FOR_SECTION}"
                    )
                    backfill_topic_from_storage(
                        topic_id=topic_id,
                        threshold=IDEAL_ARTICLES_FOR_SECTION,
                        max_articles_per_section=5,
                        min_keyword_hits=2,
                        test=test,
                        sections=[section],
                    )
            
            try:
                # Use unified material builder for all sections
                logger.info(f"📦 Building material | topic={topic_id} section={section}")
                material, article_ids = build_material_for_synthesis_section(
                    topic_id, section
                )
                logger.info(
                    f"✅ Material built | topic={topic_id} section={section} | "
                    f"articles={len(article_ids)} chars={len(material)}"
                )
            except ValueError as e:
                logger.warning(
                    f"⚠️  Material builder failed | topic={topic_id} section={section} | error={str(e)[:100]}"
                )
                if "No articles selected" in str(e) or "No articles available" in str(e):
                    # Count current pool; if under threshold, enhance then retry once
                    cnt_q = """
                    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id:$topic_id})
                    WHERE r.timeframe = $section
                    RETURN count(a) AS c
                    """
                    cnt_res = run_cypher(
                        cnt_q, {"topic_id": topic_id, "section": section}
                    ) or [{"c": 0}]
                    current_cnt = int(cnt_res[0]["c"] or 0)
                    logger.info(
                        f"📊 Article count check | topic={topic_id} section={section} | "
                        f"current={current_cnt} min_required={MIN_ARTICLES_FOR_SECTION}"
                    )
                    # Trigger enrichment if below minimum threshold
                    if current_cnt < MIN_ARTICLES_FOR_SECTION:
                        logger.info(
                            f"🔄 Triggering enrichment | topic={topic_id} section={section} | "
                            f"current={current_cnt} < min={MIN_ARTICLES_FOR_SECTION}"
                        )
                        from worker.workflows.topic_enrichment import (
                            backfill_topic_from_storage,
                        )

                        master_log(
                            f"Enhance before rewrite | {topic_id} | section={section} | cnt={current_cnt} < {MIN_ARTICLES_FOR_SECTION}"
                        )
                        backfill_topic_from_storage(
                            topic_id=topic_id,
                            threshold=MIN_ARTICLES_FOR_SECTION,
                            max_articles_per_section=5,
                            min_keyword_hits=2,
                            test=test,
                            sections=[section],
                        )
                        # Retry once after enrichment
                        try:
                            logger.info(f"🔄 Retry material build after enrichment | topic={topic_id} section={section}")
                            material, article_ids = (
                                build_material_for_synthesis_section(topic_id, section)
                            )
                            logger.info(
                                f"✅ Material built after enrichment | topic={topic_id} section={section} | "
                                f"articles={len(article_ids)}"
                            )
                        except ValueError:
                            logger.warning(
                                f"⏭️  SKIPPING section | topic={topic_id} section={section} | "
                                f"No articles after enrichment retry - needs manual investigation"
                            )
                            p = ProblemDetailsModel()
                            p.section = section
                            problem_log(
                                Problem.REWRITE_SKIPPED_0_ARTICLES,
                                topic=topic_id,
                                details=p,
                            )
                            continue
                    else:
                        logger.info(
                            f"⏭️  SKIPPING section | topic={topic_id} section={section} | "
                            f"Has {current_cnt} articles (>= min) but selector returned 0 - "
                            f"likely quality/filtering issue"
                        )
                        p = ProblemDetailsModel()
                        p.section = section
                        problem_log(
                            Problem.REWRITE_SKIPPED_0_ARTICLES,
                            topic=topic_id,
                            details=p,
                        )
                        continue
                raise
        if not material.strip():
            logger.info(
                f"Skipping rewrite for section '{section}' on node {topic_id}: no formatted material available."
            )
            continue
        
        # Track LLM generation attempt
        try:
            rewritten = rewrite_analysis_llm(
                material, 
                section_focus, 
                asset_name=topic_name, 
                asset_id=topic_id, 
                trk=None
            )
        except Exception as e:
            logger.error(f"LLM generation failed for {topic_id}/{section}: {e}")
            raise
        
        mapped_field = section
        if section in ["fundamental", "medium", "current"]:
            mapped_field = f"{section}_analysis"
        
        if not test and rewritten and rewritten.strip():
            try:
                save_analysis(topic_id, mapped_field, rewritten)
            except Exception as e:
                logger.error(f"Analysis save failed for {topic_id}/{section}: {e}")
                raise
        
        analysis_results[section] = rewritten
        total_chars += len(rewritten or "")
        logger.info(f"Section '{section}' rewritten and set for node {topic_id}.")
    
    if test:
        logger.info(
            f"analysis_rewriter complete for topic_id={topic_id} but will not save. In testing mode."
        )
    logger.info(
        f"Total characters in all rewritten analysis fields for topic_id={topic_id}: {total_chars}"
    )
    logger.info(f"analysis_rewriter complete for topic_id={topic_id}")
    master_log(f"Rewrite complete | {topic_id} | total_chars={total_chars}")
    # analysis_sections_written is already tracked by analysis_saver.py


def analysis_rewriter_with_dependencies(
    topic_id: str,
    trigger_section: str,  # Which section triggered this update ("fundamental", "medium", "current")
    analysis_type: Optional[str] = None,
    test: bool = False,
    run_id: Optional[str] = None,
) -> None:
    """
    Orchestrate analysis updates with dependency cascade.
    
    This is the new dependency-aware orchestrator that:
    1. Queries ALL analysis sections to check completeness
    2. Determines which sections need updating based on dependencies
    3. Updates sections in proper dependency order
    4. Cascades updates through the dependency chain
    
    Args:
        topic_id: The topic to update
        trigger_section: Which section triggered this ("fundamental", "medium", "current")
        analysis_type: If specified, only update this section (overrides dependency logic)
        test: If True, don't save to database
        run_id: Optional run identifier for tracking
    
    Raises:
        ValueError: If topic not found or invalid trigger_section
        Exception: Any LLM or database errors (fail fast, no fallbacks)
    """
    if run_id is None:
        run_id = f"dep_cascade_{int(time.time())}"
    
    logger.info(f"Starting dependency-aware analysis for topic_id={topic_id}, trigger={trigger_section}")
    
    # Validate trigger section
    if trigger_section not in ["fundamental", "medium", "current"]:
        raise ValueError(f"Invalid trigger_section: {trigger_section}. Must be one of: fundamental, medium, current")
    
    # Get all existing sections (fail fast if topic not found)
    existing_sections = get_all_analysis_sections(topic_id)
    topic_name = existing_sections.get("name", topic_id)
    
    # If analysis_type specified, override dependency logic and update only that section
    if analysis_type:
        logger.info(f"Single section mode: updating only '{analysis_type}' for topic_id={topic_id}")
        updates_needed = [SectionUpdate(
            section=analysis_type,
            reason="single_section_request",
            triggered_by=trigger_section
        )]
    else:
        # Determine what needs updating based on dependencies
        updates_needed = determine_sections_to_update(existing_sections, trigger_section)
    
    if not updates_needed:
        logger.info(f"No updates needed for topic_id={topic_id}")
        return
    
    logger.info(f"Sections to update for {topic_name}: {[u.section for u in updates_needed]}")
    
    # Execute updates in dependency order
    analysis_results: Dict[str, str] = {}
    total_chars = 0
    
    for update in updates_needed:
        section = update.section
        logger.info(f"Updating section '{section}' for {topic_name} (reason: {update.reason})")
        
        try:
            # Get section focus (fail fast if section not found)
            if section not in SECTION_FOCUS:
                raise ValueError(f"Unknown section: {section}")
            section_focus = SECTION_FOCUS[section]
            
            # Build material using existing logic
            material, article_ids = build_material_for_synthesis_section(topic_id, section)
            if not material or not material.strip():
                logger.warning(f"No material available for section '{section}' on topic {topic_id}")
                continue
            
            # Load market data using existing functions
            market_data = ""
            try:
                neo4j_data = load_market_data_from_neo4j(topic_id)
                if neo4j_data and neo4j_data.get("market_data"):
                    asset_class = AssetClass(neo4j_data["asset_class"])
                    snapshot = MarketSnapshot(
                        ticker=neo4j_data["ticker"],
                        asset_class=asset_class,
                        data=neo4j_data["market_data"],
                        updated_at=date.today(),
                        source=neo4j_data["source"]
                    )
                    market_data = format_market_data_display(snapshot)
                    logger.info(f"✅ Loaded market data for {topic_name} ({neo4j_data['ticker']})")
            except Exception as e:
                logger.debug(f"No market data available for {topic_name}: {e}")
                market_data = ""  # Fail silently, continue without market data
            
            # Generate analysis using existing LLM logic
            rewritten = rewrite_analysis_llm(
                material=material,
                section_focus=section_focus,
                asset_name=topic_name,
                asset_id=topic_id,
                market_data=market_data
            )
            
            if not rewritten or not rewritten.strip():
                raise ValueError(f"LLM returned empty result for section '{section}' on topic {topic_id}")
            
            analysis_results[section] = rewritten
            total_chars += len(rewritten)
            
            # Save immediately (fail fast if save fails)
            if not test:
                mapped_field = f"{section}_analysis" if section in ["fundamental", "medium", "current"] else section
                save_analysis(topic_id, mapped_field, rewritten)
                logger.info(f"✅ Saved section '{section}' for {topic_name} ({len(rewritten)} chars)")
            else:
                logger.info(f"✅ Generated section '{section}' for {topic_name} ({len(rewritten)} chars) [TEST MODE]")
            
        except Exception as e:
            logger.error(f"❌ Failed to update section '{section}' for topic {topic_id}: {e}")
            raise  # Fail fast - no fallbacks
    
    logger.info(f"✅ Completed dependency-aware analysis for {topic_name} (total: {total_chars} chars)")


def trigger_analysis_update(topic_id: str, trigger_section: str) -> None:
    """
    Simple entry point for triggering cascading analysis updates.
    
    This is the main function that should be called when new articles arrive
    or when analysis needs to be refreshed.
    
    Args:
        topic_id: The topic to update
        trigger_section: Which section triggered this ("fundamental", "medium", "current")
    
    Raises:
        Exception: Any errors from the analysis pipeline (fail fast)
    """
    try:
        analysis_rewriter_with_dependencies(
            topic_id=topic_id,
            trigger_section=trigger_section,
            test=False
        )
        logger.info(f"✅ Analysis cascade completed for topic {topic_id}")
    except Exception as e:
        logger.error(f"❌ Analysis cascade failed for topic {topic_id}: {e}")
        raise
