"""
Opportunity Finder Agent

MISSION: Identify ALL opportunities aligned with user's strategy.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from src.strategy_agents.base_agent import BaseStrategyAgent
from src.strategy_agents.opportunity_finder.prompt import OPPORTUNITY_FINDER_PROMPT, SHARED_CITATION_AND_METHODOLOGY
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT


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
        
        # Get articles reference from material package
        articles_reference = material_package.get("articles_reference", "No referenced articles available.")
        
        # Build prompt
        prompt = OPPORTUNITY_FINDER_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            analysis_mode=analysis_mode,
            user_strategy=material_package["user_strategy"],
            position_text=material_package["position_text"],
            topic_analyses=topic_analyses,
            articles_reference=articles_reference,
            market_context=market_context,
            citation_rules=SHARED_CITATION_AND_METHODOLOGY,
        )
        
        # Get LLM assessment
        llm = get_llm(ModelTier.COMPLEX)
        assessment = run_llm_decision(llm, prompt, OpportunityAssessment)
        
        total_opportunities = (
            len(assessment.position_optimization) +
            len(assessment.strategy_enhancement) +
            len(assessment.related_opportunities) +
            len(assessment.tactical_opportunities)
        )
        
        # Log output summary
        self._log_output_summary(assessment, total_opportunities)
        
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
