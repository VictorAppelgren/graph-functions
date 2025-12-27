"""
Critic Agent - Mid-exploration feedback (ONE LLM call, fully dynamic)
"""
import json
from typing import Optional

from src.exploration_agent.critic.models import CriticFeedback
from src.exploration_agent.critic.prompt import CRITIC_SYSTEM_PROMPT, build_critic_context
from src.llm.config import get_llm, ModelTier
from utils import app_logging

logger = app_logging.get_logger(__name__)


class CriticAgent:
    """
    Mid-exploration critic - provides feedback at 50% progress.

    ONE LLM call does ALL validation work:
    - Citation completeness and accuracy
    - Chain completeness
    - Quality assessment
    - Actionable suggestions
    """

    def __init__(self):
        # Use MEDIUM tier (120B model) for cost efficiency
        self.llm = get_llm(ModelTier.MEDIUM)

    def review(
        self,
        finding_headline: str,
        finding_rationale: str,
        finding_flow_path: str,
        saved_excerpts: list,
        current_step: int,
        max_steps: int
    ) -> CriticFeedback:
        """
        Review draft finding and provide feedback.

        Args:
            finding_headline: Draft headline
            finding_rationale: Draft rationale with citations
            finding_flow_path: Draft flow path
            saved_excerpts: List of saved excerpts with source_ids
            current_step: Current exploration step
            max_steps: Maximum steps allowed

        Returns:
            CriticFeedback with suggestions and verdict
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔍 MID-EXPLORATION CRITIC")
        logger.info("=" * 80)
        logger.info("📋 Reviewing draft: %s", finding_headline[:60])
        logger.info("📊 Progress: Step %s/%s (%s%% complete)",
                   current_step, max_steps, int(current_step / max_steps * 100))
        logger.info("📚 Evidence: %s saved excerpts", len(saved_excerpts))
        logger.info("-" * 80)

        # Build prompt
        context = build_critic_context(
            finding_headline,
            finding_rationale,
            finding_flow_path,
            saved_excerpts,
            current_step,
            max_steps
        )

        full_prompt = f"{CRITIC_SYSTEM_PROMPT}\n\n{context}"

        # Log token estimate
        token_estimate = len(full_prompt) // 4
        logger.info("📝 Prompt tokens (est): %s", token_estimate)

        # ONE LLM call - does all validation
        try:
            response = self.llm.invoke(full_prompt)

            # Extract content
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, dict):
                content = response.get('content', str(response))
            else:
                content = str(response)

            # Parse into CriticFeedback
            feedback = self._parse_response(content)

            if feedback:
                self._log_feedback(feedback)
                return feedback
            else:
                logger.error("❌ Failed to parse critic response")
                return self._create_error_feedback("Failed to parse LLM response")

        except Exception as e:
            logger.error("❌ Critic review failed: %s", e, exc_info=True)
            return self._create_error_feedback(str(e))

    def _parse_response(self, content: str) -> Optional[CriticFeedback]:
        """Parse LLM response into CriticFeedback."""
        try:
            # Clean markdown code blocks and formatting
            content = content.strip()

            # Remove markdown code fences
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Remove markdown bold wrapping (**, **, etc.)
            # LLM sometimes wraps JSON in **{...}**
            while content.startswith("**") and not content.startswith("**\""):
                content = content[2:].lstrip()
            while content.endswith("**") and not content.endswith("\"**"):
                content = content[:-2].rstrip()

            # Try to find JSON object if there's extra text
            # Look for first { and last }
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            parsed = json.loads(content)

            # Log thinking
            thinking = parsed.get("thinking", "")
            logger.info("🧠 Critic thinking: %s", app_logging.truncate_str(thinking, 150))

            # Extract feedback
            feedback_data = parsed.get("feedback", {})

            return CriticFeedback(
                citation_issues=feedback_data.get("citation_issues", []),
                chain_gaps=feedback_data.get("chain_gaps", []),
                quality_score=feedback_data.get("quality_score", 0.0),
                suggestions=feedback_data.get("suggestions", []),
                verdict=feedback_data.get("verdict", "continue_exploring"),
                reasoning=feedback_data.get("reasoning", "")
            )

        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s", e)
            logger.error("Raw content: %s", content[:500])
            return None
        except Exception as e:
            logger.error("Parse error: %s", e)
            return None

    def _log_feedback(self, feedback: CriticFeedback) -> None:
        """Log feedback in clear format."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 CRITIC FEEDBACK")
        logger.info("   Quality Score: %.2f/1.0", feedback.quality_score)
        logger.info("   Verdict: %s", feedback.verdict.upper())
        logger.info("")

        if feedback.citation_issues:
            logger.info("   ⚠️ Citation Issues (%s):", len(feedback.citation_issues))
            for issue in feedback.citation_issues[:3]:
                logger.info("      - %s", issue)
            if len(feedback.citation_issues) > 3:
                logger.info("      ... and %s more", len(feedback.citation_issues) - 3)
        else:
            logger.info("   ✅ Citations: All good")

        if feedback.chain_gaps:
            logger.info("   ⚠️ Chain Gaps (%s):", len(feedback.chain_gaps))
            for gap in feedback.chain_gaps[:3]:
                logger.info("      - %s", gap)
            if len(feedback.chain_gaps) > 3:
                logger.info("      ... and %s more", len(feedback.chain_gaps) - 3)
        else:
            logger.info("   ✅ Chain: Complete")

        if feedback.suggestions:
            logger.info("   💡 Suggestions (%s):", len(feedback.suggestions))
            for sug in feedback.suggestions[:3]:
                logger.info("      - %s", sug)

        logger.info("")
        logger.info("📝 Reasoning: %s", app_logging.truncate_str(feedback.reasoning, 200))
        logger.info("=" * 80)

    def _create_error_feedback(self, error_msg: str) -> CriticFeedback:
        """Create error feedback."""
        return CriticFeedback(
            citation_issues=[],
            chain_gaps=[],
            quality_score=0.0,
            suggestions=[f"Internal error: {error_msg}"],
            verdict="continue_exploring",
            reasoning=f"Critic error: {error_msg}"
        )
