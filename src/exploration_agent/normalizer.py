"""
Exploration Agent - Finding Output Normalizer

Ensures 100% frontend compatibility regardless of which LLM is used.

Frontend expectations (FlowPathViz.svelte + FindingsCards.svelte):
- flow_path: "A → B ↑ → C ↓" format (proper arrow character, direction indicators)
- confidence: lowercase string "high" | "medium" | "low"
- headline: max ~100 chars, no line breaks
- evidence: list of SavedExcerpt with all required fields
"""

import re
import unicodedata
from typing import Optional, List, Dict, Any
from src.exploration_agent.models import ExplorationResult, SavedExcerpt, ExplorationMode
from utils import app_logging

logger = app_logging.get_logger(__name__)


# =============================================================================
# ARROW NORMALIZATION
# =============================================================================

# All possible arrow-like characters LLMs might output
ARROW_VARIANTS = [
    "→",   # U+2192 RIGHTWARDS ARROW (correct)
    "->",  # ASCII arrow
    "=>",  # Fat arrow
    "-->", # Double dash arrow
    "—>",  # Em dash arrow
    "–>",  # En dash arrow
    "➔",   # U+2794 HEAVY WIDE-HEADED RIGHTWARD ARROW
    "➜",   # U+279C HEAVY ROUND-TIPPED RIGHTWARD ARROW
    "➤",   # U+27A4 BLACK RIGHTWARDS ARROWHEAD
    "▶",   # U+25B6 BLACK RIGHT-POINTING TRIANGLE
    "►",   # U+25BA BLACK RIGHT-POINTING POINTER
    "⟶",   # U+27F6 LONG RIGHTWARD ARROW
    "⇒",   # U+21D2 RIGHTWARD DOUBLE ARROW
    "⇨",   # U+21E8 RIGHTWARD WHITE ARROW
    "→",   # U+F0AE (Private use - some fonts)
]

# Proper arrow with spacing
CANONICAL_ARROW = " → "


def normalize_flow_path(flow_path: str) -> str:
    """
    Normalize flow_path to canonical format for FlowPathViz.svelte.

    Input (various LLM outputs):
        "china_stimulus->copper->fed_policy"
        "China Stimulus => Copper↑ => Fed Policy↓"
        "china_stimulus → copper ↑ → fed_policy ↓"

    Output (canonical):
        "china stimulus → copper ↑ → fed policy ↓"

    Rules:
    1. All arrow variants → " → " (with spaces)
    2. Underscores → spaces
    3. Direction indicators (↑↓) preserved and attached to node
    4. Trim excessive whitespace
    5. Proper capitalization (lowercase, first letter cap per word optional)
    """
    if not flow_path:
        return ""

    result = flow_path

    # Step 1: Normalize all arrow variants to canonical
    # Sort by length (longest first) to avoid partial replacements
    sorted_arrows = sorted(ARROW_VARIANTS, key=len, reverse=True)
    for arrow in sorted_arrows:
        result = result.replace(arrow, CANONICAL_ARROW)

    # Step 2: Fix arrows that might have incorrect spacing
    # Collapse multiple spaces around arrows
    result = re.sub(r'\s*→\s*', CANONICAL_ARROW, result)

    # Step 3: Normalize underscores to spaces (topic_id → topic id)
    result = result.replace("_", " ")

    # Step 4: Handle direction indicators - ensure they're attached to the node
    # "copper ↑ " → "copper ↑"
    # "copper↑" → "copper ↑" (add space before indicator)
    result = re.sub(r'(\w)\s*([↑↓])\s*', r'\1 \2 ', result)

    # Step 5: Clean up excessive whitespace
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()

    # Step 6: Ensure arrows have proper spacing (final pass)
    result = re.sub(r'\s*→\s*', CANONICAL_ARROW, result)

    # Step 7: Remove trailing/leading spaces from direction indicators at segment boundaries
    # " copper ↑ → " should stay, but " ↑ → " needs fixing
    result = re.sub(r'\s+→', ' →', result)
    result = re.sub(r'→\s+', '→ ', result)

    logger.debug("Normalized flow_path: '%s' → '%s'", flow_path[:50], result[:50])

    return result


# =============================================================================
# CONFIDENCE NORMALIZATION
# =============================================================================

VALID_CONFIDENCES = {"high", "medium", "low"}

# Common LLM variations
CONFIDENCE_MAP = {
    # High variants
    "high": "high",
    "HIGH": "high",
    "High": "high",
    "very high": "high",
    "strong": "high",
    "confident": "high",
    "1.0": "high",
    "0.9": "high",
    "0.8": "high",

    # Medium variants
    "medium": "medium",
    "MEDIUM": "medium",
    "Medium": "medium",
    "moderate": "medium",
    "mid": "medium",
    "0.7": "medium",
    "0.6": "medium",
    "0.5": "medium",

    # Low variants
    "low": "low",
    "LOW": "low",
    "Low": "low",
    "weak": "low",
    "uncertain": "low",
    "0.4": "low",
    "0.3": "low",
    "0.2": "low",
    "0.1": "low",
}


