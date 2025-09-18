from typing import List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.analysis.orchestration.analysis_rewriter import SECTION_FOCUS
from src.llm.prompts.generate_keywords import generate_keyword_prompt
from src.llm.sanitizer import run_llm_decision, Keywords

from utils.app_logging import get_logger

logger = get_logger("generate_keywords_llm")


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


def generate_keywords(topic_name: str, section: str) -> list[str] | None:
    """Generate a flat list (target 25–35) of short newsroom-surface keywords for scanning news."""
    focus = SECTION_FOCUS[section]

    logger.info("will generate keywords")
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = llm | parser

    p = PromptTemplate.from_template(
        generate_keyword_prompt).format(
            topic_name=topic_name,
            section=section,
            focus=focus,
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT
        )
    
    r = run_llm_decision(chain=chain, prompt=p, model=Keywords)

    logger.debug("------------------------------------")
    logger.debug("generated keywords: ")
    logger.info(f"{r}")
    logger.debug("------------------------------------")

    if r.list:
        return r.list[:40]
    else:
        return None
