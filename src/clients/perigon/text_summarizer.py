"""
LLM-driven summarization of articles for news ingestion.
"""

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from utils.app_logging import truncate_str
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.articles.article_text_formatter import extract_text_from_json_article

logger = app_logging.get_logger(__name__)

# Simple module-level cache for LLM chain
_cached_chain = None


def summarize_article(article: dict) -> dict:
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
    prompt_template = """
    {system_mission}
    {system_context}

    STRICT OUTPUT INSTRUCTIONS — READ CAREFULLY:

    You are an expert summarization system. Your ONLY task is to output a JSON object with a single field 'summary', containing a concise summary (2-5 sentences) of the article. DO NOT output anything except this JSON object. DO NOT include any explanation, markdown, commentary, or extra fields. DO NOT use backticks or code blocks. DO NOT add any text before or after the JSON. If there is nothing to summarize, output: {{"summary": ""}}

    ARTICLE TEXT:
    {input_text}


    REMEMBER THE JSON OUTPUT FORMAT SHOULD ONLY HAVE {{"summary": "..."}} NOTHING ELSE AND NO OTHER COMMENTARY!
    YOUR RESPONSE in the format {{"summary": "..."}}:
    """
    logger.debug("Prompt: %s", truncate_str(str(prompt_template), 100))

    # Use cached chain or create new one
    global _cached_chain
    if _cached_chain is None:
        prompt = PromptTemplate.from_template(prompt_template)
        parser = JsonOutputParser()
        _cached_chain = prompt | llm | parser
        logger.debug("Created and cached LLM chain")

    result = _cached_chain.invoke(
        {
            "input_text": input_text,
            "system_mission": SYSTEM_MISSION,
            "system_context": SYSTEM_CONTEXT,
        }
    )

    # Some backends may still return a string; align with should_rewrite_llm pattern
    if isinstance(result, str):
        import json  # local import to avoid top-level dependency

        result = json.loads(result)

    # Require 'summary' key (fail fast on malformed output)
    summary = result["summary"] if isinstance(result, dict) else ""

    article = dict(article)  # shallow copy
    article["argos_summary"] = summary
    logger.debug(
        f"Summary sample: {summary[:300]}{'...' if len(summary) > 300 else ''}"
    )
    logger.debug("Argos summary field added to article and returned.")
    return article
