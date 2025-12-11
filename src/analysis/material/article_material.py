"""
Builds formatted SOURCE MATERIAL for analysis rewriting, using summaries-only plus minimal metadata.
- Loads full article JSON via load_article
- Uses argos_summary, falls back to summary, then description
- Per-article output includes exactly: Title, Published, optional Source, and Summary.
"""

from __future__ import annotations
from typing import List, Tuple

from utils import app_logging

logger = app_logging.get_logger("analysis.material.article_material")

from src.articles.load_article import load_article


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
        # Timeframe sections: 10 articles from specific timeframe (using relationship properties)
        articles_query = """
        MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
        WHERE r.timeframe = $section
        WITH a, r,
             CASE 
               WHEN coalesce(r.importance_risk, 0) >= coalesce(r.importance_opportunity, 0) 
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_risk, 0)
               WHEN coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_opportunity, 0)
               WHEN coalesce(r.importance_trend, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_trend, 0)
               ELSE coalesce(r.importance_catalyst, 0)
             END as overall_importance
        RETURN a.id as article_id, a.published_at as published_at, 
               overall_importance as numeric_importance,
               r.timeframe as temporal_horizon,
               r.motivation as motivation,
               r.implications as implications,
               r.importance_risk, r.importance_opportunity, r.importance_trend, r.importance_catalyst
        ORDER BY overall_importance DESC, a.published_at DESC
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
        MATCH (a:Article)-[r:ABOUT]->(t:Topic {{id: $topic_id}})
        WHERE coalesce(r.{perspective_field}, 0) >= 2
        WITH a, r,
             coalesce(r.{perspective_field}, 0) as perspective_score,
             CASE 
               WHEN coalesce(r.importance_risk, 0) >= coalesce(r.importance_opportunity, 0) 
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_risk, 0)
               WHEN coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_opportunity, 0)
               WHEN coalesce(r.importance_trend, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_trend, 0)
               ELSE coalesce(r.importance_catalyst, 0)
             END as overall_importance
        RETURN a.id as article_id, a.published_at as published_at, 
               perspective_score, overall_importance as numeric_importance,
               r.timeframe as temporal_horizon,
               r.motivation as motivation,
               r.implications as implications,
               r.importance_risk, r.importance_opportunity, r.importance_trend, r.importance_catalyst
        ORDER BY perspective_score DESC, overall_importance DESC, a.published_at DESC
        LIMIT 10
        """
        articles_result = run_cypher(articles_query, {"topic_id": topic_id})
    else:
        # Synthesis sections: 5 articles each from fundamental/medium/current
        all_articles = []
        for timeframe in ["fundamental", "medium", "current"]:
            timeframe_query = """
            MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
            WHERE r.timeframe = $timeframe
            WITH a, r,
                 CASE 
                   WHEN coalesce(r.importance_risk, 0) >= coalesce(r.importance_opportunity, 0) 
                        AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_trend, 0)
                        AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_catalyst, 0)
                   THEN coalesce(r.importance_risk, 0)
                   WHEN coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_trend, 0)
                        AND coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_catalyst, 0)
                   THEN coalesce(r.importance_opportunity, 0)
                   WHEN coalesce(r.importance_trend, 0) >= coalesce(r.importance_catalyst, 0)
                   THEN coalesce(r.importance_trend, 0)
                   ELSE coalesce(r.importance_catalyst, 0)
                 END as overall_importance
            RETURN a.id as article_id, a.published_at as published_at, 
                   overall_importance as numeric_importance,
                   r.timeframe as temporal_horizon,
                   r.motivation as motivation,
                   r.implications as implications
            ORDER BY numeric_importance DESC, a.published_at DESC
            LIMIT 5
            """
            timeframe_result = run_cypher(timeframe_query, {"topic_id": topic_id, "timeframe": timeframe})
            all_articles.extend(timeframe_result or [])
        articles_result = all_articles

    if not articles_result:
        logger.warning(
            f"⚠️  No articles found | topic={topic_id} section={section} | "
            f"Returning empty material - section will be skipped or use fallback"
        )
        # Return minimal material structure so analysis can continue
        return f"[No articles available for {section} section - enrichment needed]", []

    article_ids = [row["article_id"] for row in articles_result]

    # Add primary asset articles section
    material_parts.append("=" * 80)
    material_parts.append(f"PRIMARY ASSET ANALYSIS")
    material_parts.append("SOURCE ARTICLES")
    material_parts.append("=" * 80)

    # Load and format each article WITH motivation and implications
    section_counts = {}
    for i, row in enumerate(articles_result, 1):
        article_id = row["article_id"]
        horizon = row.get("temporal_horizon") or "unknown"
        motivation = row.get("motivation") or "No motivation available"
        implications = row.get("implications") or "No implications available"
        section_counts[horizon] = section_counts.get(horizon, 0) + 1
        
        try:
            loaded = load_article(article_id)
            # Try argos_summary first, fallback to summary, then description
            summary = None
            if loaded:
                summary = loaded.get("argos_summary") or loaded.get("summary") or loaded.get("description")
            if not loaded or not summary:
                raise ValueError(f"Article {article_id} missing summary")
            
            # NEW FORMAT: Include motivation and implications for forward-looking analysis
            material_parts.append(f"--- ARTICLE {i}: {article_id} ({horizon}) ---")
            material_parts.append(f"SUMMARY: {summary}")
            material_parts.append(f"WHY IT MATTERS: {motivation}")
            material_parts.append(f"IMPLICATIONS: {implications}")
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
