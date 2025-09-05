"""
Builds formatted SOURCE MATERIAL for analysis rewriting, using summaries-only plus minimal metadata.
- Loads full article JSON via utils.load_article.load_article
- Requires existing argos_summary (strict); no fallbacks.
- Per-article output includes exactly: Title, Published, optional Source, and Summary.
- No URL or ID lines are included. Keeps prompts small and robust.
"""
from __future__ import annotations
from typing import List, Tuple, Dict, Any

from utils import minimal_logging
logger = minimal_logging.get_logger(__name__)

from func_analysis.best_articles_selector import select_best_articles
from utils.load_article import load_article
 

def build_material_for_section(topic_id: str, section: str) -> Tuple[str, List[str]]:
    """
    Build the formatted SOURCE MATERIAL string and the ordered list of article IDs used.

    Strategy (fail-fast, minimal):
    - Use select_best_articles(topic_id, section) ONLY. If none, raise.
    - For each article id, load cold-storage JSON and use existing summary (argos_summary/summary) only.
    - Compose an entry per article with prominent ID for in-text citations.

    Returns:
      material_str: The fully formatted material string (may be very long; never truncated here).
      article_ids: Ordered list of IDs included.
    """
    # 1) Select candidate articles (no fallbacks)
    selected = select_best_articles(topic_id, section)
    if not selected:
        from utils.master_log import problem_log
        problem_log("rewrites_skipped_0_articles", topic=topic_id, details={"section": section})
        raise ValueError(f"No articles selected for topic_id={topic_id} section={section}")

    lines: List[str] = []
    article_ids: List[str] = []

    for meta in selected:
        aid = meta["id"]

        article_ids.append(aid)
        loaded: Dict[str, Any] = load_article(aid)

        # Strict required fields: title, pubDate, argos_summary
        missing: list[str] = []
        if "title" not in loaded:
            missing.append("title")
        if "pubDate" not in loaded:
            missing.append("pubDate")
        if "argos_summary" not in loaded:
            missing.append("argos_summary")
        if missing:
            from utils.master_log import problem_log
            problem_log(
                "missing_required_fields_for_analysis_material",
                topic=topic_id,
                details={"section": section, "article_id": aid, "missing": missing},
            )
            continue

        title = loaded["title"]
        published = loaded["pubDate"]
        summary = loaded["argos_summary"]

        # Compose minimal entry
        lines.append("===== ARTICLE START =====")
        lines.append(f"Title: {title}")
        lines.append(f"Published: {published}")
        if "source" in loaded:
            lines.append(f"Source: {loaded['source']}")
        lines.append("Summary:")
        lines.append(str(summary))
        lines.append("===== ARTICLE END =====\n")

    if not lines:
        from utils.master_log import problem_log
        problem_log("rewrites_skipped_0_articles_summary_only", topic=topic_id, details={"section": section})
        raise ValueError(f"No article summaries available for topic_id={topic_id} section={section}")

    material = "\n".join(lines).strip()
    logger.info(
        f"build_material_for_section | topic_id={topic_id} section={section} articles={len(article_ids)} chars={len(material)}"
    )
    return material, article_ids


def build_material_for_synthesis_section(topic_id: str, section: str) -> Tuple[str, List[str]]:
    """
    Build material for synthesis sections using BOTH existing analysis AND all articles.
    Perfect formatting for research-grade synthesis.
    
    Returns:
        material_str: Formatted material with analysis sections + all articles
        article_ids: List of article IDs used
    """
    from graph_db.db_driver import run_cypher
    
    # Get existing analysis sections
    analysis_query = """
    MATCH (t:Topic {id: $topic_id})
    RETURN t.fundamental_analysis, t.medium_analysis, t.current_analysis, t.implications
    """
    analysis_result = run_cypher(analysis_query, {"topic_id": topic_id})
    
    material_parts = []
    
    # Format existing analysis sections with perfect presentation
    if analysis_result and analysis_result[0]:
        analysis_data = analysis_result[0]
        
        material_parts.append("=" * 80)
        material_parts.append("EXISTING ANALYSIS SECTIONS")
        material_parts.append("=" * 80)
        
        for field, label in [
            ("fundamental_analysis", "FUNDAMENTAL ANALYSIS (Multi-year Structural)"),
            ("medium_analysis", "MEDIUM-TERM ANALYSIS (3-6 months)"), 
            ("current_analysis", "CURRENT ANALYSIS (0-3 weeks)"),
            ("implications", "IMPLICATIONS")
        ]:
            analysis_content = analysis_data.get(field)
            if analysis_content:
                material_parts.append(f"\n--- {label} ---")
                material_parts.append(str(analysis_content))
                material_parts.append("")
    
    # Get ALL article IDs for this topic from graph
    articles_query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
    WHERE coalesce(a.priority, '') <> 'hidden'
    RETURN a.id as article_id, a.pubDate as published_at
    ORDER BY a.pubDate DESC
    """
    articles_result = run_cypher(articles_query, {"topic_id": topic_id})
    
    if not articles_result:
        raise ValueError(f"No articles found for topic_id={topic_id}")
    
    article_ids = [row["article_id"] for row in articles_result]
    
    # Add articles section
    material_parts.append("=" * 80)
    material_parts.append("SOURCE ARTICLES")
    material_parts.append("=" * 80)
    
    for i, row in enumerate(articles_result, 1):
        article_id = row["article_id"]
        
        try:
            # Load article using the canonical utility
            loaded = load_article(article_id)
            
            # Strict requirements for synthesis
            if "title" not in loaded or "argos_summary" not in loaded or "pubDate" not in loaded:
                logger.warning(f"Skipping article {article_id}: missing required fields")
                continue
                
            title = loaded["title"]
            published = loaded["pubDate"]
            argos_summary = loaded["argos_summary"]
            
            # Perfect formatting for synthesis
            material_parts.append(f"\n--- ARTICLE {i}: {article_id} ---")
            material_parts.append(f"Title: {title}")
            material_parts.append(f"Published: {published}")
            if "source" in loaded:
                material_parts.append(f"Source: {loaded['source']}")
            material_parts.append("Summary:")
            material_parts.append(str(argos_summary))
            material_parts.append("")
            
        except Exception as e:
            logger.warning(f"Failed to load article {article_id}: {e}")
            continue
    
    material = "\n".join(material_parts).strip()
    
    logger.info(
        f"build_material_for_synthesis_section | topic_id={topic_id} section={section} | "
        f"articles={len(article_ids)} chars={len(material)}"
    )
    
    return material, article_ids
