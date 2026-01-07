"""
Citation Validator - Deterministic ID checking (no LLM)

SINGLE SOURCE OF TRUTH for extracting and validating citation IDs.

Supports:
- Article IDs: 9-character alphanumeric in parentheses (ABC123DEF)
- Section refs: sec_topic_section format
- Topic refs: (Topic:topic_id.field) format

Usage:
    from src.citations import validate_citations

    report = validate_citations(
        text="The Fed raised rates (ABC123DEF) causing...",
        allowed_ids={"ABC123DEF", "XYZ789GHI"}
    )

    if not report.is_valid:
        print(report.format_error())
"""

import re
from dataclasses import dataclass, field
from typing import Collection, Set, Optional


# =============================================================================
# ID FORMAT PATTERNS
# =============================================================================

# Article ID: exactly 9 alphanumeric chars (uppercase)
ARTICLE_ID_PATTERN = re.compile(r'\(([A-Z0-9]{9})\)')

# Section ref: sec_topicid_sectionname (exploration agent format)
SECTION_REF_PATTERN = re.compile(r'\((sec_[a-z0-9_]+)\)')

# Topic ref: (Topic:topic_id.field_name)
TOPIC_REF_PATTERN = re.compile(r'\(Topic:([a-z_]+\.[a-z_]+)\)')

# Legacy art_ prefix (for migration - we extract the raw ID)
ART_PREFIX_PATTERN = re.compile(r'\(art_([A-Z0-9]{9})\)')


# =============================================================================
# CITATION REPORT
# =============================================================================

@dataclass
class CitationReport:
    """Result of citation validation - immutable truth about what's in the text."""

    # What we found
    article_ids: Set[str] = field(default_factory=set)
    section_refs: Set[str] = field(default_factory=set)
    topic_refs: Set[str] = field(default_factory=set)

    # What's invalid
    invalid_article_ids: Set[str] = field(default_factory=set)
    invalid_section_refs: Set[str] = field(default_factory=set)

    # Summary
    is_valid: bool = True

    # Backward compatibility aliases
    @property
    def article_ids_in_text(self) -> Set[str]:
        """Alias for article_ids (backward compatibility with old validator)."""
        return self.article_ids

    @property
    def unknown_article_ids(self) -> Set[str]:
        """Alias for invalid_article_ids (backward compatibility with old validator)."""
        return self.invalid_article_ids

    def format_error_message(self) -> str:
        """Alias for format_for_llm_retry (backward compatibility with old validator)."""
        return self.format_for_llm_retry()

    def format_error(self) -> str:
        """Format error message for logging/debugging."""
        if self.is_valid:
            return ""

        lines = ["CITATION VALIDATION FAILED:"]

        if self.invalid_article_ids:
            lines.append(f"  Invalid article IDs: {sorted(self.invalid_article_ids)}")
        if self.invalid_section_refs:
            lines.append(f"  Invalid section refs: {sorted(self.invalid_section_refs)}")

        return "\n".join(lines)

    def format_for_llm_retry(self) -> str:
        """
        Format error message for LLM to fix.
        This is the CRITICAL part - clear, actionable instruction.
        """
        if self.is_valid:
            return ""

        lines = [
            "",
            "=" * 70,
            "CITATION ERROR - YOUR OUTPUT CONTAINS INVALID SOURCE IDs",
            "=" * 70,
            "",
        ]

        if self.invalid_article_ids:
            lines.append("INVALID ARTICLE IDs (these do NOT exist in source material):")
            for aid in sorted(self.invalid_article_ids):
                lines.append(f"  - ({aid}) <- REMOVE OR REPLACE")
            lines.append("")

        if self.invalid_section_refs:
            lines.append("INVALID SECTION REFS (these do NOT exist):")
            for sid in sorted(self.invalid_section_refs):
                lines.append(f"  - ({sid}) <- REMOVE OR REPLACE")
            lines.append("")

        lines.extend([
            "YOU MUST:",
            "1. Remove ALL claims that use these invalid IDs",
            "2. OR rewrite those claims using ONLY valid IDs from the source material",
            "3. Do NOT invent new IDs - use only what's in the SOURCE MATERIAL above",
            "",
            "REWRITE YOUR RESPONSE NOW:",
            "=" * 70,
        ])

        return "\n".join(lines)


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def extract_article_ids(text: str) -> Set[str]:
    """
    Extract all 9-character article IDs from text.

    Handles both formats:
    - (ABC123DEF) - standard format
    - (art_ABC123DEF) - legacy exploration agent format (extracts raw ID)

    Returns set of raw 9-char IDs (no prefix).
    """
    if not text:
        return set()

    # Standard format
    standard_ids = set(ARTICLE_ID_PATTERN.findall(text))

    # Legacy art_ format - extract raw ID
    legacy_ids = set(ART_PREFIX_PATTERN.findall(text))

    return standard_ids | legacy_ids


