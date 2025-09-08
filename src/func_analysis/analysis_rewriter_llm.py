"""
LLM-driven analysis rewriting for a node based on selected articles.
"""
from typing import Dict, List

import sys, os
from utils import logging
logger = logging.get_logger(__name__)

from model_config import get_complex_llm
from langchain_core.output_parsers import StrOutputParser
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT

def rewrite_analysis_llm(material: str, section_focus: str, trk=None) -> str:
    """
    Calls the LLM to generate new analysis text for the section, using formatted material and section_focus.
    Implements: write → critic feedback → rewrite final (one round).
    Returns the final rewritten analysis text.
    """
    if not material or not section_focus:
        raise ValueError("Both material and section_focus are required for rewrite_analysis.")
    logger.info(f"rewrite_analysis_start | section_focus={section_focus} | material_len={len(material)} | material_sample={material[:600]}")
    llm = get_complex_llm()
    # Step 1: Initial draft (string output, inline citations and trailing Citations section)
    initial_prompt = f'''
{SYSTEM_MISSION}
{SYSTEM_CONTEXT}
You are a world-class macro/markets research analyst and swing-trading strategist tasked with producing god-tier analysis for the Saga Graph.

        SECTION FOCUS (authoritative spec for horizon, style, and goals):
        {section_focus}

        SOURCE MATERIAL (each entry includes explicit article IDs like "ID: ABC123"; use ALL salient information):
        {material}

        CITATION RULES (READ CAREFULLY — MUST COMPLY):
        - Inline citations MUST appear immediately after the specific claim they support.
        - The inline citation format is EXACTLY: (ID) — where ID is from SOURCE MATERIAL.
        - No other characters in the parentheses: NO title, NO URL, NO date, NO "ID:", NO punctuation beyond the parentheses. Examples: (2UU8NMSWU) (SFAGCBTEQ)
        - Cite FREQUENTLY and PRECISELY: every substantive fact, number, finding, or external assertion must have an inline (ID) right after the sentence or clause it supports.
        - Never invent IDs. Use only IDs present in SOURCE MATERIAL. If a claim lacks support, remove it or rewrite to what is supported and cite accordingly.
        - If multiple sources support a claim, you may include multiple IDs: (ID1)(ID2) with no spaces.
        - Do NOT place citations at paragraph ends to cover prior claims—place them directly after the claim.
        - Inline citations are ID-only. DO NOT include URL, title, source, or date inline.
        - At the end, include a Citations section listing each used ID with optional Title and URL. This section is separate and does NOT replace inline citations.

        TASK (strictly follow):
        1) Synthesize across sources; resolve conflicts explicitly; extract the causal chain (why) and the market transmission channels.
        2) Ground every substantive claim in SOURCE MATERIAL with inline (ID) citations, e.g., (ABC123). Cite frequently and precisely. Do not invent IDs.
        3) For fundamentals: derive first principles and invariant constraints that anchor long-run behavior; state structural regimes and how they shift.
        4) For medium/current: map catalysts, triggers, invalidations, and path-dependency; indicate timing windows consistent with the section horizon.
        5) Quantify where possible (ranges/magnitudes/direction); name the policy/data variables driving the view (e.g., growth, inflation, rates, balance of payments, risk premia).
        6) Conclude with: Base case (and its drivers), Key risks (2–3), What to watch next (signals), and Confidence.
        7) Form: 1 long paragraph or 2–3 compact paragraphs; no bullet lists; no filler; assert a clear, evidence-backed view.
        8) Length target: 300–700 words.

        MAIN-FOCUS DIRECTIVE — READ CAREFULLY:
        - Produce a SUPER-DEEP analysis exclusively about the primary asset specified in SECTION FOCUS, strictly within the timeframe specified there.
        - Every sentence MUST directly relate to that asset. If mentioning other entities, explicitly tie back to the asset with causal reasoning and an inline (ID) citation immediately after the claim.
        - Omit anything that cannot be clearly connected to the asset and timeframe in SECTION FOCUS.

        STRICT CITATION RULE: Only in-text (ID) citations are allowed. DO NOT include any citation lists, reference sections, or citation blocks at the end. Output only the analysis text (no JSON).
    '''
    chain = llm | StrOutputParser()
    initial = chain.invoke(initial_prompt)
    logger.info(f"rewrite_analysis_initial | length={len(initial)} | preview={initial[:800]}")
    # Step 2: Critic feedback
    critic_prompt = f"""
{SYSTEM_MISSION}
{SYSTEM_CONTEXT}
You are an expert reviewer. Provide concrete, high-signal feedback to upgrade the analysis to world-class quality. Evaluate:
- Depth and clarity of reasoning; coherence of causal chain and market transmission.
- Alignment with SECTION FOCUS (horizon/style) and adherence to length/format constraints.
- First-principles grounding (for fundamentals), scenario structure (for medium/current), and specificity of catalysts/triggers/invalidation.
- Quantification and use of numbers/ranges from sources; avoidance of generic platitudes.
- Citation density and correctness (only IDs present in SOURCE MATERIAL); coverage of all critical sources; reconciliation of conflicts.

SECTION FOCUS:
{section_focus}

SOURCE MATERIAL:
{material}

ANALYSIS DRAFT:
{initial}

Main-focus check:
- The draft MUST be exclusively about the asset defined in SECTION FOCUS, within that timeframe.
- Flag any sentence that drifts; require either an explicit causal link back to the asset with inline (ID) citation, or removal.

Output your feedback as a compact paragraph with actionable edit instructions.
"""
    feedback = chain.invoke(critic_prompt)
    logger.info(f"rewrite_analysis_critic_feedback | length={len(feedback)} | preview={feedback[:800]}")
    # Attach LLM feedback and metadata to tracker if provided
    if trk is not None:
        # Try to extract model, tokens, etc. from llm or chain if available
        model_name = getattr(llm, 'model_name', None) or getattr(llm, 'model', None) or str(llm)
        # Dummy token info unless available from chain/llm
        tokens = {}
        if hasattr(llm, 'get_num_tokens_from_messages'):
            try:
                tokens['prompt'] = llm.get_num_tokens_from_messages([{'role': 'system', 'content': initial_prompt}])
                tokens['completion'] = llm.get_num_tokens_from_messages([{'role': 'system', 'content': initial}])
                tokens['total'] = tokens['prompt'] + tokens['completion']
            except Exception:
                pass
        trk.put('llm', {
            'model': model_name,
            'feedback': feedback,
            'tokens': tokens,
            # Add more metadata as needed (prompt_name, prompt_hash, finish_reason, etc.)
        })
    # Step 3: Source checker for factual consistency
    source_checker_prompt = f"""
{SYSTEM_MISSION}
{SYSTEM_CONTEXT}
You are a meticulous fact-checker. Compare the analysis draft to SOURCE MATERIAL and SECTION FOCUS. Identify:
- Factual inaccuracies or overstatements; invented facts or IDs; uncited claims that need support.
- Numbers/dates/policy facts that conflict with sources; missing but necessary citations.
- Misalignment with the specified horizon or format constraints.
Incorporate the reviewer's feedback and point out additional corrections required. If none, say 'No factual inconsistencies found.'

SECTION FOCUS:
{section_focus}

SOURCE MATERIAL:
{material}

ANALYSIS DRAFT:
{initial}

FEEDBACK FROM CRITIC:
{feedback}

Main-focus verification:
- Identify any sentence not explicitly about the asset in SECTION FOCUS within the specified timeframe.
- Require removal unless a clear causal link is added with an inline (ID) citation.

STRICT: If you find any citation lists, reference sections, or citation blocks at the end of the analysis, instruct the writer to remove them. Only in-text (ID) citations are allowed. Output your factual corrections as a compact paragraph.
"""
    factual_corrections = chain.invoke(source_checker_prompt)
    logger.info(f"rewrite_analysis_source_checker | length={len(factual_corrections)} | preview={factual_corrections[:800]}")
    # Step 4: Rewrite final
    final_prompt = f"""
{SYSTEM_MISSION}
{SYSTEM_CONTEXT}
You are a world-class investment research analyst. Revise the OLD ANALYSIS DRAFT using the expert feedback and factual corrections. Preserve valuable content and structure but make all changes needed to achieve depth, accuracy, and clarity.

SECTION FOCUS:
{section_focus}

SOURCE MATERIAL:
{material}

OLD ANALYSIS DRAFT:
{initial}

FEEDBACK FROM CRITIC:
{feedback}

FACTUAL CORRECTIONS FROM SOURCE CHECKER:
{factual_corrections}

CITATION RULES (READ CAREFULLY — MUST COMPLY):
- Inline citations MUST appear immediately after the specific claim they support.
- The inline citation format is EXACTLY: (ID) — where ID is from SOURCE MATERIAL.
- No other characters in the parentheses: NO title, NO URL, NO date, NO "ID:", NO punctuation beyond the parentheses. Examples: (2UU8NMSWU) (SFAGCBTEQ)
- Cite FREQUENTLY and PRECISELY: every substantive fact, number, finding, or external assertion must have an inline (ID) right after the sentence or clause it supports.
- Never invent IDs. Use only IDs present in SOURCE MATERIAL. If a claim lacks support, remove it or rewrite to what is supported and cite accordingly.
- If multiple sources support a claim, you may include multiple IDs: (ID1)(ID2) with no spaces.
- Do NOT place citations at paragraph ends to cover prior claims—place them directly after the claim.
- Inline citations are ID-only. DO NOT include URL, title, source, or date inline.
- At the end, include a Citations section listing each used ID with optional Title and URL. This section is separate and does NOT replace inline citations.

Final requirements:
- Strong synthesis; explicit causal chain; scenario/catalyst logic appropriate to the section.
- Frequent, precise inline (ID) citations tied to specific claims; no invented IDs.
- Form: 1 long paragraph or 2–3 compact paragraphs; no bullet lists.
- STRICT: DO NOT include any citation lists, reference sections, or citation blocks at the end. Only in-text (ID) citations are allowed.
- Only in-text (ID) citations are allowed.
- MAIN-FOCUS DIRECTIVE: Produce a SUPER-DEEP analysis exclusively about the asset from SECTION FOCUS, strictly within its timeframe. Remove any off-topic sentence or one lacking a clear causal link supported by inline (ID) citations.

Output only the analysis text (no JSON).
"""
    import re
    final = chain.invoke(final_prompt)
    logger.info(f"rewrite_analysis_final | length={len(final)} | preview={final[:800]}")
    # Strip trailing Citations section if present
    def strip_trailing_citations(text):
        return re.split(r"\n?Citations?:", text, flags=re.IGNORECASE)[0].rstrip()
    return strip_trailing_citations(final)
