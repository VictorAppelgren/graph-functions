"""
LLM-driven categorization of articles in the context of a topic.
"""

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from typing import cast, Any, Literal
import json
from src.llm.prompts.find_category import find_category_prompt
from src.llm.sanitizer import run_llm_decision, CategoryName, FindCategory

logger = get_logger(__name__)

def find_category(article_text: str) -> tuple[str, CategoryName] | None:
    """
    Ask the LLM to assign categories to an article and return the first (motivation, name).

    Returns:
        (motivation, name) where both may be None if parsing/validation failed.
    """
    categories = [c.value for c in CategoryName]

    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = llm | parser

    p = PromptTemplate.from_template(
        find_category_prompt).format(
            article_text=article_text,
            categories=categories,
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT
        )

    r = run_llm_decision(chain=chain, prompt=p, model=FindCategory)

    if r.motivation:
        return r.motivation, r.name
    else: 
        return None