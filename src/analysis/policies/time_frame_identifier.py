from __future__ import annotations

import json
from typing import Any, Literal, cast
from langchain_core.runnables import Runnable
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.find_time_frame import find_time_frame_prompt
from src.llm.sanitizer import run_llm_decision, TimeFrame

# Configure logging
logger = app_logging.get_logger(__name__)

# Horizon type now defined in sanitizer.py TimeFrame model


# Removed duplicate classes - using centralized TimeFrame model from sanitizer.py


def find_time_frame(article_text: str) -> TimeFrame:
    """
    Classify an article's time frame. Returns TimeFrame object.
    Raises on malformed LLM output.
    """
    logger.info(
        "Article text: %s%s",
        article_text[:200],
        "..." if len(article_text) > 200 else "",
    )

    llm = get_llm(ModelTier.MEDIUM)

    prompt = PromptTemplate.from_template(find_time_frame_prompt).format(
        article_text=article_text,
        system_mission=SYSTEM_MISSION,
        system_context=SYSTEM_CONTEXT
    )
    
    r = run_llm_decision(chain=llm, prompt=prompt, model=TimeFrame)

    logger.info("Time frame decision: %s", r.model_dump())
    return r
