"""
Citation Validator - Deterministic ID checking (no LLM)

Extracts 9-character article IDs from analysis text and validates
them against the set of allowed IDs from source material.
"""

import re
from dataclasses import dataclass
from typing import Collection, Set


@dataclass
class CitationReport:
    """Result of citation validation."""
    
    article_ids_in_text: Set[str]
    unknown_article_ids: Set[str]
    is_valid: bool  # True if no unknown IDs
    
    def format_error_message(self) -> str:
        """Generate clear error message for the Writer prompt."""
        if self.is_valid:
            return ""
        
        ids_list = ", ".join(sorted(self.unknown_article_ids))
        return (
            "⚠️ CRITICAL: YOUR PREVIOUS DRAFT CONTAINED INVALID ARTICLE IDs ⚠️\n"
            f"These IDs do NOT exist in the source material: {ids_list}\n"
            "You MUST rewrite using ONLY the 9-character IDs from the SOURCE MATERIAL above.\n"
            "Do NOT invent IDs. Every (XXXXXXXXX) citation must match an ID from the articles provided."
        )


def validate_citations(
    text: str,
    allowed_article_ids: Collection[str],
) -> CitationReport:
    """
    Extract all 9-character article IDs from text and check against allowed set.
    
    Args:
        text: The analysis text to validate
        allowed_article_ids: Set of valid article IDs from source material
        
    Returns:
        CitationReport with validation results
    """
    # Regex: exactly 9 alphanumeric chars in parentheses
    # This will NOT match Topic refs like (Topic:fed_policy.drivers)
    pattern = r"\(([A-Za-z0-9]{9})\)"
    found_ids = set(re.findall(pattern, text))
    
    allowed_set = set(allowed_article_ids)
    unknown = found_ids - allowed_set
    
    return CitationReport(
        article_ids_in_text=found_ids,
        unknown_article_ids=unknown,
        is_valid=len(unknown) == 0,
    )


if __name__ == "__main__":
    # Quick test
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
    
    The real impact (REALID123) is clear.
    
    Topic references like (Topic:fed_policy.drivers) should be ignored.
    """
    
    print("\n📋 ALLOWED IDs:")
    for aid in sorted(allowed_ids):
        print(f"   • {aid}")
    
    print("\n📝 TEST TEXT:")
    print(test_text)
    
    print("\n🔍 VALIDATION RESULT:")
    report = validate_citations(test_text, allowed_ids)
    
    print(f"   IDs found in text: {sorted(report.article_ids_in_text)}")
    print(f"   Unknown IDs: {sorted(report.unknown_article_ids)}")
    print(f"   Is valid: {report.is_valid}")
    
    if not report.is_valid:
        print("\n⚠️ ERROR MESSAGE FOR PROMPT:")
        print("-" * 40)
        print(report.format_error_message())
        print("-" * 40)
    
    # Assertions
    assert report.article_ids_in_text == {"Z7O1DCHS7", "K8M2NQWER", "A3B4C5D6E", "FAKEID999", "ABC123DEF", "REALID123"}
    assert report.unknown_article_ids == {"FAKEID999", "ABC123DEF"}
    assert not report.is_valid
    
    print("\n✅ ALL TESTS PASSED!")
    print("=" * 60)
