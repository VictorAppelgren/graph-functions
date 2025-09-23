"""
LLM-driven summarization of articles for news ingestion.
"""

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.articles.article_text_formatter import extract_text_from_json_article
from src.llm.prompts.summarize_article import summarize_article_prompt
from src.llm.sanitizer import run_llm_decision, Summary

logger = app_logging.get_logger(__name__)

# Simple module-level cache for LLM chain
_cached_chain = None


def summarize_article(article: dict) -> str | None:
    """
    Uses LLM to summarize the full extracted article text in a strict JSON format.
    Returns the input article with 'argos_summary' populated.
    """
    logger.debug(
        "Entering summarize_article for title: %s", article.get("title", "<no title>")
    )

    # Build input from full extracted text (title, main, scraped, metadata) via formatter
    input_text = extract_text_from_json_article(article)

    llm = get_llm(ModelTier.MEDIUM)

    # Log stats about input
    logger.debug(
        f"About to generate summary with input text of {len(input_text)} characters."
    )
    if len(input_text) > 500:
        logger.debug(f"Summary input text (first 500 chars): {input_text[:500]}...")
    else:
        logger.debug(f"Summary input text: {input_text}")
    
    parser = JsonOutputParser()
    chain = llm | parser
    logger.debug("Created and cached LLM chain")

    p = PromptTemplate.from_template(
        summarize_article_prompt).format(
            input_text=input_text,
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT
        )
    
    r = run_llm_decision(chain=chain, prompt=p, model=Summary)

    if r.summary:
        return r.summary
    else:
        return None
