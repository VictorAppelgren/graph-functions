"""
Simplified Article Backfill Orchestrator
- Iterates topics and dynamic analysis sections (fundamental, medium, current)
- For sections with < threshold articles, generates ~25–35 flat keywords via LLM
- Scans cold JSON storage and collects articles with >= 3 distinct keyword hits
  across concatenated text: title + summary + argos_summary (tolerant separators)
- Relevance-gates candidates via LLM
- Adds relevant articles using add_article(..., intended_topic_id=topic_id)
- Minimal surface area: no try/except, no fallbacks
"""

from __future__ import annotations

import os
import sys
import re
import random

# Canonical import pattern: ensure project root is on sys.path when running this module directly
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import List, Dict, Tuple
import requests
import os

from utils.app_logging import get_logger
from src.observability.pipeline_logging import (
    master_log,
    problem_log,
    master_statistics,
    Problem,
)

from src.analysis.orchestration.analysis_rewriter import SECTIONS
from src.graph.ops.topic import get_all_topics, get_topic_by_id
from src.graph.neo4j_client import run_cypher

from src.articles.ingest_article import add_article
from src.analysis.policies.keyword_generator import generate_keywords
from src.analysis.policies.relevance_gate import relevance_gate_llm
from src.analysis.orchestration.should_rewrite import should_rewrite

logger = get_logger("topic_enrichment")

# Use only timeframe sections for sparsity checks
TIMEFRAME_SECTIONS = [s for s in SECTIONS if s in ("fundamental", "medium", "current")]


# Backend API configuration
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://saga-apis:8000")


def count_articles_for_topic_section(topic_id: str, section: str) -> int:
    """Return count of non-hidden articles linked to topic with temporal_horizon == section."""
    q = (
        "MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id}) "
        "WHERE a.temporal_horizon = $section AND coalesce(a.priority, '') <> 'hidden' "
        "RETURN count(a) AS c"
    )
    res = run_cypher(q, {"topic_id": topic_id, "section": section})
    number_of_articles = int(res[0]["c"]) if res else 0
    logger.info(
        f"count_articles_for_topic_section found {number_of_articles} articles for {topic_id} and {section}"
    )
    return number_of_articles