def normalize_confidence(confidence: Any) -> str:
    """
    Normalize confidence to one of: "high", "medium", "low"

    Handles:
    - Case variations: "HIGH" → "high"
    - Numeric values: 0.8 → "high"
    - Word variations: "strong" → "high"
    - Invalid values → "medium" (safe default)
    """
    if confidence is None:
        return "medium"

    # Convert to string and clean
    conf_str = str(confidence).strip().lower()

    # Direct match
    if conf_str in VALID_CONFIDENCES:
        return conf_str

    # Try mapping
    if conf_str in CONFIDENCE_MAP:
        return CONFIDENCE_MAP[conf_str]

    # Try numeric interpretation
    try:
        conf_float = float(conf_str)
        if conf_float >= 0.7:
            return "high"
        elif conf_float >= 0.4:
            return "medium"
        else:
            return "low"
    except ValueError:
        pass

    # Default to medium
    logger.warning("Unknown confidence value '%s', defaulting to 'medium'", confidence)
    return "medium"


# =============================================================================
# HEADLINE NORMALIZATION
# =============================================================================

MAX_HEADLINE_LENGTH = 100


def normalize_headline(headline: str) -> str:
    """
    Normalize headline for frontend display.

    Rules:
    1. Remove line breaks
    2. Collapse whitespace
    3. Truncate to max length with ellipsis
    4. Remove leading/trailing quotes if present
    """
    if not headline:
        return "Untitled Finding"

    result = headline

    # Remove line breaks
    result = result.replace("\n", " ").replace("\r", " ")

    # Collapse whitespace
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()

    # Remove surrounding quotes
    if (result.startswith('"') and result.endswith('"')) or \
       (result.startswith("'") and result.endswith("'")):
        result = result[1:-1]

    # Truncate if needed
    if len(result) > MAX_HEADLINE_LENGTH:
        result = result[:MAX_HEADLINE_LENGTH - 3] + "..."

    return result


# =============================================================================
# RATIONALE NORMALIZATION
# =============================================================================

def normalize_rationale(rationale: str) -> str:
    """
    Normalize rationale text.

    Rules:
    1. Preserve line breaks (markdown rendering)
    2. Ensure citations are in correct format
    3. Clean up excessive whitespace
    """
    if not rationale:
        return ""

    result = rationale

    # Fix common citation format issues
    # "(art_ABC123)" should stay, but "( art_ABC123 )" should be cleaned
    result = re.sub(r'\(\s+(art_\w+)\s+\)', r'(\1)', result)
    result = re.sub(r'\(\s+(sec_\w+)\s+\)', r'(\1)', result)

    # Collapse multiple blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Trim
    result = result.strip()

    return result


# =============================================================================
# EVIDENCE NORMALIZATION
# =============================================================================

def normalize_evidence(evidence: List[SavedExcerpt]) -> List[SavedExcerpt]:
    """
    Normalize evidence list for frontend.

    Rules:
    1. Ensure all required fields present
    2. Clean up excerpt text
    3. Validate source_id format
    """
    if not evidence:
        return []

    normalized = []
    for exc in evidence:
        # Ensure source_id has proper prefix
        source_id = exc.source_id
        if not source_id.startswith("art_") and not source_id.startswith("sec_"):
            # Try to infer type
            if "article" in exc.source_type.lower():
                source_id = f"art_{source_id}"
            else:
                source_id = f"sec_{source_id}"

        # Clean excerpt
        excerpt = exc.excerpt.strip() if exc.excerpt else ""

        # Clean why_relevant
        why = exc.why_relevant.strip() if exc.why_relevant else ""

        normalized.append(SavedExcerpt(
            excerpt=excerpt,
            source_id=source_id,
            source_type=exc.source_type,
            why_relevant=why,
            saved_at_topic=exc.saved_at_topic or "",
            saved_at_step=exc.saved_at_step or 0
        ))

    return normalized


# =============================================================================
# MAIN NORMALIZER FUNCTION
# =============================================================================

