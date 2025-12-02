# analysis/should_rewrite.py

from src.analysis.policies.should_rewrite import should_rewrite_llm
from src.analysis.orchestration.analysis_rewriter import analysis_rewriter
from src.graph.neo4j_client import run_cypher
from utils import app_logging
from src.articles.load_article import load_article
from src.observability.pipeline_logging import master_log
from src.observability.pipeline_logging import master_statistics
from src.observability.pipeline_logging import problem_log, Problem, ProblemDetailsModel

# NEW imports for TF handling
from src.graph.ops.article import get_article_temporal_horizon
from src.analysis.policies.time_frame_identifier import find_time_frame
from src.analysis.types import RewriteInfo

logger = app_logging.get_logger(__name__)


def should_rewrite(
    topic_id: str, new_article_id: str, test: bool = False, triggered_by: str = "article"
) -> RewriteInfo:
    """
    Orchestrator: builds analysis+article text, LLM judge, targeted rewrite by temporal_horizon section.
    Returns dict: {'should_rewrite': bool, 'motivation': str, 'section': str}
    """
    logger.info(f"Starting should_rewrite for topic_id={topic_id}")

    # Track entry and trigger source
    if triggered_by == "enrichment":
        master_statistics(
            should_rewrite_attempted=1,
            should_rewrite_trigger_from_enrichment_completion=1
        )
    else:
        master_statistics(
            should_rewrite_attempted=1,
            should_rewrite_trigger_from_article_ingestion=1
        )

    topic_cypher = """
    MATCH (t:Topic {id: $topic_id})
    RETURN t.name as name, t.fundamental_analysis as fundamental_analysis, t.medium_analysis as medium_analysis, t.current_analysis as current_analysis
    """
    topic = run_cypher(topic_cypher, {"topic_id": topic_id})
    if not topic:
        logger.warning(f"Topic {topic_id} not found for should_rewrite.")
        # Topic not found - no specific tracking for this
        return {
            "should_rewrite": False,
            "motivation": "Topic not found",
            "section": None,
        }

    topic_name = topic[0].get("name", topic_id)  # Fallback to topic_id if no name
    analysis_fields = {
        k: topic[0][k]
        for k in [
            "fundamental_analysis",
            "medium_analysis",
            "current_analysis",
        ]
        if topic[0][k]
    }

    # Format analysis fields
    analysis_text = []
    for section, label in zip(
        ["fundamental_analysis", "medium_analysis", "current_analysis"],
        [
            "Fundamental Analysis",
            "Medium-Term Analysis",
            "Current Analysis",
        ],
    ):
        val = analysis_fields.get(section)  # Use .get() to handle missing keys
        analysis_text.append(f"{label}:\n{val}" if val else f"{label}: Not available")
    analysis_text_str = "\n\n".join(analysis_text)

    # Load article and require existing argos_summary (no LLM fallback)
    article = load_article(new_article_id)

    if article:
        if "argos_summary" not in article:
            p = ProblemDetailsModel()
            p.article_id = new_article_id
            problem_log(
                Problem.MISSING_SUMMARY_FOR_SHOULD_REWRITE, topic=topic_id, details=p
            )
            return {
                "should_rewrite": False,
                "motivation": "No argos_summary available",
                "section": None,
            }
        summary = article["argos_summary"]

    # Determine temporal horizon -> section (from relationship, not article node)
    tf_query = """
    MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
    RETURN r.timeframe as timeframe
    """
    tf_result = run_cypher(tf_query, {"article_id": new_article_id, "topic_id": topic_id})
    
    if not tf_result or not tf_result[0].get("timeframe"):
        logger.warning(
            f"Article {new_article_id} -> Topic {topic_id} relationship missing timeframe. This shouldn't happen with new system."
        )
        # Fallback: infer from summary
        time_frame_result = find_time_frame(summary)
        tf_section = time_frame_result.horizon
        logger.warning(f"Using inferred timeframe: {tf_section}")
    else:
        tf_section = tf_result[0]["timeframe"]

    # LLM decision (tuple: (bool, str))
    try:
        should_rewrite_flag, motivation = should_rewrite_llm(
            analysis_text_str, summary, topic_name, test=test
        )

        if should_rewrite_flag is True:
            master_log(
                f"Will rewrite section {tf_section} because response was: True | topic={topic_id} | article={new_article_id}"
            )
            master_statistics(should_rewrite_true=1)
            
            # Try analysis generation
            try:
                analysis_rewriter(topic_id, test=test, analysis_type=tf_section)
                master_statistics(analysis_sections_written=1)  # Track successful completion
            except Exception as e:
                logger.error(f"Analysis rewriter failed for {topic_id}: {e}")
                master_statistics(errors=1)  # Track failure as error
        else:
            master_log(
                f"No rewrite of section {tf_section} because response was: False | topic={topic_id} | article={new_article_id}"
            )
            master_statistics(should_rewrite_false=1)
    except Exception as e:
        logger.error(f"Should rewrite LLM call failed for {topic_id}: {e}")
        master_statistics(errors=1)  # LLM failure is an error
        return {
            "should_rewrite": False,
            "motivation": f"LLM call failed: {str(e)}",
            "section": tf_section,
        }

    # Always run cross-section check
    if not test:
        _check_and_enrich_other_sections(topic_id, tf_section, test=test)

    return {
        "should_rewrite": bool(should_rewrite_flag),
        "motivation": motivation,
        "section": tf_section,
    }


