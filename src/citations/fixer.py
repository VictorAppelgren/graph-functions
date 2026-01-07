"""
Citation Fixer - Automatic retry workflow for invalid citations

SINGLE SOURCE OF TRUTH for how to handle citation errors.
When LLM generates invalid citations, we give it ONE chance to fix.

Design Philosophy:
- Simple: One retry, clear instruction, done
- Robust: Same context, just add error message
- Universal: Works with any LLM, any prompt structure

Usage:
    from src.citations import validate_and_fix_citations

    final_text, report = validate_and_fix_citations(
        generate_fn=lambda prompt: llm.invoke(prompt).content,
        initial_prompt=my_prompt,
        initial_output=first_draft,
        allowed_ids=valid_article_ids,
    )

    if report.is_valid:
        # Use final_text - it's clean
    else:
        # Even after retry, still invalid - log warning, use anyway or fail
"""

from typing import Callable, Optional, Set, Tuple
from src.citations.validator import CitationReport, validate_citations
from utils import app_logging

logger = app_logging.get_logger(__name__)


# =============================================================================
# CITATION FIX INSTRUCTION
# =============================================================================

CITATION_FIX_INSTRUCTION = """
===============================================================================
CITATION ERROR - REWRITE REQUIRED
===============================================================================

YOUR PREVIOUS OUTPUT CONTAINED INVALID SOURCE IDs.
These IDs do NOT exist in the source material provided:

{invalid_ids}

MANDATORY ACTION:
1. REMOVE all claims that cite these invalid IDs
2. OR REWRITE those claims using ONLY valid IDs from SOURCE MATERIAL above
3. Do NOT invent new IDs - they will be detected and rejected

The valid article IDs are ONLY the 9-character codes shown in the source
material sections above (e.g., ABC123DEF, XYZ789GHI).

REWRITE YOUR COMPLETE RESPONSE NOW:
===============================================================================
"""


def build_citation_fix_prompt(
    original_prompt: str,
    original_output: str,
    report: CitationReport,
) -> str:
    """
    Build a retry prompt that includes the error feedback.

    Structure:
    1. Original prompt (with source material)
    2. Previous output (for context)
    3. Clear error message with invalid IDs
    4. Instruction to rewrite

    This gives the LLM maximum context to fix correctly.
    """
    # Format invalid IDs for display
    invalid_ids_display = []
    for aid in sorted(report.invalid_article_ids):
        invalid_ids_display.append(f"  - ({aid})")
    for sid in sorted(report.invalid_section_refs):
        invalid_ids_display.append(f"  - ({sid})")

    fix_instruction = CITATION_FIX_INSTRUCTION.format(
        invalid_ids="\n".join(invalid_ids_display) if invalid_ids_display else "  (none)"
    )

    # Build retry prompt
    retry_prompt = f"""{original_prompt}

--- YOUR PREVIOUS OUTPUT (CONTAINS ERRORS) ---
{original_output}
--- END PREVIOUS OUTPUT ---

{fix_instruction}
"""
    return retry_prompt


