"""
Improve Strategy Text Function

Input: User's strategy text (thesis), asset, optional position text
Process: LLM enhances the text while preserving voice and core ideas
Output: Improved text + summary of changes

This function embodies Saga's philosophy: AI AMPLIFIES human judgment, doesn't replace it.
"""

import json
from typing import Optional
from pydantic import BaseModel

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION
from .prompt import IMPROVE_STRATEGY_PROMPT, MACRO_CONTEXT_SECTION, MACRO_CONTEXT_EMPTY

from utils.app_logging import get_logger

logger = get_logger(__name__)


class ImproveStrategyResult(BaseModel):
    """Result of strategy text improvement."""
    improved_text: str
    changes_summary: str


def improve_strategy_text(
    strategy_text: str,
    asset: str,
    position_text: Optional[str] = None,
    topic_context: Optional[str] = None,
) -> ImproveStrategyResult:
    """
    Improve the user's strategy thesis text.

    Args:
        strategy_text: The user's current strategy thesis
        asset: The primary asset (e.g., EURUSD, AAPL)
        position_text: Optional position/outlook text for context
        topic_context: Optional macro context from related topics

    Returns:
        ImproveStrategyResult with improved_text and changes_summary
    """
    logger.info(f"Improving strategy text for asset: {asset}")

    # Build macro context section
    if topic_context:
        macro_section = MACRO_CONTEXT_SECTION.format(context=topic_context)
    else:
        macro_section = MACRO_CONTEXT_EMPTY

    # Build the full prompt
    prompt = IMPROVE_STRATEGY_PROMPT.format(
        system_mission=SYSTEM_MISSION,
        asset=asset,
        strategy_text=strategy_text,
        position_text=position_text or "(No position details provided - thesis monitoring mode)",
        macro_context=macro_section,
    )

    # Use COMPLEX tier (DeepSeek) for smart, cost-effective strategy improvement
    llm = get_llm(ModelTier.COMPLEX)

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()

        # Parse JSON response
        # Handle potential markdown code blocks
        if content.startswith("```"):
            # Remove markdown code block
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        result = json.loads(content)

        improved_text = result.get("improved_text", "")
        changes_summary = result.get("changes_summary", "")

        if not improved_text:
            logger.warning("LLM returned empty improved_text, using original")
            improved_text = strategy_text
            changes_summary = "No changes made - original text preserved."

        logger.info(f"Strategy text improved. Changes: {changes_summary[:100]}...")

        return ImproveStrategyResult(
            improved_text=improved_text,
            changes_summary=changes_summary,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response was: {content[:500]}")
        # Return original with error note
        return ImproveStrategyResult(
            improved_text=strategy_text,
            changes_summary="Error: Could not process improvement. Original text preserved.",
        )
    except Exception as e:
        logger.error(f"Error improving strategy text: {e}")
        raise


def get_topic_context_for_strategy(username: str, strategy_id: str) -> Optional[str]:
    """
    Fetch relevant topic context for a strategy to enrich the improvement.

    Returns a summary of relevant topic analyses if available.
    """
    try:
        from src.api.backend_client import get_strategy
        from src.strategy_agents.material_builder import build_material_package

        # Get the strategy
        strategy = get_strategy(username, strategy_id)
        if not strategy:
            return None

        # Get topic mapping
        topics = strategy.get("topics", {})
        if not topics:
            return None

        # Build material package (this fetches topic analyses)
        material = build_material_package(
            user_strategy=strategy.get("user_input", {}).get("strategy_text", ""),
            position_text=strategy.get("user_input", {}).get("position_text", ""),
            topics=topics,
        )

        # Extract key context
        context_parts = []
        for topic_id, topic_data in material.get("topics", {}).items():
            if topic_data.get("current"):
                context_parts.append(f"**{topic_data.get('name', topic_id)}**: {topic_data['current'][:300]}...")

        if context_parts:
            return "\n\n".join(context_parts[:3])  # Top 3 topics

        return None

    except Exception as e:
        logger.warning(f"Could not fetch topic context: {e}")
        return None


if __name__ == "__main__":
    # Quick test with sample data
    test_strategy = """
    I think EURUSD is going higher because the Fed is done hiking and ECB still has more to go.
    Also dollar looks weak technically.
    """

    test_asset = "EURUSD"
    test_position = "Watching for entry around 1.0850"

    result = improve_strategy_text(
        strategy_text=test_strategy,
        asset=test_asset,
        position_text=test_position,
    )

    print("=" * 60)
    print("ORIGINAL:")
    print(test_strategy)
    print("\nIMPROVED:")
    print(result.improved_text)
    print("\nCHANGES:")
    print(result.changes_summary)