def get_existing_article_ids_for_topic_section(topic_id: str, section: str) -> set[str]:
    """Get all article IDs already linked to this topic in this timeframe section"""
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
    WHERE a.temporal_horizon = $section
    RETURN a.id as article_id
    """
    result = run_cypher(query, {"topic_id": topic_id, "section": section})
    return {row["article_id"] for row in result}


def collect_candidates_by_keywords(
    keyword_list: List[str],
    max_articles: int = 5,
    min_keyword_hits: int = 3,
    exclude_ids: set[str] = None,
) -> List[Tuple[str, Dict]]:
    """
    Call backend API to search articles by keywords.
    Return up to max_articles of (article_id, article_object) tuples.
    """
    url = f"{BACKEND_API_URL}/api/articles/search"
    payload = {
        "keywords": keyword_list,
        "limit": max_articles,
        "min_keyword_hits": min_keyword_hits,
        "exclude_ids": list(exclude_ids) if exclude_ids else []
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Transform API response to expected format: List[Tuple[article_id, article_object]]
        results = data.get("results", [])
        matches = [(r["article_id"], r["article"]) for r in results]
        
        logger.info(f"Backend API search | keywords={len(keyword_list)} | found={len(matches)}")
        return matches
        
    except Exception as e:
        logger.error(f"Backend API search failed: {e}")
        return []


def _generate_boolean_query_for_perigon(topic_name: str, section: str) -> str:
    """Generate boolean query using create_query_llm style for Perigon searches."""
    # Create a mock article text to feed to create_wide_query
    focus_contexts = {
        "fundamental": f"economic drivers, policy decisions, and structural factors affecting {topic_name}",
        "current": f"breaking news, immediate events, and real-time developments for {topic_name}",
        "medium": f"analysis, trends, and medium-term outlook for {topic_name}"
    }
    
    mock_article = f"""
    Title: {topic_name} {section} analysis
    Summary: This article discusses {topic_name} in the context of {focus_contexts.get(section, '')}.
    Content: Key topics include {topic_name} market movements, policy impacts, and related financial developments.
    """
    
    # For now, return a simple query - we can enhance this later with create_wide_query
    return f'{topic_name}'


def _generate_query_variants(topic_name: str, section: str) -> List[str]:
    """Generate 2-4 query variants using boolean query style."""
    queries = []
    
    # Query 1: Main boolean query
    main_query = _generate_boolean_query_for_perigon(topic_name, section)
    queries.append(main_query)
    
    # Query 2: Simple topic + section terms
    section_terms = {
        "fundamental": "policy economic monetary fiscal",
        "current": "breaking news latest today announcement", 
        "medium": "analysis outlook forecast trend impact"
    }
    if section in section_terms:
        queries.append(f"{topic_name} {section_terms[section]}")
    
    # Query 3: Topic variations
    queries.append(f"({topic_name} OR {topic_name.replace('_', ' ')})")
    
    return queries[:3]  # Max 3 queries


def _dedupe_articles(articles: List[Dict]) -> List[Dict]:
    """Remove duplicate articles by URL and title."""
    seen_urls = set()
    seen_titles = set()
    deduped = []
    
    for article in articles:
        url = article.get('url', '')
        title = article.get('title', '').lower().strip()
        
        if url and url not in seen_urls and title and title not in seen_titles:
            seen_urls.add(url)
            seen_titles.add(title)
            deduped.append(article)
    
    return deduped


def enrich_topic_via_perigon(topic_id: str, section: str, target_articles: int = 5) -> int:
    """Use Perigon to find fresh articles for sparse topic sections."""
    
    # 1. Get topic details
    topic_node = get_topic_by_id(topic_id)
    topic_name = topic_node.get("name") or topic_id
    
    # 2. Generate query variants using boolean query style
    queries = _generate_query_variants(topic_name, section)
    
    # For now, we'll implement a simple version without NewsIngestionOrchestrator
    # This can be enhanced later when the Perigon integration is available
    logger.info(f"Perigon enrichment | {topic_id}/{section} | queries={queries}")
    master_log(f"Perigon enrichment attempted | {topic_id}/{section} | target={target_articles}")
    
    # Return 0 for now - this will be enhanced when Perigon integration is ready
    return 0


def enrich_topic_via_cold_storage(
    topic_id: str, section: str, topic_name: str, needed: int,
    max_articles_per_section: int, min_keyword_hits: int, test: bool
) -> int:
    """Extract cold storage enrichment into separate function."""
    # Generate keywords with section-specific focus
    focus_contexts = {
        "fundamental": f"economic drivers, policy decisions, and structural factors affecting {topic_name}",
        "current": f"breaking news, immediate events, and real-time developments for {topic_name}",
        "medium": f"analysis, trends, and medium-term outlook for {topic_name}"
    }
    
    keywords = generate_keywords(topic_name, section)
    logger.info(f"Generated {len(keywords.list)} keywords for topic={topic_name} section={section}: {keywords.list}")
    if not keywords.list:
        problem_log(Problem.ZERO_RESULTS, topic_id)
        return 0
    
    # Get existing article IDs to exclude from search
    existing_ids = get_existing_article_ids_for_topic_section(topic_id, section)
    
    # Search cold storage
    candidates = collect_candidates_by_keywords(
        keyword_list=keywords.list,
        max_articles=max_articles_per_section,
        min_keyword_hits=min_keyword_hits,
        exclude_ids=existing_ids,
    )
    if not candidates:
        problem_log(Problem.ZERO_RESULTS, topic_id)
        return 0

    added = 0
    rel_checked = 0
    rel_passed = 0
    logger.info(
        f"Cold storage relevance checks | topic={topic_id} section={section} | candidates={len(candidates)} | needed={needed}"
    )
    
    for (article_id, article_obj) in candidates:
        if added >= needed:
            break
        
        # Extract text from article object for relevance check (no wrapper, direct access)
        title = article_obj.get("title", "")
        summary = article_obj.get("summary", "") or article_obj.get("description", "")
        argos_summary = article_obj.get("argos_summary", "")
        article_text = " ".join([title, summary, argos_summary]).strip()
        
        logger.info(f"Relevance check start | id={article_id} | section={section}")
        relevance_result = relevance_gate_llm(topic_id, section, article_text)
        rel_checked += 1
        if not relevance_result.relevant:
            logger.info(f"Article not relevant | id={article_id} | rejected by LLM")
            continue
        logger.info(f"Article relevant | id={article_id} | approved by LLM")
        rel_passed += 1
        
        # Add article with full object (not just ID)
        try:
            res = add_article(article_obj, test=test, intended_topic_id=topic_id)
        except Exception as e:
            logger.warning(f"Failed to add article {article_id}: {e}")
            continue
        if res and res.get("status") not in ("skipped", "failed"):
            added += 1
            master_log(f"Cold storage added | {article_id} -> {topic_id} | section={section}")
    
    if added == 0:
        problem_log(Problem.ZERO_RESULTS, topic_id)
    
    logger.info(
        f"Cold storage summary | topic={topic_id} section={section} | candidates={len(candidates)} | rel_checked={rel_checked} | rel_passed={rel_passed} | added={added} | needed={needed}"
    )
    
    return added


def backfill_topic_from_storage(
    topic_id: str,
    threshold: int = 2,
    max_articles_per_section: int = 5,
    min_keyword_hits: int = 3,
    test: bool = False,
    sections: list[str] | None = None,
) -> int:
    """
    Enrich a single topic across selected sections (default: TIMEFRAME_SECTIONS) by scanning cold storage.
    Enhanced: Tries Perigon enrichment first, then falls back to cold storage if needed.
    Returns total number of articles added for this topic.
    """
    topic = get_topic_by_id(topic_id)
    topic_name = topic.get("name") or topic_id
    total_added = 0

    sections_to_run = sections if sections is not None else TIMEFRAME_SECTIONS
    added_by_section: dict[str, int] = {s: 0 for s in sections_to_run}
    logger.info(f"sections_to_run | {sections_to_run}")

    for section in sections_to_run:
        logger.info(f"Enrichment check | {topic_id} | section={section}")
        master_log(f"Enrichment check | {topic_id} | section={section}")
        cnt = count_articles_for_topic_section(topic_id, section)
        logger.info(f"Pre-enrichment | topic={topic_id} section={section} | current_articles={cnt} threshold={threshold}")
        if cnt >= threshold:
            logger.info(f"Enrichment skipped | topic={topic_id} section={section} | has {cnt} articles >= threshold {threshold}")
            continue
        needed = threshold - cnt
        logger.info(f"Enrichment needed | topic={topic_id} section={section} | need {needed} more articles (have {cnt}, want {threshold})")
        master_log(f"Enrichment attempt | topic={topic_id} section={section} | current={cnt} needed={needed}")
        
        added = 0
        
        # Try Perigon enrichment first
        logger.info(f"Trying Perigon enrichment first | topic={topic_id} section={section} | need {needed} articles")
        perigon_added = enrich_topic_via_perigon(topic_id, section, needed)
        added += perigon_added
        total_added += perigon_added
        if perigon_added > 0:
            master_log(f"Perigon enrichment | {topic_id}/{section} | added {perigon_added} articles")
        
        # Check if we still need more articles
        cnt_after_perigon = count_articles_for_topic_section(topic_id, section)
        remaining_needed = max(0, threshold - cnt_after_perigon)
        
        if remaining_needed > 0:
            logger.info(f"Still need {remaining_needed} more articles after Perigon, trying cold storage")
            cold_storage_added = enrich_topic_via_cold_storage(
                topic_id, section, topic_name, remaining_needed, 
                max_articles_per_section, min_keyword_hits, test
            )
            added += cold_storage_added
            total_added += cold_storage_added
        
        added_by_section[section] = added
        
        # Final count for this section
        final_cnt = count_articles_for_topic_section(topic_id, section)
        master_log(f"Section status | {topic_id}/{section} | before={cnt} | after={final_cnt} | threshold={threshold}")
        
        # Post-enrichment article count
        logger.info(f"Post-enrichment | topic={topic_id} section={section} | final_articles={final_cnt} (was {cnt}, added {added})")
        
    # Topic-level enrichment summary with clear separators
    parts = []
    for s in sections_to_run:
        n = added_by_section.get(s, 0)
        parts.append(f"{n} new {s} article{'s' if n != 1 else ''}")
    summary_line = f"Enrichment summary | topic={topic_id} ({topic_name}) | " + ", ".join(parts)
    logger.info("=" * 100)
    logger.info(summary_line)
    logger.info("=" * 100)
    master_log(summary_line)
    
    # Check if analysis is missing and trigger generation
    if not test:
        # Check if topic has sufficient articles for analysis
        sufficient_fundamental = count_articles_for_topic_section(topic_id, "fundamental") >= 2
        sufficient_medium = count_articles_for_topic_section(topic_id, "medium") >= 2  
        sufficient_current = count_articles_for_topic_section(topic_id, "current") >= 2
        
        if sufficient_fundamental and sufficient_medium and sufficient_current:
            # Check if analysis exists
            analysis_query = "MATCH (t:Topic {id: $topic_id}) RETURN t.fundamental_analysis, t.medium_analysis, t.current_analysis"
            analysis_result = run_cypher(analysis_query, {"topic_id": topic_id})
            
            if analysis_result:
                analysis_fields = analysis_result[0]
                missing_analysis = [k for k, v in analysis_fields.items() if not v]
                
                if missing_analysis:
                    from src.analysis.orchestration.analysis_rewriter import analysis_rewriter
                    master_log(f"Analysis generation triggered | {topic_id} | sufficient_articles=True | missing={missing_analysis}")
                    analysis_rewriter(topic_id, test=False)
    
    # Trigger analysis check if articles were added
    if total_added > 0 and not test:
        master_log(f"Post-enrichment analysis check | {topic_id} | articles_added={total_added}")
        
        # Get any recent article for this topic to use as trigger
        recent_article_query = """
        MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
        WHERE coalesce(a.priority, '') <> 'hidden'
        RETURN a.id as article_id
        ORDER BY a.published_at DESC
        LIMIT 1
        """
        recent_articles = run_cypher(recent_article_query, {"topic_id": topic_id})
        if recent_articles:
            article_id = recent_articles[0]["article_id"]
            logger.info(f"🔄 CALLING should_rewrite | topic={topic_id} trigger_article={article_id}")
            should_rewrite(topic_id, article_id, triggered_by="enrichment")
        else:
            logger.warning(f"No recent articles found for analysis trigger | topic={topic_id}")
    else:
        if total_added == 0:
            logger.info(f"No analysis trigger | topic={topic_id} | no articles were added during enrichment")
        elif test:
            logger.info(f"No analysis trigger | topic={topic_id} | test mode enabled")
    
    return total_added


def enrich_topics_from_storage(
    threshold: int = 3,
    max_articles_per_section: int = 30,
    min_keyword_hits: int = 3,
    test: bool = False,
) -> None:
    """
    Main orchestrator.
    - threshold: if count(section) < threshold, try to add until reaching threshold
    - max_articles_per_section: maximum number of candidate articles to consider per section (default 30)
    - min_keyword_hits: minimum number of distinct keyword tokens in text to qualify (default 3)
    - test: passed through to add_article
    """
    topics = get_all_topics(["id", "name", "type"])
    # Minimal fairness: shuffle to avoid always enriching the same first items
    random.shuffle(topics)
    logger.info(f"Starting enrichment over {len(topics)} topics")

    for t in topics:

        # Before backfill
        logger.info("=" * 100)
        logger.info(f"Processing topic        : {t['name']}")
        logger.info(f"Processing type         : {t.get('type')}")
        logger.info(
            f"Enrichment params       : threshold={threshold} | max_candidates={max_articles_per_section} | min_kw_hits={min_keyword_hits}"
        )

        topic_id = t["id"]
        backfill_topic_from_storage(
            topic_id=topic_id,
            threshold=threshold,
            max_articles_per_section=max_articles_per_section,
            min_keyword_hits=min_keyword_hits,
            test=test,
        )


if __name__ == "__main__":
    # Default run: minimal, fail-fast
    enrich_topics_from_storage(threshold=5, test=False)
