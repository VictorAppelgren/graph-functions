"""
Orchestrator: loops over all analysis sections for a topic, calls rewrite_analysis_llm for each, formats and saves results.
No prompt logic here.
"""
from typing import Optional
from src.analysis.writing.analysis_rewriter import rewrite_analysis_llm
from src.analysis.persistance.analysis_saver import save_analysis
from src.analysis.utils.driver_aggregator import aggregate_driver_analyses
from src.analysis.material.article_material import build_material_for_synthesis_section
from utils import app_logging
from src.observability.pipeline_logging import master_log, problem_log
from src.graph.neo4j_client import run_cypher
from events.classifier import EventClassifier
from src.graph.ops.get_topic_analysis_field import get_topic_analysis_field
import time
logger = app_logging.get_logger(__name__)

MIN_ARTICLES_FOR_SECTION = 2

SECTION_FOCUS = {
    "fundamental": (
        "Horizon: multi‑year (structural). Derive first‑principles/invariant anchors (e.g., real rate differentials, terms‑of‑trade, productivity, BoP, net external position, policy reaction functions). "
        "State regimes and transition conditions; articulate the causal chain to market pricing. Conclude with base case, key risks, what to watch, confidence."
    ),
    "medium": (
        "Horizon: 3–6 months. Build scenario/catalyst map with triggers and invalidations; integrate macro data, policy, positioning, flows, and valuation. "
        "Specify timing windows and path‑dependency; end with base case, 1–2 alts, risks, watch‑list signals, confidence."
    ),
    "current": (
        "Horizon: 0–3 weeks. Explain immediate drivers (news/data/policy), near‑term catalysts and positioning dynamics, and expected reaction function. "
        "State key levels/thresholds, invalidation, and what to monitor next."
    ),
    "drivers": (
        "Synthesize the most material cross‑topic drivers (macro, policy, flows/positioning, valuation/technicals). "
        "Clarify direction/sign, mechanisms, and where the view is fragile; provide a concise watch‑list of decisive upcoming signals."
    ),
    "executive_summary": (
        "Professional investor brief: integrate fundamental/medium/current views into a crisp house view, highlighting catalysts, risks, and watch‑items. "
        "Be decision‑useful and specific; avoid platitudes. "
        "Be concise, to-the-point, and executive in style—no filler or repetition. Limit to 4–6 sentences or bullet points."
    ),
    "movers_scenarios": (
        "Be precise, compact, and forward-looking. Output exactly 4 items: 2 Up and 2 Down. Each item must be a single line strictly formatted as: "
        "Up/Down | Time window | Driver/Mechanism | What to watch | Probability %. "
        "Require concrete triggers and probabilities based on the best-supported facts from the material. Keep each line to one sentence, no filler. "
        "Use in-text (ID) citations only when asserting specific facts or numbers. Never include a references section or citation list."
    ),
    "swing_trade_or_outlook": (
        "Produce a first-principles, scenario-driven Swing Trade or Outlook using only the provided material. "
        "1) Movers & Scenarios: output exactly 4 lines — 2 Up and 2 Down. Each line strictly: "
        "Up/Down | Time window | Driver/Mechanism | What to watch | Probability %. "
        "Base probabilities on evidence in the material; use in-text (ID) citations only when asserting specific facts or numbers. "
        "2) Trade/Outlook Plan (1–2 lines total): If asset is tradable (e.g., FX pair, equity, commodity, liquid rate future), output Swing Trade lines strictly: "
        "Direction | Horizon | Entry | Stop | Target | R/R | Invalidation | Trigger | Probability % | Confidence 0–100. "
        "If not tradable, output an Outlook line strictly: Direction | Horizon | Expected path/levels | Decision signals | Invalidation | Trigger | Probability % | Confidence 0–100. "
        "Keep Outlook shorter (prefer 1 line; max 2). Swing Trade may use up to 2 lines if needed. "
        "Be precise, forward-looking, and actionable. No filler. No references section; never include trailing citation lists."
    ),
}

SECTIONS = ["fundamental", "medium", "current", "drivers", "movers_scenarios", "swing_trade_or_outlook", "executive_summary"]

