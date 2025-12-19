"""
Critic Agent - Verifies and ranks exploration findings.

Single-shot LLM call that:
1. Verifies all citations are accurate
2. Checks chain validity
3. Ranks against existing items
4. Returns accept/reject verdict
"""
import json
from typing import Optional

from src.exploration_agent.critic.models import CriticInput, CriticVerdict
from src.exploration_agent.critic.prompt import CRITIC_SYSTEM_PROMPT, build_critic_context
from src.llm.config import get_llm, ModelTier
from utils import app_logging

logger = app_logging.get_logger(__name__)


class CriticAgent:
    """
    Critic agent that validates exploration findings.
    
    Unlike the explorer, this is a single-shot evaluation:
    - Receives finding + all source material
    - Verifies citations and chain
    - Returns verdict
    """
    
    def __init__(self):
        # Reuse COMPLEX tier – best available reasoning model
        self.llm = get_llm(ModelTier.COMPLEX)
    
    def evaluate(self, critic_input: CriticInput) -> CriticVerdict:
        """
        Evaluate a finding and return verdict.
        
        Args:
            critic_input: Finding + all source material + existing items
            
        Returns:
            CriticVerdict with accept/reject decision
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔍 CRITIC EVALUATION")
        logger.info("=" * 80)
        logger.info("📋 Finding: %s", critic_input.finding.headline[:80])
        logger.info("📚 Sources: %s articles, %s topic analyses", 
                   len(critic_input.articles), 
                   len(critic_input.topic_analyses))
        logger.info("📊 Existing %ss: %s", critic_input.mode, len(critic_input.existing_items))
        logger.info("-" * 80)
        
        # Build prompt
        system_prompt = CRITIC_SYSTEM_PROMPT.format(
            mode=critic_input.mode,
            mode_upper=critic_input.mode.upper(),
        )
        context = build_critic_context(critic_input)
        
        full_prompt = f"{system_prompt}\n\n{context}"
        
        # Log token estimate
        token_estimate = len(full_prompt) // 4
        logger.info("📝 Prompt tokens (est): %s", token_estimate)
        
        # Call LLM
        try:
            response = self.llm.invoke(full_prompt)
            
            # Extract content
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, dict):
                content = response.get('content', str(response))
            else:
                content = str(response)
            
            # Parse JSON
            verdict = self._parse_response(content)
            
            if verdict:
                self._log_verdict(verdict)
                return verdict
            else:
                logger.error("❌ Failed to parse critic response")
                return CriticVerdict(
                    accepted=False,
                    confidence=0.0,
                    reasoning="Failed to parse critic response",
                    rejection_reasons=["Internal error: could not parse LLM response"]
                )
                
        except Exception as e:
            logger.error("❌ Critic evaluation failed: %s", e, exc_info=True)
            return CriticVerdict(
                accepted=False,
                confidence=0.0,
                reasoning=f"Critic evaluation error: {e}",
                rejection_reasons=[f"Internal error: {e}"]
            )
    
    def _parse_response(self, content: str) -> Optional[CriticVerdict]:
        """Parse LLM response into CriticVerdict."""
        try:
            # Clean markdown code blocks
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            
            # Log thinking
            thinking = parsed.get("thinking", "")
            logger.info("🧠 Critic thinking: %s", app_logging.truncate_str(thinking, 150))
            
            # Extract verdict
            verdict_data = parsed.get("verdict", {})
            
            return CriticVerdict(
                accepted=verdict_data.get("accepted", False),
                confidence=verdict_data.get("confidence", 0.0),
                reasoning=verdict_data.get("reasoning", ""),
                replaces=verdict_data.get("replaces"),
                rejection_reasons=verdict_data.get("rejection_reasons", [])
            )
            
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s", e)
            logger.error("Raw content: %s", content[:500])
            return None
        except Exception as e:
            logger.error("Parse error: %s", e)
            return None
    
    def _log_verdict(self, verdict: CriticVerdict) -> None:
        """Log the verdict in a clear format."""
        logger.info("")
        logger.info("=" * 80)
        if verdict.accepted:
            logger.info("✅ VERDICT: ACCEPTED (confidence: %.2f)", verdict.confidence)
            if verdict.replaces:
                logger.info("   📍 Replaces existing #%s", verdict.replaces)
            else:
                logger.info("   📍 Will be added as new")
        else:
            logger.info("❌ VERDICT: REJECTED (confidence: %.2f)", verdict.confidence)
            for reason in verdict.rejection_reasons:
                logger.info("   ⚠️ %s", reason)
        logger.info("📝 Reasoning: %s", app_logging.truncate_str(verdict.reasoning, 200))
        logger.info("=" * 80)
