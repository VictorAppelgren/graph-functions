from typing import Tuple
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.analysis.orchestration.analysis_rewriter import SECTIONS, SECTION_FOCUS
from src.graph.ops.topic import get_topic_node_by_id
from src.graph.neo4j_client import run_cypher
from utils.app_logging import get_logger
import time
from src.articles.load_article import load_article

logger = get_logger(__name__)

def _fetch_existing_section_summaries(topic_id: str, section: str, limit: int = 10) -> list[tuple[str, str]]:
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
    logger.info(f"========== about to perform cypher for getting all connected nodes ==========")
    logger.info(f"Existing coverage fetch | topic={topic_id} section={section} | limit={limit}")
    rows = run_cypher(q, {"topic_id": topic_id, "section": section, "limit": int(limit)}) or []
    logger.info(f"Existing coverage fetch | topic={topic_id} section={section} | rows={len(rows)}")
    logger.info(f"========== Done performing cypher for getting all connected nodes ==========")

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
            summ_source = art['source']
            summ = art["argos_summary"]
            logger.info(
                f"Existing coverage item | id={aid} | title={title} | src={summ_source} | summary_len={len(summ)} | preview={summ[:200]}"
            )
            out.append((title, summ))
    return out


def relevance_gate_llm(topic_id: str, section: str, article_text: str) -> Tuple[bool, str]:
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
    topic_node = get_topic_node_by_id(topic_id)
    topic_name = topic_node["name"] if ("name" in topic_node and topic_node["name"]) else topic_id
    logger.info(
        f"Relevance gate start | topic={topic_id}({topic_name}) section={section} | article_len_chars={len(article_text)} | article_len_words={len(article_text.split())}"
    )
    existing = _fetch_existing_section_summaries(topic_id, section, limit=8)
    if existing:
        existing_block = "\n".join([f"- {i+1}) {title}: {summary}" for i, (title, summary) in enumerate(existing)])
    else:
        existing_block = "(none found)"
    logger.info(f"Existing coverage items included: {len(existing)} | existing_block_chars={len(existing_block)}")

    prompt_template = """
    THE KNOWLEDGE SYSTEM YOU ARE WORKING WITH AIMS TO DO THE FOLLOWING:
    {system_mission}
    {system_context}

    You are a strict relevance gate for topic-section enrichment.

    TOPIC: {topic_name}

    SECTION FOCUS: {focus}

    CURRENT SECTION COVERAGE (recent, non-hidden):
    {existing_summaries}

    CANDIDATE ARTICLE (to consider adding):
    {article_text}

    TASK:
    - Judge whether the candidate substantively complements or improves the section coverage for the topic.
    - Reject if redundant, off-topic, or low-signal relative to CURRENT SECTION COVERAGE.
    - Consider diversity and recency of angles.

    Output ONLY a JSON object with exactly:
      - motivation: short one-sentence justification (first field)
      - relevant: true/false

    EXAMPLE OUTPUT:
    {{"motivation": "Adds a fresh perspective on X not covered by current articles.", "relevant": true}}

    YOUR RESPONSE:
    """

    prompt = PromptTemplate(
        input_variables=[
            "topic_name",
            "focus",
            "existing_summaries",
            "article_text",
            "system_mission",
            "system_context",
        ],
        template=prompt_template,
    )
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    # Prepare variables and compute prompt size for logging
    vars_ = {
        "topic_name": topic_name,
        "focus": focus,
        "existing_summaries": existing_block,
        "article_text": article_text,
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    }
    prompt_str = prompt.format(**vars_)
    approx_tokens = max(1, int(len(prompt_str) / 4))
    lines_count = prompt_str.count("\n") + 1
    logger.info(f"Prompt prepared | chars={len(prompt_str)} | lines={lines_count} | ~tokens={approx_tokens}")
    logger.debug(f"Prompt preview (first 400 chars): {prompt_str[:400]}")

    start = time.monotonic()
    try:
        result = chain.invoke(vars_)
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error(f"LLM call failed | elapsed={elapsed:.2f}s | err={e}")
        raise
    else:
        elapsed = time.monotonic() - start
        logger.info(f"LLM call done | elapsed={elapsed:.2f}s")
    if isinstance(result, dict):
        rel = bool(result["relevant"])  # required field, fail-fast on KeyError
        mot_raw = result["motivation"]  # required field, fail-fast on KeyError
        mot = str(mot_raw).strip()

        logger.info(
            f"Relevance decision | relevant={rel} | motivation_preview={mot[:200]}"
        )

        return rel, mot
    return False, ""