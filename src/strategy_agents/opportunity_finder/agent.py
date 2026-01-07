"""
Opportunity Finder Agent

MISSION: Identify ALL opportunities aligned with user's strategy.
"""

from typing import Dict, Any, List, Set
from pydantic import BaseModel, Field
from src.strategy_agents.base_agent import BaseStrategyAgent
from src.strategy_agents.opportunity_finder.prompt import OPPORTUNITY_FINDER_PROMPT, SHARED_CITATION_AND_METHODOLOGY
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.citations import validate_citations, extract_article_ids, build_citation_fix_prompt


class Opportunity(BaseModel):
    """Single opportunity assessment."""
    description: str = Field(description="Clear description of the opportunity")
    probability: str = Field(description="low, medium, or high")
    reward: str = Field(description="Potential reward with price targets or % gain")
    timeframe: str = Field(description="When to act and when to expect results")
    entry_exit: str = Field(description="Specific entry/exit levels")
    alignment: str = Field(description="How this fits with main strategy")


class OpportunityAssessment(BaseModel):
    """Complete opportunity assessment output."""
    position_optimization: List[Opportunity] = Field(description="Ways to optimize current position")
    strategy_enhancement: List[Opportunity] = Field(description="Factors enhancing the strategy")
    related_opportunities: List[Opportunity] = Field(description="Correlated or hedging trades")
    tactical_opportunities: List[Opportunity] = Field(description="Short-term tactical setups")
    overall_opportunity_level: str = Field(description="low, medium, high, or exceptional")
    key_opportunity_summary: str = Field(description="2-3 sentence summary of top opportunities")


