"""
Orchestrator: loops over all analysis sections for a topic, calls rewrite_analysis_llm for each, formats and saves results.
No prompt logic here.
"""

from typing import Optional, Dict, List, Set
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
from events.classifier import EventClassifier, EventType
from src.graph.ops.topic import get_topic_analysis_field
import time

logger = app_logging.get_logger(__name__)

MIN_ARTICLES_FOR_SECTION = 2

SECTION_FOCUS = {
    "fundamental": (
        "HORIZON: Multi-year structural analysis. "
        "CONTENT: Derive first-principles/invariant anchors for the primary asset (real rate differentials, terms-of-trade, productivity, BoP, policy reaction functions). State regimes and transition conditions; articulate explicit causal chains to asset pricing. "
        "FORMAT: 2-3 authoritative paragraphs, professional tone, maximum information density. "
        "STRUCTURE: Causal chain → Base case → Key risks → Watch signals → Confidence level. "
        "CITATIONS: Only 9-character IDs. FOCUS: Every sentence about primary asset performance."
    ),
    "medium": (
        "HORIZON: 3-6 months scenario analysis. "
        "CONTENT: Build scenario/catalyst map for primary asset with triggers and invalidations. Integrate macro data, policy, positioning, flows affecting the asset. "
        "FORMAT: 2-3 compact paragraphs, authoritative tone, decision-focused. "
        "STRUCTURE: Scenario map → Timing windows → Base case + alternatives → Risks → Watch signals → Confidence. "
        "CITATIONS: Only 9-character IDs. FOCUS: All scenarios about primary asset movement."
    ),
    "current": (
        "HORIZON: 0-3 weeks immediate analysis. "
        "CONTENT: Explain immediate drivers affecting primary asset (news/data/policy), near-term catalysts and positioning dynamics, expected reaction function. "
        "FORMAT: 1-2 paragraphs, urgent tone, actionable intelligence. "
        "STRUCTURE: Immediate drivers → Key levels/thresholds → Expected reaction → Invalidation signals → Next monitors. "
        "CITATIONS: Only 9-character IDs. FOCUS: All catalysts about primary asset price action. "
        "MANDATORY: Always generate content - this is core market analysis function."
    ),
    "drivers": (
        "HORIZON: Cross-topic synthesis. "
        "CONTENT: Synthesize most material drivers affecting primary asset (macro, policy, flows/positioning, technicals). Show explicit transmission mechanisms to asset. "
        "FORMAT: Concise synthesis, professional tone, maximum insight density. "
        "STRUCTURE: Key drivers → Direction/mechanisms → Fragility points → Watch signals. "
        "CITATIONS: Only 9-character IDs. FOCUS: All drivers impact primary asset specifically."
    ),
    "executive_summary": (
        "HORIZON: Integrated synthesis across all timeframes. "
        "CONTENT: Integrate fundamental/medium/current views into crisp house view for primary asset. Highlight catalysts, risks, watch-items. "
        "FORMAT: Executive brief, authoritative tone, decision-useful intelligence. "
        "STRUCTURE: House view → Key catalysts → Critical risks → Watch items → Confidence. "
        "LENGTH: Maximum information density - shortest possible text. "
        "CITATIONS: Only 9-character IDs. FOCUS: All insights about primary asset performance."
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
}

SECTIONS = [
    "fundamental",
    "medium",
    "current",
    "drivers",
    "movers_scenarios",
    "swing_trade_or_outlook",
    "executive_summary",
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
    
    # Track analysis rewriter attempts - always increment regardless of analysis_type
    from src.observability.pipeline_logging import master_statistics
    master_statistics(analysis_rewriter_attempted=1)
    
    run_tracker = EventClassifier(EventType.ANALYSIS_REWRITER_RUN)
    run_id = f"{topic_id}__analysis_run__{int(time.time())}"
    section_summaries = []
    sections_to_run = [analysis_type] if analysis_type else SECTIONS

    run_tracker.put_many(
        topic_id=topic_id,
        test=bool(test),
        analysis_type=analysis_type or "all",
        sections_to_run=sections_to_run,
    )

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
        section_tracker = EventClassifier(EventType.ANALYSIS_SECTION_REWRITE)
        section_tracker.put_many(
            topic_id=topic_id, section=section, test=bool(test), run_id=run_id
        )
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
            section_tracker.put("prior_sections", prior_sections)
            material = "\n\n".join([analysis_results[s] for s in prior_sections])
            logger.info(f"Aggregated material length: {len(material)}")
            if not material.strip():
                logger.info(
                    f"Skipping rewrite for section 'executive_summary' on node {topic_id}: no prior section material available."
                )
                section_tracker.put("status", "skipped_no_material")
                section_tracker.set_id(f"{topic_id}__{section}__{run_id}")
                section_summaries.append(
                    {
                        "section": section,
                        "tracker_id": f"{topic_id}__{section}__{run_id}",
                    }
                )
                continue
            logger.info(
                f"Invoking rewrite_analysis_llm for executive_summary on topic {topic_id} with material from sections: {prior_sections}"
            )
# REMOVED: drivers special case - now uses unified material builder
        else:
            try:
                # Use unified material builder for all sections
                material, article_ids = build_material_for_synthesis_section(
                    topic_id, section
                )
                section_tracker.put_many(
                    article_ids=article_ids, selected_articles_count=len(article_ids)
                )
            except ValueError as e:
                if "No articles selected" in str(e):
                    # Count current pool; if under threshold, enhance then retry once
                    cnt_q = """
                    MATCH (a:Article)-[:ABOUT]->(t:Topic {id:$topic_id})
                    WHERE a.temporal_horizon = $section AND (a.priority IS NULL OR a.priority <> 'hidden')
                    RETURN count(a) AS c
                    """
                    cnt_res = run_cypher(
                        cnt_q, {"topic_id": topic_id, "section": section}
                    ) or [{"c": 0}]
                    current_cnt = int(cnt_res[0]["c"] or 0)
                    logger.info(
                        f"Rewrite missing material | {topic_id} | section={section} | current_cnt={current_cnt} < {MIN_ARTICLES_FOR_SECTION}"
                    )
                    if current_cnt < MIN_ARTICLES_FOR_SECTION:
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
                        # Retry once
                        try:
                            material, article_ids = (
                                build_material_for_synthesis_section(topic_id, section)
                            )
                            section_tracker.put_many(
                                article_ids=article_ids,
                                selected_articles_count=len(article_ids),
                            )
                        except ValueError:
                            logger.warning(
                                f"Skipping rewrite for section '{section}' on node {topic_id}: no articles selected after enhancement retry."
                            )
                            p = ProblemDetailsModel()
                            p.section = section
                            problem_log(
                                Problem.REWRITE_SKIPPED_0_ARTICLES,
                                topic=topic_id,
                                details=p,
                            )
                            section_tracker.put(
                                "status", "skipped_selector_zero_articles"
                            )
                            section_tracker.set_id(f"{topic_id}__{section}__{run_id}")
                            section_summaries.append(
                                {
                                    "section": section,
                                    "tracker_id": f"{topic_id}__{section}__{run_id}",
                                }
                            )
                            continue
                    else:
                        logger.warning(
                            f"Skipping rewrite for section '{section}' on node {topic_id}: no articles selected by selector (0)."
                        )
                        p = ProblemDetailsModel()
                        p.section = section
                        problem_log(
                            Problem.REWRITE_SKIPPED_0_ARTICLES,
                            topic=topic_id,
                            details=p,
                        )
                        section_tracker.put("status", "skipped_selector_zero_articles")
                        section_tracker.set_id(f"{topic_id}__{section}__{run_id}")
                        section_summaries.append(
                            {
                                "section": section,
                                "tracker_id": f"{topic_id}__{section}__{run_id}",
                            }
                        )
                        continue
                raise
        section_tracker.put("material_chars", len(material))
        if not material.strip():
            logger.info(
                f"Skipping rewrite for section '{section}' on node {topic_id}: no formatted material available."
            )
            section_tracker.put("status", "skipped_no_material")
            section_tracker.set_id(f"{topic_id}__{section}__{run_id}")
            section_summaries.append(
                {"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"}
            )
            master_statistics(analysis_rewriter_stopped_no_articles=1)
            continue
        
        # Track LLM generation attempt
        try:
            rewritten = rewrite_analysis_llm(
                material, 
                section_focus, 
                asset_name=topic_name, 
                asset_id=topic_id, 
                trk=section_tracker
            )
            if rewritten and rewritten.strip():
                master_statistics(analysis_llm_generation_proceeded=1)
            else:
                master_statistics(analysis_llm_generation_stopped_failure=1)
        except Exception as e:
            logger.error(f"LLM generation failed for {topic_id}/{section}: {e}")
            master_statistics(analysis_llm_generation_stopped_failure=1)
            raise
        
        section_tracker.put("output_chars", len(rewritten or ""))
        mapped_field = section
        if section in ["fundamental", "medium", "current"]:
            mapped_field = f"{section}_analysis"
        
        # Track save attempt
        if not test and rewritten and rewritten.strip():
            try:
                save_analysis(topic_id, mapped_field, rewritten)
                section_tracker.put_many(
                    saved=True, saved_field=mapped_field, status="success"
                )
                master_statistics(analysis_save_proceeded=1)
            except Exception as e:
                logger.error(f"Analysis save failed for {topic_id}/{section}: {e}")
                master_statistics(analysis_save_stopped_error=1)
                raise
        else:
            section_tracker.put_many(
                saved=False,
                saved_field=mapped_field,
                status="generated_no_save" if test else "no_text_not_saved",
            )
        section_tracker.set_id(f"{topic_id}__{section}__{run_id}")
        section_summaries.append(
            {"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"}
        )
        analysis_results[section] = rewritten
        total_chars += len(rewritten or "")
        logger.info(f"Section '{section}' rewritten and set for node {topic_id}.")
    run_tracker.put_many(
        total_chars=total_chars, sections=section_summaries, status="success"
    )
    run_tracker.set_id(run_id)
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
            
            # Generate analysis using existing LLM logic
            rewritten = rewrite_analysis_llm(
                material=material,
                section_focus=section_focus,
                asset_name=topic_name,
                asset_id=topic_id
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