def _check_and_enrich_other_sections(
    topic_id: str, current_section: str, test: bool = False
) -> None:
    """
    Check ALL sections for missing analysis. Handle timeframe vs non-timeframe sections differently.
    """
    from worker.workflows.topic_enrichment import (
        backfill_topic_from_storage,
        count_articles_for_topic_section,
    )

    # Timeframe sections - check individually
    timeframe_sections = ["fundamental", "medium", "current"]
    other_timeframe = [s for s in timeframe_sections if s != current_section]

    for section in other_timeframe:
        analysis_query = (
            f"MATCH (t:Topic {{id: $topic_id}}) RETURN t.{section}_analysis as analysis"
        )
        result = run_cypher(analysis_query, {"topic_id": topic_id})

        if not result or not result[0]["analysis"]:
            count = count_articles_for_topic_section(topic_id, section)
            if count < 2:
                logger.info(
                    f"Enriching {section} section for {topic_id} (count={count})"
                )
                added = backfill_topic_from_storage(
                    topic_id=topic_id, threshold=1, sections=[section], test=test
                )
                if added > 0:
                    analysis_rewriter(topic_id, test=test, analysis_type=section)
            elif count >= 2:
                logger.info(
                    f"Sufficient articles for {section} ({count}); triggering analysis"
                )
                analysis_rewriter(topic_id, test=test, analysis_type=section)

    # Non-timeframe sections - check based on total article count
    non_timeframe_sections = [
        "drivers",
        "movers_scenarios",
        "swing_trade_or_outlook",
        "executive_summary",
    ]

    # Get total article count across all timeframe sections (from relationships)
    total_query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
    WHERE r.timeframe IN ['fundamental', 'medium', 'current']
    RETURN count(a) as total_count
    """
    total_result = run_cypher(total_query, {"topic_id": topic_id})
    total_count = total_result[0]["total_count"] if total_result else 0

    # Check if we have minimum articles per timeframe section
    min_per_section = all(
        count_articles_for_topic_section(topic_id, s) >= 2 for s in timeframe_sections
    )

    if total_count >= 3 and min_per_section:
        # Sufficient articles for non-timeframe sections
        for section in non_timeframe_sections:
            analysis_query = (
                f"MATCH (t:Topic {{id: $topic_id}}) RETURN t.{section} as analysis"
            )
            result = run_cypher(analysis_query, {"topic_id": topic_id})

            if not result or not result[0]["analysis"]:
                logger.info(
                    f"Triggering {section} analysis for {topic_id} (total_count={total_count})"
                )
                analysis_rewriter(topic_id, test=test, analysis_type=section)
    elif total_count < 3:
        # Need more articles overall - enrich all timeframe sections
        logger.info(
            f"Total count {total_count} < 3; enriching timeframe sections for {topic_id}"
        )
        added = backfill_topic_from_storage(
            topic_id=topic_id, threshold=2, sections=timeframe_sections, test=test
        )
        if added > 0:
            # Re-check after enrichment
            _check_and_enrich_other_sections(topic_id, current_section, test=test)
