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

import os, sys
import re
import random
# Canonical import pattern: ensure project root is on sys.path when running this module directly
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pathlib import Path
from typing import List, Dict, Tuple

from utils.logging import get_logger
from utils.pipeline_logging import master_log, problem_log, master_statistics

from func_analysis.analysis_rewriter import SECTIONS, SECTION_FOCUS
from graph_utils.get_all_nodes import get_all_nodes
from graph_utils.get_node_by_id import get_node_by_id
from graph_db.db_driver import run_cypher
from utils.load_article import load_article
from paths import get_raw_news_dir

from func_add_article.add_article import add_article
from entry_point_enrich_topic.generate_keywords_llm import generate_keywords
from entry_point_enrich_topic.relevance_test_llm import relevance_gate_llm

logger = get_logger(__name__)

# Use only timeframe sections for sparsity checks
TIMEFRAME_SECTIONS = [s for s in SECTIONS if s in ("fundamental", "medium", "current")]


def _build_keyword_pattern(kw: str) -> "re.Pattern[str]":
    """Return a compiled regex matching kw with optional separators between tokens.
    - Lowercase kw, split on spaces/hyphens/slashes, escape parts, join with optional [-/\s].
    - Add loose non-alnum boundaries to avoid partial-word matches.
    """
    s = kw.lower().strip()
    parts = re.split(r"[-/\s]+", s)
    parts = [p for p in parts if p]
    if not parts:
        # Fallback to escaped whole kw
        inner = re.escape(s)
    else:
        inner = r"(?:[-/\s]?)".join(re.escape(p) for p in parts)
    pattern = rf"(?<![a-z0-9]){inner}(?![a-z0-9])"
    return re.compile(pattern)


def count_articles_for_topic_section(topic_id: str, section: str) -> int:
    """Return count of non-hidden articles linked to topic with temporal_horizon == section."""
    q = (
        "MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id}) "
        "WHERE a.temporal_horizon = $section AND coalesce(a.priority, '') <> 'hidden' "
        "RETURN count(a) AS c"
    )
    res = run_cypher(q, {"topic_id": topic_id, "section": section})
    number_of_articles = int(res[0]["c"]) if res else 0
    logger.info(f"count_articles_for_topic_section found {number_of_articles} articles for {topic_id} and {section}")
    return number_of_articles

def collect_candidates_by_keywords(
    keyword_list: List[str],
    max_articles: int = 5,
    min_keyword_hits: int = 3,
) -> List[Tuple[str, str]]:
    """
    Scan cold storage newest->oldest.
    Return up to max_articles of (article_id, full_text) for files where at least
    min_keyword_hits tokens from keyword_list appear in the text. Stops when max_articles reached.
    """
    base = get_raw_news_dir()
    days = [p for p in base.iterdir() if p.is_dir()]
    days_sorted = sorted(days, key=lambda p: p.name, reverse=True)

    # Prepare deduped, lowercase keywords and compile tolerant regex patterns once per call
    kw_lower: List[str] = []
    seen_kw: set[str] = set()
    for k in keyword_list:
        if not k:
            continue
        kk = k.lower()
        if kk in seen_kw:
            continue
        seen_kw.add(kk)
        kw_lower.append(kk)
    compiled = [(k, _build_keyword_pattern(k)) for k in kw_lower]
    matches: List[Tuple[str, str]] = []
    scanned = 0

    for day in days_sorted:
        for f in sorted(day.glob("*.json"), key=lambda p: p.name, reverse=True):
            scanned += 1
            # Load via canonical loader for consistency (fail-fast)
            article_id = f.stem
            loaded = load_article(article_id, max_days=365)
            title = loaded.get("title") or ""
            summary = loaded.get("summary") or loaded.get("description") or ""
            argos = loaded["argos_summary"]
            text = " ".join([title, summary, argos]).strip()
            text_l = text.lower()
            word_count = len(text_l.split())
            # Match each keyword at most once using tolerant patterns (space/hyphen/slash/none)
            matched_keywords = [k for (k, pat) in compiled if pat.search(text_l)]
            hits = len(matched_keywords)
            if hits > 0:
                logger.debug(
                    f"Keyword scan | id={article_id} | words={word_count} | hits={hits} (min={min_keyword_hits}) | tokens={matched_keywords}"
                )
            else:
                logger.debug(
                    f"Keyword scan | id={article_id} | words={word_count} | hits=0"
                )
            # Qualify only if we meet or exceed the minimum keyword hits
            if hits >= min_keyword_hits:
                matches.append((article_id, text))
                if len(matches) >= max_articles:
                    logger.info(
                        f"Keyword scan done | scanned={scanned} | found={len(matches)}"
                    )
                    return matches
    logger.info(
        f"Keyword scan done | scanned={scanned} | found={len(matches)}"
    )
    return matches


