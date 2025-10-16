"""
Builds formatted SOURCE MATERIAL for analysis rewriting, using summaries-only plus minimal metadata.
- Loads full article JSON via utils.load_article.load_article
- Requires existing argos_summary (strict); no fallbacks.
- Per-article output includes exactly: Title, Published, optional Source, and Summary.
- No URL or ID lines are included. Keeps prompts small and robust.
"""

from __future__ import annotations
from typing import List, Tuple

from utils import app_logging

logger = app_logging.get_logger("analysis.material.article_material")

from src.analysis.selectors.best_articles import select_best_articles
from src.articles.load_article import load_article
from src.observability.pipeline_logging import problem_log, Problem, ProblemDetailsModel


def build_material_for_section(topic_id: str, section: str) -> Tuple[str, List[str]]:
    """DEPRECATED: Use build_material_for_synthesis_section() instead"""
    logger.warning(f"DEPRECATED: build_material_for_section() called for {topic_id}/{section} - redirecting to new function")
    return build_material_for_synthesis_section(topic_id, section)


def build_material_for_synthesis_section(
    topic_id: str, section: str
) -> Tuple[str, List[str]]:
    """
    Build material for analysis sections with smart article selection:
    - Timeframe sections (fundamental/medium/current): 10 articles from that timeframe
    - Synthesis sections (drivers/movers_scenarios/swing_trade_or_outlook/executive_summary): 5 articles each from fundamental/medium/current
    - Perspective sections (risk/opportunity/trend/catalyst_analysis): 10 articles with perspective score >= 2
    
    Returns:
        material_str: Formatted material with analysis sections + articles
        article_ids: List of article IDs used
    """
    from src.graph.neo4j_client import run_cypher

    # Section type detection
    TIMEFRAME_SECTIONS = ["fundamental", "medium", "current"]
    SYNTHESIS_SECTIONS = ["drivers", "movers_scenarios", "swing_trade_or_outlook", "executive_summary"]
    PERSPECTIVE_SECTIONS = ["risk_analysis", "opportunity_analysis", "trend_analysis", "catalyst_analysis"]
    
    # Get existing analysis sections - query ALL sections for complete context
    analysis_query = """
    MATCH (t:Topic {id: $topic_id})
    RETURN t.fundamental_analysis, t.medium_analysis, t.current_analysis,
           t.drivers, t.executive_summary, t.movers_scenarios, t.swing_trade_or_outlook,
           t.risk_analysis, t.opportunity_analysis, t.trend_analysis, t.catalyst_analysis
    """
    analysis_result = run_cypher(analysis_query, {"topic_id": topic_id})

    material_parts = []

    # Format existing analysis sections with perfect presentation
    if analysis_result and analysis_result[0]:
        analysis_data = analysis_result[0]

        material_parts.append("=" * 80)
        material_parts.append("SUPPORTING CONTEXT (Drivers/Correlations)")
        material_parts.append("=" * 80)

        for field, label in [
            ("fundamental_analysis", "FUNDAMENTAL ANALYSIS (Multi-year Structural)"),
            ("medium_analysis", "MEDIUM-TERM ANALYSIS (3-6 months)"),
            ("current_analysis", "CURRENT ANALYSIS (0-3 weeks)"),
            ("drivers", "DRIVERS (Cross-topic Influences)"),
            ("risk_analysis", "RISK ANALYSIS (Downside Scenarios)"),
            ("opportunity_analysis", "OPPORTUNITY ANALYSIS (Upside Scenarios)"),
            ("trend_analysis", "TREND ANALYSIS (Structural Shifts)"),
            ("catalyst_analysis", "CATALYST ANALYSIS (Immediate Triggers)"),
            ("executive_summary", "EXECUTIVE SUMMARY"),
            ("movers_scenarios", "MOVERS & SCENARIOS"),
            ("swing_trade_or_outlook", "SWING TRADE / OUTLOOK"),
        ]:
            analysis_content = analysis_data.get(field)
            if analysis_content:
                material_parts.append(f"\n--- {label} ---")
                material_parts.append(str(analysis_content))
                material_parts.append("")

    # Smart article selection based on section type
    if section in TIMEFRAME_SECTIONS:
        # Timeframe sections: 10 articles from specific timeframe
        articles_query = """
        MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
        WHERE coalesce(a.temporal_horizon, '') = $section AND coalesce(a.priority, '') <> 'hidden'
        WITH a, 
             CASE 
               WHEN a.importance = 'hidden' THEN 0
               WHEN a.importance IS NULL THEN 1
               ELSE toInteger(a.importance)
             END as numeric_importance
        RETURN a.id as article_id, a.pubDate as published_at, numeric_importance, coalesce(a.temporal_horizon, 'unknown') as temporal_horizon
        ORDER BY numeric_importance DESC, a.pubDate DESC
        LIMIT 10
        """
        articles_result = run_cypher(articles_query, {"topic_id": topic_id, "section": section})
    elif section in PERSPECTIVE_SECTIONS:
        # Perspective sections: 10 articles with perspective score >= 2
        perspective_field_map = {
            "risk_analysis": "importance_risk",
            "opportunity_analysis": "importance_opportunity",
            "trend_analysis": "importance_trend",
            "catalyst_analysis": "importance_catalyst"
        }
        perspective_field = perspective_field_map[section]
        
        articles_query = f"""
        MATCH (a:Article)-[:ABOUT]->(t:Topic {{id: $topic_id}})
        WHERE coalesce(a.{perspective_field}, 0) >= 2 AND coalesce(a.priority, '') <> 'hidden'
        WITH a, 
             coalesce(a.{perspective_field}, 0) as perspective_score,
             CASE 
               WHEN a.importance = 'hidden' THEN 0
               WHEN a.importance IS NULL THEN 1
               ELSE toInteger(a.importance)
             END as numeric_importance
        RETURN a.id as article_id, a.pubDate as published_at, perspective_score, numeric_importance, 
               coalesce(a.temporal_horizon, 'unknown') as temporal_horizon
        ORDER BY perspective_score DESC, numeric_importance DESC, a.pubDate DESC
        LIMIT 10
        """
        articles_result = run_cypher(articles_query, {"topic_id": topic_id})
    else:
        # Synthesis sections: 5 articles each from fundamental/medium/current
        all_articles = []
        for timeframe in ["fundamental", "medium", "current"]:
            timeframe_query = """
            MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
            WHERE coalesce(a.temporal_horizon, '') = $timeframe AND coalesce(a.priority, '') <> 'hidden'
            WITH a, 
                 CASE 
                   WHEN a.importance = 'hidden' THEN 0
                   WHEN a.importance IS NULL THEN 1
                   ELSE toInteger(a.importance)
                 END as numeric_importance
            RETURN a.id as article_id, a.pubDate as published_at, numeric_importance, coalesce(a.temporal_horizon, 'unknown') as temporal_horizon
            ORDER BY numeric_importance DESC, a.pubDate DESC
            LIMIT 5
            """
            timeframe_result = run_cypher(timeframe_query, {"topic_id": topic_id, "timeframe": timeframe})
            all_articles.extend(timeframe_result or [])
        articles_result = all_articles

    if not articles_result:
        raise ValueError(f"No articles found for topic_id={topic_id}")

    article_ids = [row["article_id"] for row in articles_result]

    # Add primary asset articles section
    material_parts.append("=" * 80)
    material_parts.append(f"PRIMARY ASSET ANALYSIS")
    material_parts.append("SOURCE ARTICLES")
    material_parts.append("=" * 80)

    # Load and format each article
    section_counts = {}
    for i, row in enumerate(articles_result, 1):
        article_id = row["article_id"]
        horizon = row.get("temporal_horizon") or "unknown"
        section_counts[horizon] = section_counts.get(horizon, 0) + 1
        
        try:
            loaded = load_article(article_id)
            if not loaded or "argos_summary" not in loaded:
                raise ValueError(f"Article {article_id} missing argos_summary")
            
            material_parts.append(f"--- ARTICLE {i}: {article_id} ({horizon}) ---")
            material_parts.append(loaded["argos_summary"])
            material_parts.append("")
        except Exception as e:
            logger.warning(f"Failed to load article {article_id}: {e}")
            # Remove failed article from the list
            if article_id in article_ids:
                article_ids.remove(article_id)
    
    # Clear visual separation for each section
    logger.info("=" * 80)
    logger.info(f"🎯 STARTING {section.upper()} SECTION | topic_id={topic_id}")
    logger.info("=" * 80)
    
    # Log article breakdown
    for timeframe in ["fundamental", "medium", "current", "unknown"]:
        if timeframe in section_counts:
            logger.info(f"  {timeframe}: {section_counts[timeframe]} articles")

    material = "\n".join(material_parts).strip()
    
    # Limit material size to prevent LLM token overflow (roughly 100K chars = ~25K tokens)
    # This leaves room for system prompts, analysis sections, and response generation
    MAX_MATERIAL_SIZE = 100_000
    if len(material) > MAX_MATERIAL_SIZE:
        logger.warning(
            f"Material too large ({len(material)} chars), truncating to {MAX_MATERIAL_SIZE} chars"
        )
        material = material[:MAX_MATERIAL_SIZE] + "\n\n[MATERIAL TRUNCATED DUE TO SIZE LIMIT]"

    # Continue with analysis section logging
    
    # Log existing analysis sections that are included in synthesis
    included_sections = []
    if analysis_result and analysis_result[0]:
        analysis_data = analysis_result[0]
        for field, label in [
            ("fundamental_analysis", "fundamental analysis"),
            ("medium_analysis", "medium analysis"), 
            ("current_analysis", "current analysis"),
            ("drivers", "drivers"),
            ("risk_analysis", "risk analysis"),
            ("opportunity_analysis", "opportunity analysis"),
            ("trend_analysis", "trend analysis"),
            ("catalyst_analysis", "catalyst analysis"),
            ("movers_scenarios", "movers scenarios"),
            ("swing_trade_or_outlook", "swing trade/outlook"),
            ("executive_summary", "executive summary")
        ]:
            if analysis_data.get(field):
                included_sections.append(label)
    
    if included_sections:
        logger.info(f"  analysis sections: {', '.join(included_sections)}")
    else:
        logger.info(f"  analysis sections: none")
    
    logger.info(f"  total: {len(article_ids)} articles | {len(material)} chars")

    return material, article_ids