def normalize_finding_output(
    result: ExplorationResult,
    confidence: Optional[str] = None
) -> ExplorationResult:
    """
    Main normalization function - ensures 100% frontend compatibility.

    Call this before returning ExplorationResult to ensure it will
    render correctly in FlowPathViz.svelte and FindingsCards.svelte.

    Args:
        result: The raw ExplorationResult from exploration
        confidence: Optional confidence override (from critic verdict)

    Returns:
        Normalized ExplorationResult safe for frontend
    """
    logger.info("🔧 Normalizing finding output for frontend...")

    # Normalize each field
    normalized_headline = normalize_headline(result.headline)
    normalized_rationale = normalize_rationale(result.rationale)
    normalized_flow_path = normalize_flow_path(result.flow_path)
    normalized_evidence = normalize_evidence(result.evidence)

    # Log changes
    if normalized_headline != result.headline:
        logger.debug("  headline: '%s' → '%s'", result.headline[:30], normalized_headline[:30])
    if normalized_flow_path != result.flow_path:
        logger.debug("  flow_path: '%s' → '%s'", result.flow_path[:50], normalized_flow_path[:50])

    # Build normalized result
    normalized = ExplorationResult(
        headline=normalized_headline,
        rationale=normalized_rationale,
        flow_path=normalized_flow_path,
        evidence=normalized_evidence,
        target_topic_id=result.target_topic_id,
        target_strategy_id=result.target_strategy_id,
        mode=result.mode,
        exploration_steps=result.exploration_steps,
        success=result.success,
        error=result.error
    )

    logger.info("✅ Normalization complete")

    return normalized


# =============================================================================
# LLM FALLBACK NORMALIZER (if basic normalization isn't enough)
# =============================================================================

def llm_normalize_flow_path(flow_path: str, llm=None) -> str:
    """
    OPTIONAL: Use LLM to normalize flow_path if regex-based normalization fails.

    This is a fallback for truly malformed outputs. Only use if:
    1. Basic normalization produces invalid output
    2. The flow_path is important enough to warrant an LLM call

    Args:
        flow_path: The flow_path to normalize
        llm: Optional LLM instance (uses default if not provided)

    Returns:
        Normalized flow_path
    """
    if not flow_path:
        return ""

    # First try basic normalization
    basic_result = normalize_flow_path(flow_path)

    # Validate basic result
    if _is_valid_flow_path(basic_result):
        return basic_result

    # If invalid and LLM requested, use LLM
    if llm is None:
        logger.warning("Flow path validation failed, no LLM provided for fallback")
        return basic_result

    logger.info("🤖 Using LLM to normalize malformed flow_path...")

    prompt = f"""Convert this flow path to the exact format: "node1 → node2 ↑ → node3 ↓"

Rules:
- Use " → " (with spaces) between nodes
- Keep direction indicators (↑ for up, ↓ for down) attached to their node
- Remove underscores from node names
- Keep it simple - just the chain

Input: {flow_path}

Output ONLY the normalized flow path, nothing else:"""

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        content = content.strip().strip('"').strip("'")

        # Validate LLM output
        if _is_valid_flow_path(content):
            logger.info("✅ LLM normalization successful")
            return content
        else:
            logger.warning("⚠️ LLM output also invalid, using basic result")
            return basic_result

    except Exception as e:
        logger.error("LLM normalization failed: %s", e)
        return basic_result


def _is_valid_flow_path(flow_path: str) -> bool:
    """
    Validate flow_path format.

    Valid: "node1 → node2 → node3"
    Valid: "node1 → node2 ↑ → node3 ↓"
    Invalid: Empty, no arrows, weird characters
    """
    if not flow_path:
        return False

    # Must contain at least one canonical arrow
    if "→" not in flow_path:
        return False

    # Must have at least 2 segments
    segments = flow_path.split("→")
    if len(segments) < 2:
        return False

    # Each segment should have some content
    for seg in segments:
        cleaned = seg.replace("↑", "").replace("↓", "").strip()
        if not cleaned:
            return False

    return True


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("Testing normalize_flow_path...")

    test_cases = [
        # (input, expected_contains)
        ("china_stimulus->copper->fed_policy", "→"),
        ("china_stimulus => copper ↑ => fed_policy ↓", "↑"),
        ("A --> B --> C", "→"),
        ("gold ➔ inflation ➔ rates", "→"),
        ("", ""),
        ("single_node", "single node"),
    ]

    for input_val, expected in test_cases:
        result = normalize_flow_path(input_val)
        status = "✅" if expected in result else "❌"
        print(f"  {status} '{input_val[:30]}...' → '{result[:40]}...'")

    print("\nTesting normalize_confidence...")

    conf_cases = [
        ("HIGH", "high"),
        ("Medium", "medium"),
        (0.8, "high"),
        (0.5, "medium"),
        ("strong", "high"),
        ("unknown", "medium"),
    ]

    for input_val, expected in conf_cases:
        result = normalize_confidence(input_val)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {input_val} → {result} (expected {expected})")

    print("\nTesting normalize_headline...")

    headline_cases = [
        ("Short headline", "Short headline"),
        ("Line1\nLine2", "Line1 Line2"),
        ('"Quoted headline"', "Quoted headline"),
        ("A" * 150, "A" * 97 + "..."),
    ]

    for input_val, expected in headline_cases:
        result = normalize_headline(input_val)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_val[:20]}...' → '{result[:30]}...'")

    print("\n✅ All tests complete!")
