# analysis/should_rewrite_llm.py

"""
LLM-driven helper to decide if a topic's analysis should be rewritten given a new article.
Returns a tuple: (should_rewrite: bool, motivation: str).
"""
from typing import Tuple
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from utils import app_logging
from utils.app_logging import truncate_str
from langchain_core.prompts import PromptTemplate
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = app_logging.get_logger(__name__)

def should_rewrite_llm(analysis_str: str, new_article_summary: str, test: bool = False) -> Tuple[bool, str]:
    """
    Uses LLM to decide if the analysis should be rewritten for this topic.
    Returns (should_rewrite: bool, motivation: str)
    """
    if test:
        return (False, "Test mode: no rewrite.")

    logger.info("Analysis fields: %s", truncate_str(str(analysis_str), 100))

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS ANALYSIS REWRITE JUDGE for the Saga Graph.

        TASK:
        - Given the current analysis fields for a topic and the summary of a new article, output a JSON object with two fields:
            - "motivation" (string): short, specific, research-grade reasoning.
            - "should_rewrite" (boolean): true or false (JSON boolean).
        - Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields.

        CURRENT ANALYSIS FIELDS:
        {analysis_str}

        NEW ARTICLE SUMMARY:
        {new_article_summary}

        TWO EXAMPLES OF OUTPUT:
        {{ "motivation": "New policy change not reflected.", "should_rewrite": true }}
        {{ "motivation": "Redundant with existing analysis.", "should_rewrite": false }}

        YOUR RESPONSE:
    """
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_llm(ModelTier.COMPLEX)
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "analysis_str": analysis_str,
        "new_article_summary": new_article_summary,
    })

    logger.info("----- results should rewrite: ------")
    logger.info(result)
    logger.info("----- end results should rewrite ------")

    # Normalize to (bool, str)
    import json
    if isinstance(result, str):
        result = json.loads(result)

    sr_raw = result["should_rewrite"]  # required
    motivation = result["motivation"]  # required

    if isinstance(sr_raw, bool):
        sr_bool = sr_raw
    else:
        sr_bool = str(sr_raw).strip().lower() in ("true", "yes", "1")

    return sr_bool, motivation