def backfill_topic_from_storage(
    topic_id: str,
    threshold: int = 2,
    max_articles_per_section: int = 5,
    min_keyword_hits: int = 3,
    test: bool = False,
    sections: list[str] | None = None,            # NEW
) -> int:
    """
    Enrich a single topic across selected sections (default: TIMEFRAME_SECTIONS) by scanning cold storage.
    Stateless API: requires only topic_id; resolves other fields via get_node_by_id().
    Returns total number of articles added for this topic.
    """
    topic = get_node_by_id(topic_id)
    topic_name = topic.get("name") or topic_id
    total_added = 0

    sections_to_run = sections if sections is not None else TIMEFRAME_SECTIONS  # NEW
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
        # We are attempting enrichment for this section
        master_statistics(enrichment_attempts=1)
        # Generate keywords
        keywords = generate_keywords(topic_name, section)
        logger.info(f"Generated {len(keywords)} keywords for topic={topic_name} section={section}: {keywords}")
        if not keywords:
            problem_log("Zero results", topic=topic_id)
            continue
        # Search cold storage...
        candidates = collect_candidates_by_keywords(
            keyword_list=keywords,
            max_articles=max_articles_per_section,
            min_keyword_hits=min_keyword_hits,
        )
        if not candidates:
            problem_log("Zero results", topic=topic_id)
            continue

        added = 0
        rel_checked = 0
        rel_passed = 0
        logger.info(
            f"Relevance checks starting | topic={topic_id} section={section} | candidates={len(candidates)} | needed={needed}"
        )
        for (article_id, article_text) in candidates:
            if added >= needed:
                break
            logger.info(f"Relevance check start | id={article_id} | section={section}")
            is_rel, _mot = relevance_gate_llm(topic_id, section, article_text)
            rel_checked += 1
            if not is_rel:
                logger.info(f"Relevance check fail | id={article_id}")
                continue
            logger.info(f"Relevance check pass | id={article_id}")
            rel_passed += 1
            # Add and explicitly link to the topic
            res = add_article(article_id, test=test, intended_topic_id=topic_id)
            # Count additions
            if res and res.get("status") not in ("skipped", "failed"):
                added += 1
                total_added += 1
                master_statistics(enrichment_articles_added=1)
                # Log informational message only; add_article already increments counters
                master_log(f"Backfill added | {article_id} -> {topic_id} | section={section}")
        # if no additions after candidates
        if added == 0:
            problem_log("Zero results", topic=topic_id)
        logger.info(
            f"Section summary | topic={topic_id} section={section} | candidates={len(candidates)} | rel_checked={rel_checked} | rel_passed={rel_passed} | added={added} | needed={needed}"
        )
        added_by_section[section] = added
        
        # Post-enrichment article count
        final_cnt = count_articles_for_topic_section(topic_id, section)
        logger.info(f"Post-enrichment | topic={topic_id} section={section} | final_articles={final_cnt} (was {cnt}, added {added})")
        
    # Topic-level enrichment summary with clear separators
    parts = []
    for s in sections_to_run:
        n = added_by_section.get(s, 0)
        parts.append(f"{n} new {s} article{'s' if n != 1 else ''}")
    summary_line = (
        f"Enrichment summary | topic={topic_id} ({topic_name}) | " + ", ".join(parts)
    )
    logger.info("=" * 100)
    logger.info(summary_line)
    logger.info("=" * 100)
    master_log(summary_line)
    
    # Trigger analysis check if articles were added
    if total_added > 0 and not test:
        from func_analysis.should_rewrite import should_rewrite
        logger.info(f"🎯 ANALYSIS TRIGGER | topic={topic_id} | enrichment added {total_added} articles, now checking if analysis rewrite needed")
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
            should_rewrite(topic_id, article_id)
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
    topics = get_all_nodes(["id", "name", "type"])  
    # Minimal fairness: shuffle to avoid always enriching the same first items
    random.shuffle(topics)
    logger.info(f"Starting enrichment over {len(topics)} topics")

    for t in topics:

        # Before backfill
        logger.info("=" * 100)
        logger.info(f"Processing topic        : {t['name']}")
        logger.info(f"Processing type         : {t.get('type')}")
        logger.info(f"Enrichment params       : threshold={threshold} | max_candidates={max_articles_per_section} | min_kw_hits={min_keyword_hits}")

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
