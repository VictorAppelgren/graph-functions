# analysis/should_rewrite_llm.py

"""
LLM-driven helper to decide if a topic's analysis should be rewritten given a new article.
Returns a tuple: (should_rewrite: bool, motivation: str).
"""
import json
from typing import Tuple
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from utils import app_logging
from utils.app_logging import truncate_str
from langchain_core.prompts import PromptTemplate
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.llm.prompts.should_rewrite import should_rewrite_prompt
from src.llm.sanitizer import run_llm_decision, ShouldRewrite

logger = app_logging.get_logger(__name__)


def should_rewrite_llm(
    analysis: str, new_article_summary: str, test: bool = False
) -> Tuple[bool, str] | None:
    """
    Uses LLM to decide if the analysis should be rewritten for this topic.
    Returns (should_rewrite: bool, motivation: str)
    """
    if test:
        return (False, "Test mode: no rewrite.")

    logger.info("Analysis fields: %s", truncate_str(str(analysis), 100))

    # prompt_template = """
    #     {system_mission}
    #     {system_context}

    #     YOU ARE A WORLD-CLASS MACRO/MARKETS ANALYSIS REWRITE JUDGE for the Saga Graph.

    #     TASK:
    #     - Given the current analysis fields for a topic and the summary of a new article, output a JSON object with two fields:
    #         - "motivation" (string): short, specific, research-grade reasoning.
    #         - "should_rewrite" (boolean): true or false (JSON boolean).
    #     - Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields.

    #     CURRENT ANALYSIS FIELDS:
    #     {analysis_str}

    #     NEW ARTICLE SUMMARY:
    #     {new_article_summary}

    #     TWO EXAMPLES OF OUTPUT:
    #     {{ "motivation": "New policy change not reflected.", "should_rewrite": true }}
    #     {{ "motivation": "Redundant with existing analysis.", "should_rewrite": false }}

    #     YOUR RESPONSE:
    # """

    llm = get_llm(ModelTier.COMPLEX)
    parser = JsonOutputParser()
    chain = llm | parser

    p = PromptTemplate.from_template(
        should_rewrite_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            analysis=analysis,
            new_article_summary=new_article_summary
        )

    r = run_llm_decision(chain=chain, prompt=p, model=ShouldRewrite)

    if r.motivation:
        return r.rewrite, r.motivation
    else:
        return None

