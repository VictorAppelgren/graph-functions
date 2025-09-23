"""
LLM-driven analysis rewriting for a node based on selected articles.
"""

import re
from utils import app_logging
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.llm.prompts.rewrite_analysis_llm import (
    initial_prompt,
    critic_prompt,
    source_checker_prompt,
    final_prompt,
)
from events.classifier import EventClassifier
from src.llm.sanitizer import run_llm_text_response

logger = app_logging.get_logger(__name__)

def extract_section_name(section_focus: str) -> str:
    """Extract section name from section_focus string"""
    if "Multi-year structural" in section_focus:
        return "FUNDAMENTAL"
    elif "3-6 months" in section_focus:
        return "MEDIUM"
    elif "0-3 weeks" in section_focus:
        return "CURRENT"
    elif "Cross-topic synthesis" in section_focus:
        return "DRIVERS"
    elif "Forward-looking scenarios" in section_focus:
        return "MOVERS_SCENARIOS"
    elif "Actionable trading" in section_focus:
        return "SWING_TRADE_OR_OUTLOOK"
    elif "Integrated synthesis" in section_focus:
        return "EXECUTIVE_SUMMARY"
    else:
        return "UNKNOWN"

def parse_material_overview(material: str, section_focus: str) -> str:
    """Parse material to show clean overview - now handled by material builder logging"""
    # Count articles in PRIMARY ASSET ANALYSIS section
    article_matches = re.findall(r'--- ARTICLE \d+:', material)
    return f"{len(article_matches)} articles loaded"


def rewrite_analysis_llm(
    material: str, section_focus: str, asset_name: str = "", asset_id: str = "", trk: EventClassifier | None = None
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
    # Simple confirmation - detailed logging done by material builder
    section_name = extract_section_name(section_focus)
    material_overview = parse_material_overview(material, section_focus)
    logger.info(f"🚀 STARTING LLM GENERATION | {section_name} | {material_overview}")
    llm = get_llm(ModelTier.COMPLEX)
  
    # Step 1: Initial draft (string output, inline citations and trailing Citations section)

    p_1 = PromptTemplate.from_template(
        initial_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            material=material,
            asset_name=asset_name,
            asset_id=asset_id
        )

    # Use standardized LLM text response handler
    parser = StrOutputParser()
    chain = llm | parser
    
    r_1 = run_llm_text_response(chain=chain, prompt=p_1)

    logger.info(
        f"rewrite_analysis_initial | length={len(r_1.response)} | preview={r_1.response[:800]}"
    )

    # Step 2: Critic feedback

    p_2 = PromptTemplate.from_template(
        critic_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            material=material,
            initial=r_1.response,
            asset_name=asset_name,
            asset_id=asset_id
        )
    
    r_2 = run_llm_text_response(chain=chain, prompt=p_2)

    logger.info(
        f"rewrite_analysis_critic_feedback | length={len(r_2.response)} | preview={r_2.response[:800]}"
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
            feedback=r_2.response,
            asset_name=asset_name,
            asset_id=asset_id
        )
    
    r_3 = run_llm_text_response(chain=chain, prompt=p_3)

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
            factual_corrections=r_3.response,
            asset_name=asset_name,
            asset_id=asset_id
        )
    
    r_4 = run_llm_text_response(chain=chain, prompt=p_4)

    logger.info(f"rewrite_analysis_final | length={len(r_4.response)} | preview={r_4.response[:800]}")
    return re.split(r"\n?Citations?:", r_4.response, flags=re.IGNORECASE)[0].rstrip()