def validate_and_fix_citations(
    generate_fn: Callable[[str], str],
    initial_prompt: str,
    initial_output: str,
    allowed_ids: Set[str],
    allowed_section_refs: Optional[Set[str]] = None,
    max_retries: int = 1,
) -> Tuple[str, CitationReport]:
    """
    Validate citations and retry ONCE if invalid.

    This is the UNIVERSAL workflow for all text generation:
    1. Validate initial output
    2. If invalid, build fix prompt and retry ONCE
    3. Return final output + report

    Args:
        generate_fn: Function that takes prompt and returns text
                     (typically: lambda p: llm.invoke(p).content)
        initial_prompt: The original prompt with source material
        initial_output: The first generated text to validate
        allowed_ids: Set of valid 9-char article IDs
        allowed_section_refs: Optional set of valid sec_XXX refs
        max_retries: Number of retry attempts (default 1)

    Returns:
        (final_text, report) - The best output we got and its validation report

    Example:
        text, report = validate_and_fix_citations(
            generate_fn=lambda p: llm.invoke(p).content,
            initial_prompt=full_prompt,
            initial_output=first_draft,
            allowed_ids=material_package["referenced_articles"].keys(),
        )

        if report.is_valid:
            save(text)
        else:
            logger.warning(f"Citations still invalid: {report.invalid_article_ids}")
            save(text)  # or raise error
    """
    current_output = initial_output

    # First validation
    report = validate_citations(
        current_output,
        allowed_article_ids=allowed_ids,
        allowed_section_refs=allowed_section_refs,
    )

    if report.is_valid:
        logger.info("Citation validation passed on first attempt")
        return current_output, report

    # Need to retry
    logger.warning(
        "Citation validation FAILED | invalid_ids=%s | retrying...",
        sorted(report.invalid_article_ids)
    )

    for attempt in range(max_retries):
        # Build retry prompt with error feedback
        retry_prompt = build_citation_fix_prompt(
            original_prompt=initial_prompt,
            original_output=current_output,
            report=report,
        )

        # Generate new output
        try:
            current_output = generate_fn(retry_prompt)
        except Exception as e:
            logger.error("LLM retry failed: %s", e)
            break

        # Validate again
        report = validate_citations(
            current_output,
            allowed_article_ids=allowed_ids,
            allowed_section_refs=allowed_section_refs,
        )

        if report.is_valid:
            logger.info("Citation validation passed after retry %d", attempt + 1)
            return current_output, report

        logger.warning(
            "Citation validation still FAILED after retry %d | invalid_ids=%s",
            attempt + 1,
            sorted(report.invalid_article_ids)
        )

    # Exhausted retries - return what we have
    logger.error(
        "Citation validation FAILED after %d retries | invalid_ids=%s | proceeding anyway",
        max_retries,
        sorted(report.invalid_article_ids)
    )

    return current_output, report


# =============================================================================
# SIMPLE WRAPPER FOR AGENTS
# =============================================================================

def validated_generate(
    llm,
    prompt: str,
    allowed_ids: Set[str],
    response_model=None,
) -> Tuple[str, CitationReport]:
    """
    Simplified wrapper for agents - generate and validate in one call.

    Args:
        llm: LangChain LLM instance
        prompt: Full prompt with source material
        allowed_ids: Valid article IDs
        response_model: Optional Pydantic model for structured output

    Returns:
        (text, report)
    """
    # First generation
    if response_model:
        result = llm.with_structured_output(response_model).invoke(prompt)
        initial_output = result.model_dump_json() if hasattr(result, 'model_dump_json') else str(result)
    else:
        result = llm.invoke(prompt)
        initial_output = result.content if hasattr(result, 'content') else str(result)

    # Define generate function for retry
    def generate_fn(p: str) -> str:
        r = llm.invoke(p)
        return r.content if hasattr(r, 'content') else str(r)

    return validate_and_fix_citations(
        generate_fn=generate_fn,
        initial_prompt=prompt,
        initial_output=initial_output,
        allowed_ids=allowed_ids,
    )


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CITATION FIXER TEST")
    print("=" * 60)

    # Simulate an LLM that fixes its mistakes
    call_count = [0]

    def mock_llm(prompt: str) -> str:
        call_count[0] += 1
        if "CITATION ERROR" in prompt:
            # Second call - fix the mistake
            return "Fed policy (Z7O1DCHS7) is important. This affects rates (K8M2NQWER)."
        else:
            # First call - make a mistake
            return "Fed policy (Z7O1DCHS7) is important. Recent data (FAKEID999) shows trends."

    # Test data
    allowed = {"Z7O1DCHS7", "K8M2NQWER"}
    initial_prompt = "Write about Fed policy using these sources: Z7O1DCHS7, K8M2NQWER"
    initial_output = mock_llm(initial_prompt)

    print(f"\nInitial output: {initial_output}")
    print(f"Allowed IDs: {allowed}")

    final_text, report = validate_and_fix_citations(
        generate_fn=mock_llm,
        initial_prompt=initial_prompt,
        initial_output=initial_output,
        allowed_ids=allowed,
    )

    print(f"\nFinal output: {final_text}")
    print(f"Is valid: {report.is_valid}")
    print(f"LLM calls: {call_count[0]}")

    assert report.is_valid, "Should be valid after retry"
    assert call_count[0] == 2, "Should have called LLM twice (initial + retry)"
    assert "FAKEID999" not in final_text, "Invalid ID should be removed"

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