def extract_section_refs(text: str) -> Set[str]:
    """Extract all sec_XXX_YYY references from text."""
    if not text:
        return set()
    return set(SECTION_REF_PATTERN.findall(text))


def extract_topic_refs(text: str) -> Set[str]:
    """Extract all (Topic:xxx.yyy) references from text."""
    if not text:
        return set()
    return set(TOPIC_REF_PATTERN.findall(text))


def normalize_id(raw_id: str) -> str:
    """
    Normalize any ID format to canonical form.

    art_ABC123DEF -> ABC123DEF
    ABC123DEF -> ABC123DEF
    sec_topic_section -> sec_topic_section (unchanged)
    """
    if raw_id.startswith("art_"):
        return raw_id[4:]  # Strip art_ prefix
    return raw_id


def validate_citations(
    text: str,
    allowed_article_ids: Optional[Collection[str]] = None,
    allowed_section_refs: Optional[Collection[str]] = None,
) -> CitationReport:
    """
    Validate all citations in text against allowed sets.

    Args:
        text: The generated text to validate
        allowed_article_ids: Set of valid 9-char article IDs (raw, no prefix)
        allowed_section_refs: Set of valid sec_XXX_YYY refs

    Returns:
        CitationReport with validation results

    Example:
        report = validate_citations(
            text="Fed raised rates (ABC123DEF) causing bond selloff (FAKE12345)",
            allowed_article_ids={"ABC123DEF", "XYZ789GHI"}
        )
        # report.is_valid = False
        # report.invalid_article_ids = {"FAKE12345"}
    """
    # Extract all citations
    article_ids = extract_article_ids(text)
    section_refs = extract_section_refs(text)
    topic_refs = extract_topic_refs(text)

    # Normalize allowed sets
    allowed_articles = set(allowed_article_ids) if allowed_article_ids else set()
    allowed_sections = set(allowed_section_refs) if allowed_section_refs else set()

    # Find invalids
    invalid_articles = set()
    invalid_sections = set()

    if allowed_article_ids is not None:  # Only validate if allowed set provided
        invalid_articles = article_ids - allowed_articles

    if allowed_section_refs is not None:  # Only validate if allowed set provided
        invalid_sections = section_refs - allowed_sections

    # Determine validity
    is_valid = len(invalid_articles) == 0 and len(invalid_sections) == 0

    return CitationReport(
        article_ids=article_ids,
        section_refs=section_refs,
        topic_refs=topic_refs,
        invalid_article_ids=invalid_articles,
        invalid_section_refs=invalid_sections,
        is_valid=is_valid,
    )


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CITATION VALIDATOR TEST")
    print("=" * 60)

    # Test data
    allowed_ids = {"Z7O1DCHS7", "K8M2NQWER", "A3B4C5D6E", "REALID123"}

    test_text = """
    The Fed's policy shift (Z7O1DCHS7) has significant implications.
    Multiple sources confirm this trend (K8M2NQWER)(A3B4C5D6E).

    However, some analysis suggests otherwise (FAKEID999) based on
    recent data (ABC123DEF) from various reports.

    Legacy format also works (art_REALID123) and extracts the raw ID.

    The real impact is clear from the executive summary (sec_fed_policy_executive_summary).

    Topic references like (Topic:fed_policy.drivers) should be captured.
    """

    print("\nALLOWED IDs:", sorted(allowed_ids))
    print("\nTEST TEXT:")
    print(test_text)

    print("\n" + "=" * 60)
    print("VALIDATION RESULT:")
    print("=" * 60)

    report = validate_citations(test_text, allowed_ids)

    print(f"Article IDs found: {sorted(report.article_ids)}")
    print(f"Section refs found: {sorted(report.section_refs)}")
    print(f"Topic refs found: {sorted(report.topic_refs)}")
    print(f"Invalid article IDs: {sorted(report.invalid_article_ids)}")
    print(f"Is valid: {report.is_valid}")

    if not report.is_valid:
        print("\nERROR MESSAGE FOR LLM:")
        print("-" * 40)
        print(report.format_for_llm_retry())

    # Assertions
    assert "Z7O1DCHS7" in report.article_ids
    assert "K8M2NQWER" in report.article_ids
    assert "REALID123" in report.article_ids  # From art_ prefix
    assert "FAKEID999" in report.invalid_article_ids
    assert "ABC123DEF" in report.invalid_article_ids
    assert "sec_fed_policy_executive_summary" in report.section_refs
    assert "fed_policy.drivers" in report.topic_refs
    assert not report.is_valid

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
