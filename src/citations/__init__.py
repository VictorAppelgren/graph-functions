"""
Citations Module - Universal Citation Validation for Saga

SINGLE SOURCE OF TRUTH for all citation validation across the project.
Every agent that generates text with citations MUST use this module.

Usage:
    from src.citations import validate_and_fix_citations

    # Simple: validate and auto-retry once if invalid
    final_text, report = validate_and_fix_citations(
        generate_fn=lambda prompt: llm.invoke(prompt).content,
        initial_prompt=my_prompt,
        initial_output=first_draft,
        allowed_ids={"ABC123DEF", "XYZ789GHI"},
    )

    # Or just validate without retry:
    from src.citations import validate_citations
    report = validate_citations(text, allowed_ids)
    if not report.is_valid:
        # Handle manually
"""

from src.citations.validator import (
    CitationReport,
    validate_citations,
    extract_article_ids,
    normalize_id,
)
from src.citations.fixer import (
    validate_and_fix_citations,
    build_citation_fix_prompt,
    CITATION_FIX_INSTRUCTION,
)

__all__ = [
    # Core validation
    "CitationReport",
    "validate_citations",
    "extract_article_ids",
    "normalize_id",
    # Auto-fix workflow
    "validate_and_fix_citations",
    "build_citation_fix_prompt",
    "CITATION_FIX_INSTRUCTION",
]
