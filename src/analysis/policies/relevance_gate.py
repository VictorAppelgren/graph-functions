from typing import Tuple
from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.analysis.orchestration.analysis_rewriter import SECTION_FOCUS
from src.graph.ops.topic import get_topic_by_id
from src.graph.neo4j_client import run_cypher
from utils.app_logging import get_logger
import time
from src.articles.load_article import load_article
from src.llm.prompts.relevance_gate_llm import relevance_gate_llm_prompt
from src.llm.sanitizer import run_llm_decision, RelevanceGate

logger = get_logger(__name__)


def _fetch_existing_section_summaries(
    topic_id: str, section: str, limit: int = 10
) -> list[tuple[str, str]]:
    if not topic_id or not isinstance(topic_id, str):
        raise ValueError("topic_id is required")
    if section not in SECTION_FOCUS:
        raise KeyError(f"Unknown section: {section}")
    q = (
        "MATCH (a:Article)-[:ABOUT]->(t:Topic {id:$topic_id}) "
        "WHERE a.temporal_horizon = $section AND coalesce(a.priority, '') <> 'hidden' "
        "RETURN a.id AS id "
        "ORDER BY a.published_at DESC LIMIT $limit"
    )
    logger.info(
        "========== about to perform cypher for getting all connected nodes =========="
    )
    logger.info(
        f"Existing coverage fetch | topic={topic_id} section={section} | limit={limit}"
    )
    rows = (
        run_cypher(q, {"topic_id": topic_id, "section": section, "limit": int(limit)})
        or []
    )
    logger.info(
        f"Existing coverage fetch | topic={topic_id} section={section} | rows={len(rows)}"
    )
    logger.info(
        "========== Done performing cypher for getting all connected nodes =========="
    )

    out: list[tuple[str, str]] = []
    for r in rows:
        aid = r["id"]
        try:
            art = load_article(aid)
        except Exception as e:
            logger.warning(f"Cold storage load failed | id={aid} | err={e}")
            continue
        # Prefer argos_summary; fallback to common summary-like fields

        if art:
            title = (art.get("title") if isinstance(art, dict) else None) or aid
            summ_source = art["source"]
            summ = art["argos_summary"]
            logger.info(
                f"Existing coverage item | id={aid} | title={title} | src={summ_source} | summary_len={len(summ)} | preview={summ[:200]}"
            )
            out.append((title, summ))
    return out


def relevance_gate_llm(
    topic_id: str, section: str, article_text: str
) -> RelevanceGate:
    """Return (is_relevant, motivation) by comparing candidate vs current section coverage.

    Inputs are IDs-only for context lookups (SAGA_V3).
    """
    if not topic_id or not isinstance(topic_id, str):
        raise ValueError("topic_id is required")
    if section not in SECTION_FOCUS:
        raise KeyError(f"Unknown section: {section}")
    if not article_text or not isinstance(article_text, str):
        raise ValueError("article_text is required")

    focus = SECTION_FOCUS[section]
    topic_node = get_topic_by_id(topic_id)
    topic_name = (
        topic_node["name"]
        if ("name" in topic_node and topic_node["name"])
        else topic_id
    )
    logger.info(
        f"Relevance gate start | topic={topic_id}({topic_name}) section={section} | article_len_chars={len(article_text)} | article_len_words={len(article_text.split())}"
    )
    existing = _fetch_existing_section_summaries(topic_id, section, limit=8)
    if existing:
        existing_block = "\n".join(
            [
                f"- {i+1}) {title}: {summary}"
                for i, (title, summary) in enumerate(existing)
            ]
        )
    else:
        existing_block = "(none found)"
    logger.info(
        f"Existing coverage items included: {len(existing)} | existing_block_chars={len(existing_block)}"
    )

    llm = get_llm(ModelTier.SIMPLE)

    prompt = PromptTemplate.from_template(relevance_gate_llm_prompt).format(
        article_text=article_text,
        topic_name=topic_name,
        focus=SECTION_FOCUS[section],
        existing_summaries=existing_block,
        system_mission=SYSTEM_MISSION,
        system_context=SYSTEM_CONTEXT
    )

    result = run_llm_decision(chain=llm, prompt=prompt, model=RelevanceGate)
    
    # Track LLM call
    from src.observability.pipeline_logging import master_statistics
    master_statistics(llm_simple_calls=1)
    
    return result
