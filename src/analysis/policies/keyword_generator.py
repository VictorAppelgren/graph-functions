from typing import List
from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.analysis.orchestration.analysis_rewriter import SECTION_FOCUS
from src.llm.prompts.generate_keywords import generate_keyword_prompt
from src.llm.sanitizer import run_llm_decision, Keywords

from utils.app_logging import get_logger

logger = get_logger("analysis.keyword_generator")


def _clean_list(items: List[str]) -> List[str]:
    """Normalize, dedupe, and drop overly long/joined phrases.
    - lowercase, strip
    - keep up to 3 words; drop items > 20 chars with no separators (likely joined junk)
    """
    seen = set()
    out: List[str] = []
    for x in items:
        s = str(x).strip().lower()
        if not s:
            continue
        # drop overly long joined tokens without spaces
        if len(s) > 20 and (" " not in s):
            continue
        # cap phrases to max 3 words
        if len(s.split()) > 3:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def generate_keywords(topic_name: str, section: str) -> Keywords:
    """Generate keywords for a topic section using LLM."""
    logger.info("Generating keywords | topic=%s | section=%s", topic_name, section)

    llm = get_llm(ModelTier.SIMPLE)

    prompt = PromptTemplate.from_template(generate_keyword_prompt).format(
        topic_name=topic_name,
        section=section,
        focus=SECTION_FOCUS[section],
        system_mission=SYSTEM_MISSION,
        system_context=SYSTEM_CONTEXT
    )
    
    r = run_llm_decision(chain=llm, prompt=prompt, model=Keywords)

    logger.debug("------------------------------------")
    logger.debug("generated keywords: ")
    logger.info(f"list={r.list}")
    logger.debug("------------------------------------")

    # Track LLM call (statistics tracking disabled for now)
    # from src.observability.pipeline_logging import master_statistics
    # master_statistics(llm_simple_calls=1)

    return r