def analysis_rewriter(topic_id: str, test: bool = False, analysis_type: Optional[str] = None) -> None:
    """
    Orchestrates the full analysis pipeline for a topic node.
    If analysis_type is given, only that section is run. Otherwise, all sections are run in order.
    Logs every input, output, and error. Fails fast and loud.
    Now also emits tracker events for full run and per-section, capturing all LLM outputs/feedback.
    """
    logger.info(f"Starting analysis_rewriter for topic_id={topic_id}")
    run_trk = EventClassifier("analysis_rewriter_run")
    run_id = f"{topic_id}__analysis_run__{int(time.time())}"
    run_trk.put("topic_id", topic_id)
    run_trk.put("test", bool(test))
    run_trk.put("analysis_type", analysis_type or "all")
    section_summaries = []
    sections_to_run = [analysis_type] if analysis_type else SECTIONS
    run_trk.put("sections_to_run", sections_to_run)
    analysis_results: dict[str, str] = {}
    total_chars = 0
    for section in sections_to_run:
        section_focus = SECTION_FOCUS[section]
        sec_trk = EventClassifier("analysis_section_rewrite")
        sec_trk.put("topic_id", topic_id)
        sec_trk.put("section", section)
        sec_trk.put("test", bool(test))
        sec_trk.put("run_id", run_id)
        # Fail fast: section_focus must always be present and non-empty per contract
        if not section_focus or not isinstance(section_focus, str) or not section_focus.strip():
            raise ValueError(f"Missing section_focus for section '{section}' on topic {topic_id}")
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
                        logger.info(f"No analysis found for section '{s}' on topic {topic_id} (in-memory or DB)")
            logger.info(f"Writing executive_summary for topic {topic_id} using sections: {prior_sections}")
            sec_trk.put("prior_sections", prior_sections)
            material = "\n\n".join([analysis_results[s] for s in prior_sections])
            logger.info(f"Aggregated material length: {len(material)}")
            if not material.strip():
                logger.info(f"Skipping rewrite for section 'executive_summary' on node {topic_id}: no prior section material available.")
                sec_trk.put("status", "skipped_no_material")
                sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
                section_summaries.append({"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"})
                continue
            logger.info(f"Invoking rewrite_analysis_llm for executive_summary on topic {topic_id} with material from sections: {prior_sections}")
        elif section == "movers_scenarios":
            logger.info(f"writing movers_scenarios for topic_id={topic_id}")
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
                        logger.info(f"No analysis found for section '{s}' on topic {topic_id} (in-memory or DB)")
            logger.info(f"Writing movers_scenarios for topic {topic_id} using sections: {prior_sections}")
            sec_trk.put("prior_sections", prior_sections)
            material = "\n\n".join([analysis_results[s] for s in prior_sections])
            logger.info(f"Aggregated material length: {len(material)}")
            if not material.strip():
                logger.info(f"Skipping rewrite for section 'movers_scenarios' on node {topic_id}: no prior section material available.")
                sec_trk.put("status", "skipped_no_material")
                sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
                section_summaries.append({"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"})
                continue
            logger.info(f"Invoking rewrite_analysis_llm for movers_scenarios on topic {topic_id} with material from sections: {prior_sections}")
        elif section == "swing_trade_or_outlook":
            logger.info(f"writing swing_trade_or_outlook for topic_id={topic_id}")
            prior_sections = []
            for s in ["fundamental", "medium", "current", "drivers", "executive_summary"]:
                if analysis_results.get(s):
                    prior_sections.append(s)
                else:
                    if s in ("drivers", "executive_summary"):
                        field_name = s
                    else:
                        field_name = f"{s}_analysis"
                    val = get_topic_analysis_field(topic_id, field_name)
                    if val:
                        analysis_results[s] = val
                        prior_sections.append(s)
                    else:
                        logger.info(f"No analysis found for section '{s}' on topic {topic_id} (in-memory or DB)")
            logger.info(f"Writing swing_trade_or_outlook for topic {topic_id} using sections: {prior_sections}")
            sec_trk.put("prior_sections", prior_sections)
            material = "\n\n".join([analysis_results[s] for s in prior_sections])
            logger.info(f"Aggregated material length: {len(material)}")
            if not material.strip():
                logger.info(f"Skipping rewrite for section 'swing_trade_or_outlook' on node {topic_id}: no prior section material available.")
                sec_trk.put("status", "skipped_no_material")
                sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
                section_summaries.append({"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"})
                continue
            logger.info("Invoking rewrite_analysis_llm for swing_trade_or_outlook on topic %s with material from sections: %s", topic_id, prior_sections)
        elif section == "drivers":
            driver_summaries = aggregate_driver_analyses(topic_id)
            filtered_drivers = []
            for d in driver_summaries:
                if not d or not d.get('executive_summary'):
                    logger.warning(f"Skipping driver for topic {topic_id} in section 'drivers': missing or empty executive_summary.")
                    continue
                filtered_drivers.append(d)
            sec_trk.put("drivers_count", len(filtered_drivers))
            if len(filtered_drivers) < 1:
                logger.info(f"Skipping rewrite for section 'drivers' on node {topic_id}: no valid driver executive summaries available.")
                sec_trk.put("status", "skipped_no_material")
                sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
                section_summaries.append({"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"})
                continue
            material = "\n".join([
                f"{d.get('name', '[no name]')} ({d.get('relation', '[no relation]')}): {(d.get('executive_summary') or '')[:400]}"
                for d in filtered_drivers
            ])
        else:
            try:
                # Use synthesis input for non-timeframe sections
                if section in ["drivers", "movers_scenarios", "swing_trade_or_outlook", "executive_summary"]:
                    material, article_ids = build_material_for_synthesis_section(topic_id, section)
                else:
                    material, article_ids = build_material_for_synthesis_section(topic_id, section)
                sec_trk.put("article_ids", article_ids)
                sec_trk.put("selected_articles_count", len(article_ids))
            except ValueError as e:
                if "No articles selected" in str(e):
                    # Count current pool; if under threshold, enhance then retry once
                    cnt_q = """
                    MATCH (a:Article)-[:ABOUT]->(t:Topic {id:$topic_id})
                    WHERE a.temporal_horizon = $section AND (a.priority IS NULL OR a.priority <> 'hidden')
                    RETURN count(a) AS c
                    """
                    cnt_res = run_cypher(cnt_q, {"topic_id": topic_id, "section": section}) or [{"c": 0}]
                    current_cnt = int(cnt_res[0]["c"] or 0)
                    logger.info(f"Rewrite missing material | {topic_id} | section={section} | current_cnt={current_cnt} < {MIN_ARTICLES_FOR_SECTION}")
                    if current_cnt < MIN_ARTICLES_FOR_SECTION:
                        from worker.workflows.topic_enrichment import backfill_topic_from_storage
                        master_log(f"Enhance before rewrite | {topic_id} | section={section} | cnt={current_cnt} < {MIN_ARTICLES_FOR_SECTION}")
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
                            material, article_ids = build_material_for_synthesis_section(topic_id, section)
                            sec_trk.put("article_ids", article_ids)
                            sec_trk.put("selected_articles_count", len(article_ids))
                        except ValueError:
                            logger.warning(
                                f"Skipping rewrite for section '{section}' on node {topic_id}: no articles selected after enhancement retry."
                            )
                            problem_log("rewrites_skipped_0_articles", topic=topic_id, details={"section": section})
                            sec_trk.put("status", "skipped_selector_zero_articles")
                            sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
                            section_summaries.append({"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"})
                            continue
                    else:
                        logger.warning(
                            f"Skipping rewrite for section '{section}' on node {topic_id}: no articles selected by selector (0)."
                        )
                        problem_log("rewrites_skipped_0_articles", topic=topic_id, details={"section": section})
                        sec_trk.put("status", "skipped_selector_zero_articles")
                        sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
                        section_summaries.append({"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"})
                        continue
                raise
        sec_trk.put("material_chars", len(material))
        if not material.strip():
            logger.info(f"Skipping rewrite for section '{section}' on node {topic_id}: no formatted material available.")
            sec_trk.put("status", "skipped_no_material")
            sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
            section_summaries.append({"section": section, "tracker_id": f"{topic_id}__{section}__{run_id}"})
            continue
        rewritten = rewrite_analysis_llm(material, section_focus, trk=sec_trk)
        sec_trk.put("output_chars", len(rewritten or ""))
        mapped_field = section
        if section in ["fundamental", "medium", "current"]:
            mapped_field = f"{section}_analysis"
        if not test and rewritten and rewritten.strip():
            save_analysis(topic_id, mapped_field, rewritten)
            sec_trk.put("saved", True)
            sec_trk.put("saved_field", mapped_field)
            sec_trk.put("status", "success")
        else:
            sec_trk.put("saved", False)
            sec_trk.put("saved_field", mapped_field)
            sec_trk.put("status", "generated_no_save" if test else "no_text_not_saved")
        sec_trk.set_id(f"{topic_id}__{section}__{run_id}")
        section_summaries.append({
            "section": section,
            "tracker_id": f"{topic_id}__{section}__{run_id}"
        })
        analysis_results[section] = rewritten
        total_chars += len(rewritten or "")
        logger.info(f"Section '{section}' rewritten and set for node {topic_id}.")
    run_trk.put("total_chars", total_chars)
    run_trk.put("sections", section_summaries)
    run_trk.put("status", "success")
    run_trk.set_id(run_id)
    if test:
        logger.info(f"analysis_rewriter complete for topic_id={topic_id} but will not save. In testing mode.")
    logger.info(f"Total characters in all rewritten analysis fields for topic_id={topic_id}: {total_chars}")
    logger.info(f"analysis_rewriter complete for topic_id={topic_id}")
    master_log(f"Rewrite complete | {topic_id} | total_chars={total_chars}", rewrites_saved=1)
