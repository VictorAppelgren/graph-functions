"""
LLM-driven analysis rewriting for a node based on selected articles.
"""

import re
from utils import app_logging

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import StrOutputParser
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from events.classifier import EventClassifier
from src.llm.prompts.rewrite_analysis_llm import initial_prompt, critic_prompt, source_checker_prompt, final_prompt
from src.llm.sanitizer import run_llm_decision, Response
from langchain_core.prompts import PromptTemplate

logger = app_logging.get_logger(__name__)


def rewrite_analysis_llm(
    material: str, section_focus: str, trk: EventClassifier | None = None
) -> str:
    """
    Calls the LLM to generate new analysis text for the section, using formatted material and section_focus.
    Implements: write → critic feedback → rewrite final (one round).
    Returns the final rewritten analysis text.
    """
    if not material or not section_focus:
        raise ValueError(
            "Both material and section_focus are required for rewrite_analysis."
        )
    logger.info(
        f"rewrite_analysis_start | section_focus={section_focus} | material_len={len(material)} | material_sample={material[:600]}"
    )
    llm = get_llm(ModelTier.COMPLEX)
  
    # Step 1: Initial draft (string output, inline citations and trailing Citations section)

    p_1 = PromptTemplate.from_template(
        initial_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            material=material
        )

    parser = StrOutputParser()
    chain = llm | parser

    r_1 = run_llm_decision(chain=chain, prompt=p, model=Response)

    logger.info(
        f"rewrite_analysis_initial | length={len(r)} | preview={r[:800]}"
    )

    # Step 2: Critic feedback

    p_2 = PromptTemplate.from_template(
        critic_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            material=material,
            initial=r_1.response
        )
    
    r_2 = run_llm_decision(chain=chain, prompt=p_2, model=Response)

    logger.info(
        f"rewrite_analysis_critic_feedback | length={len(r_1.response)} | preview={r_1.response[:800]}"
    )
    # Attach LLM feedback and metadata to tracker if provided
    if trk is not None:
        # Try to extract model, tokens, etc. from llm or chain if available
        model_name = (
            getattr(llm, "model_name", None) or getattr(llm, "model", None) or str(llm)
        )
        # Dummy token info unless available from chain/llm
        tokens = {}
        if hasattr(llm, "get_num_tokens_from_messages"):
            try:
                tokens["prompt"] = llm.get_num_tokens_from_messages(
                    [{"role": "system", "content": p_1}]
                )
                tokens["completion"] = llm.get_num_tokens_from_messages(
                    [{"role": "system", "content": r_1.response}]
                )
                tokens["total"] = tokens["prompt"] + tokens["completion"]
            except Exception:
                pass
        trk.put(
            "llm",
            {
                "model": model_name,
                "feedback": r_2,
                "tokens": tokens,
                # Add more metadata as needed (prompt_name, prompt_hash, finish_reason, etc.)
            },
        )

    # Step 3: Source checker for factual consistency

    p_3 = PromptTemplate.from_template(
        source_checker_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            material=material,
            initial=r_1.response,
            feedback=r_2.response
        )
    
    r_3 = run_llm_decision(chain.chain, prompt=p_3, model=Response)

    logger.info(
        f"rewrite_analysis_source_checker | length={len(r_3.response)} | preview={r_3.response[:800]}"
    )

    p_4 = PromptTemplate.from_template(
        final_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            material=material,
            initial=r_1.response,
            feedback=r_2.response,
            factual_corrections=r_3.response
        )
    
    r_4 = run_llm_decision(chain=chain, prompt=p_4, model=Response)

    logger.info(f"rewrite_analysis_final | length={len(r_4.response)} | preview={r_4.response[:800]}")
    return re.split(r"\n?Citations?:", r_4.response, flags=re.IGNORECASE)[0].rstrip()
