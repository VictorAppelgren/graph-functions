"""
LLM-driven helper to decide if a new article should replace an existing one for a topic node.
Returns a dict with 'motivation' and 'id_to_replace'.
"""

from typing import Optional, Any
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.analysis.types import TestParams
from src.llm.prompts.article_evaluator import article_evaluator_prompt
from src.llm.sanitizer import run_llm_decision, Decision
from langchain_core.prompts import PromptTemplate

logger = app_logging.get_logger("analysis.article_evaluator")

# Per-timeframe policy (simple defaults)
MIN_PER_TIMEFRAME = 5
MAX_PER_TIMEFRAME = 10


def does_article_replace_old_llm(
    new_article_summary: str,
    existing_articles: list[dict[str, Any]],
    test: bool = False,
    decision_instruction: str = "",
    context_text: Optional[str] = None,
) -> TestParams | Any:
    """
    Uses LLM to decide if the new article replaces any existing article for the topic.
    Each existing article is a dict with 'id' and 'argos_summary'.
    Returns a dict: {'motivation': str, 'tool': str, 'id': str or None}
    """
    if test:
        return {"motivation": "Test mode: no action.", "tool": "none", "id": None}
    summaries = "\n".join(
        [f"- {a['id']}: {a.get('argos_summary', '')}" for a in existing_articles]
    )
    allowed_ids_str = ", ".join([a["id"] for a in existing_articles])
    context_block = (
        f"\nOTHER TIMEFRAMES CONTEXT (read-only, do not act on these):\n{context_text}\n"
        if context_text
        else ""
    )

    llm = get_llm(ModelTier.SIMPLE)

    prompt = PromptTemplate.from_template(article_evaluator_prompt).format(
        article_text=new_article_summary,
        allowed_ids=allowed_ids_str,
        system_mission=SYSTEM_MISSION,
        system_context=SYSTEM_CONTEXT
    )
    
    logger.debug("Prompt: %s", truncate_str(str(prompt), 120))

    r = run_llm_decision(chain=llm, prompt=prompt, model=Decision)

    if r.tool:
        return r
    else:
        return None