class OpportunityFinderAgent(BaseStrategyAgent):
    """
    Agent that identifies opportunities aligned with user's strategy.
    
    MISSION: Comprehensive opportunity analysis across position, strategy, related trades, and tactics.
    """
    
    def __init__(self):
        super().__init__("OpportunityFinder")
    
    def run(self, material_package: Dict[str, Any], **kwargs) -> OpportunityAssessment:
        """
        Find opportunities in user's strategy.
        
        Args:
            material_package: Complete material from material_builder
        
        Returns:
            OpportunityAssessment with all identified opportunities
        """
        self._log("Finding strategy opportunities")
        # Determine mode from material package (canonical flag if present)
        has_position = material_package.get("has_position")
        if has_position is None:
            has_position = bool(material_package.get("position_text", "").strip())
        mode_label = "ACTIVE POSITION ANALYSIS" if has_position else "THESIS MONITORING (no active position)"
        self._log(f"Mode: {mode_label}")

        if has_position:
            analysis_mode = (
                "ACTIVE POSITION ANALYSIS: the user currently has a live position described "
                "in USER POSITION. You must give precise, concrete, position-specific "
                "opportunities (entries, exits, sizing) grounded ONLY in the provided "
                "strategy, position text, and market context."
            )
        else:
            analysis_mode = (
                "THESIS MONITORING (NO ACTIVE POSITION): the user has NO live position. "
                "You must NOT invent current trades, sizes, entries, stops, or PnL. "
                "Any position_optimization opportunities must be framed as potential "
                "future structures only, consistent with the fact that there is no "
                "open trade described."
            )
        
        # Format material for prompt
        topic_analyses = self._format_topic_analyses(material_package["topics"])
        market_context = self._format_market_context(material_package["topics"])
        
        # Log input summary
        self._log_input_summary(material_package, topic_analyses, market_context)
        
        # Get articles reference and relationship context from material package
        articles_reference = material_package.get("articles_reference", "No referenced articles available.")
        relationship_context = material_package.get("relationship_context", "No topic relationships available.")

        # Build prompt
        prompt = OPPORTUNITY_FINDER_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            analysis_mode=analysis_mode,
            user_strategy=material_package["user_strategy"],
            position_text=material_package["position_text"],
            topic_analyses=topic_analyses,
            relationship_context=relationship_context,
            articles_reference=articles_reference,
            market_context=market_context,
            citation_rules=SHARED_CITATION_AND_METHODOLOGY,
        )
        
        # Get allowed article IDs from material package
        allowed_ids = self._get_allowed_article_ids(material_package)
        self._log(f"Allowed article IDs for citation validation: {len(allowed_ids)}")

        # Get LLM assessment
        llm = get_llm(ModelTier.COMPLEX)
        assessment = run_llm_decision(llm, prompt, OpportunityAssessment)

        # Validate citations and retry if needed
        assessment = self._validate_and_fix_assessment(llm, prompt, assessment, allowed_ids)

        total_opportunities = (
            len(assessment.position_optimization) +
            len(assessment.strategy_enhancement) +
            len(assessment.related_opportunities) +
            len(assessment.tactical_opportunities)
        )

        # Log output summary
        self._log_output_summary(assessment, total_opportunities)

        return assessment

    def _get_allowed_article_ids(self, material_package: Dict[str, Any]) -> Set[str]:
        """Extract allowed article IDs from material package."""
        allowed = set()

        # From referenced_articles dict
        referenced = material_package.get("referenced_articles", {})
        if isinstance(referenced, dict):
            allowed.update(referenced.keys())

        # Also extract from topic analyses (in case some weren't fetched)
        topic_analyses = material_package.get("topic_analyses", "")
        if topic_analyses:
            allowed.update(extract_article_ids(topic_analyses))

        return allowed

    def _validate_and_fix_assessment(
        self,
        llm,
        prompt: str,
        assessment: OpportunityAssessment,
        allowed_ids: Set[str],
    ) -> OpportunityAssessment:
        """
        Validate citations in assessment and retry ONCE if invalid.
        """
        # Combine all text for validation
        all_text_parts = [assessment.key_opportunity_summary]
        for opp in assessment.position_optimization + assessment.strategy_enhancement + assessment.related_opportunities + assessment.tactical_opportunities:
            all_text_parts.extend([
                opp.description, opp.reward, opp.entry_exit, opp.alignment
            ])
        all_text = "\n".join(all_text_parts)

        # Validate
        report = validate_citations(all_text, allowed_article_ids=allowed_ids)

        if report.is_valid:
            self._log("Citation validation PASSED")
            return assessment

        # Invalid - need to retry
        self._log(f"Citation validation FAILED | invalid_ids={sorted(report.invalid_article_ids)} | retrying...")

        # Build retry prompt with error feedback
        retry_prompt = build_citation_fix_prompt(
            original_prompt=prompt,
            original_output=all_text,
            report=report,
        )

        # Retry generation
        try:
            assessment = run_llm_decision(llm, retry_prompt, OpportunityAssessment)

            # Validate again
            all_text_parts_retry = [assessment.key_opportunity_summary]
            for opp in assessment.position_optimization + assessment.strategy_enhancement + assessment.related_opportunities + assessment.tactical_opportunities:
                all_text_parts_retry.extend([
                    opp.description, opp.reward, opp.entry_exit, opp.alignment
                ])
            all_text_retry = "\n".join(all_text_parts_retry)
            report_retry = validate_citations(all_text_retry, allowed_article_ids=allowed_ids)

            if report_retry.is_valid:
                self._log("Citation validation PASSED after retry")
            else:
                self._log(f"Citation validation still FAILED after retry | invalid_ids={sorted(report_retry.invalid_article_ids)}")
        except Exception as e:
            self._log(f"Citation retry failed: {e}")

        return assessment
    
    def _format_topic_analyses(self, topics: Dict[str, Dict]) -> str:
        """Format topic analyses for prompt."""
        lines = []
        for topic_id, data in topics.items():
            lines.append(f"\n{'='*70}")
            lines.append(f"TOPIC: {data['name']} ({topic_id})")
            lines.append('='*70)
            
            for section in ['fundamental', 'medium', 'current', 'drivers']:
                content = data.get(section, '')
                if content:
                    lines.append(f"\n{section.upper()}:")
                    lines.append(content)
        
        return '\n'.join(lines) if lines else "No topic analyses available"
    
    def _format_market_context(self, topics: Dict[str, Dict]) -> str:
        """Format market context for prompt."""
        lines = []
        for topic_id, data in topics.items():
            context = data.get('market_context', '')
            if context:
                lines.append(f"{data['name']}: {context}")
        
        return '\n'.join(lines) if lines else "No market data available"
    
    def _log_input_summary(self, material: Dict, topic_analyses: str, market_context: str):
        """Log input material summary."""
        strategy_chars = len(material["user_strategy"])
        position_chars = len(material["position_text"])
        analyses_chars = len(topic_analyses)
        market_chars = len(market_context)
        total_input = strategy_chars + position_chars + analyses_chars + market_chars
        
        self._log(f"""
📥 INPUT MATERIAL:
   Strategy: {strategy_chars:,} chars
   Position: {position_chars:,} chars
   Topic Analyses: {analyses_chars:,} chars ({len(material['topics'])} topics)
   Market Context: {market_chars:,} chars
   ─────────────────────────────
   TOTAL INPUT: {total_input:,} chars (~{total_input//1000}K)
""")
    
    def _log_output_summary(self, assessment: OpportunityAssessment, total_opportunities: int):
        """Log output summary."""
        self._log(f"""
📤 OUTPUT SUMMARY:
   Total Opportunities Identified: {total_opportunities}
   - Position Optimization: {len(assessment.position_optimization)}
   - Strategy Enhancement: {len(assessment.strategy_enhancement)}
   - Related Opportunities: {len(assessment.related_opportunities)}
   - Tactical Opportunities: {len(assessment.tactical_opportunities)}
   ─────────────────────────────
   Overall Opportunity Level: {assessment.overall_opportunity_level.upper()}
   Key Summary: {assessment.key_opportunity_summary[:100]}...
""")
