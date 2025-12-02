"""
Strategy Writer Agent

MISSION: Write world-class personalized strategy analysis.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from src.strategy_agents.base_agent import BaseStrategyAgent
from src.strategy_agents.strategy_writer.prompt import STRATEGY_WRITER_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT


class StrategyAnalysis(BaseModel):
    """Complete strategy analysis output."""
    executive_summary: str = Field(description="3-4 sentence overview")
    position_analysis: str = Field(description="2-3 paragraphs on position status")
    risk_analysis: str = Field(description="2-3 paragraphs on risks")
    opportunity_analysis: str = Field(description="2-3 paragraphs on opportunities")
    recommendation: str = Field(description="2-3 paragraphs with clear action")


class StrategyWriterAgent(BaseStrategyAgent):
    """
    Agent that writes comprehensive personalized strategy analysis.
    
    MISSION: Synthesize all material into world-class actionable intelligence.
    """
    
    def __init__(self):
        super().__init__("StrategyWriter")
    
    def run(
        self,
        material_package: Dict[str, Any],
        risk_assessment: Any,
        opportunity_assessment: Any,
        **kwargs
    ) -> StrategyAnalysis:
        """
        Write personalized strategy analysis.
        
        Args:
            material_package: Complete material from material_builder
            risk_assessment: Output from RiskAssessorAgent
            opportunity_assessment: Output from OpportunityFinderAgent
        
        Returns:
            StrategyAnalysis with complete personalized analysis
        """
        self._log("Writing strategy analysis")
        
        # Format all material for prompt
        topic_analyses = self._format_topic_analyses(material_package["topics"])
        market_context = self._format_market_context(material_package["topics"])
        risk_summary = self._format_risk_assessment(risk_assessment)
        opportunity_summary = self._format_opportunity_assessment(opportunity_assessment)
        
        # Log input summary
        self._log_input_summary(material_package, topic_analyses, market_context, risk_summary, opportunity_summary)
        
        # Build prompt
        prompt = STRATEGY_WRITER_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            user_strategy=material_package["user_strategy"],
            position_text=material_package["position_text"],
            topic_analyses=topic_analyses,
            market_context=market_context,
            risk_assessment=risk_summary,
            opportunity_assessment=opportunity_summary
        )
        
        # Get LLM analysis
        llm = get_llm(ModelTier.COMPLEX)
        analysis = run_llm_decision(llm, prompt, StrategyAnalysis)
        
        # Log output summary
        self._log_output_summary(analysis)
        
        return analysis
    
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
    
    def _format_risk_assessment(self, assessment: Any) -> str:
        """Format risk assessment for prompt."""
        lines = [
            f"OVERALL RISK LEVEL: {assessment.overall_risk_level.upper()}",
            f"\nKEY RISKS: {assessment.key_risk_summary}",
            "\nDETAILED RISKS:"
        ]
        
        for category, risks in [
            ("POSITION", assessment.position_risks),
            ("MARKET", assessment.market_risks),
            ("THESIS", assessment.thesis_risks),
            ("EXECUTION", assessment.execution_risks)
        ]:
            if risks:
                lines.append(f"\n{category} RISKS:")
                for risk in risks:
                    lines.append(f"  - {risk.description} ({risk.probability} probability, {risk.timeframe})")
        
        return '\n'.join(lines)
    
    def _format_opportunity_assessment(self, assessment: Any) -> str:
        """Format opportunity assessment for prompt."""
        lines = [
            f"OVERALL OPPORTUNITY LEVEL: {assessment.overall_opportunity_level.upper()}",
            f"\nKEY OPPORTUNITIES: {assessment.key_opportunity_summary}",
            "\nDETAILED OPPORTUNITIES:"
        ]
        
        for category, opportunities in [
            ("POSITION OPTIMIZATION", assessment.position_optimization),
            ("STRATEGY ENHANCEMENT", assessment.strategy_enhancement),
            ("RELATED TRADES", assessment.related_opportunities),
            ("TACTICAL SETUPS", assessment.tactical_opportunities)
        ]:
            if opportunities:
                lines.append(f"\n{category}:")
                for opp in opportunities:
                    lines.append(f"  - {opp.description} ({opp.probability} probability, {opp.timeframe})")
        
        return '\n'.join(lines)
    
    def _log_input_summary(self, material: Dict, topic_analyses: str, market_context: str, risk_summary: str, opportunity_summary: str):
        """Log input material summary."""
        strategy_chars = len(material["user_strategy"])
        position_chars = len(material["position_text"])
        analyses_chars = len(topic_analyses)
        market_chars = len(market_context)
        risk_chars = len(risk_summary)
        opp_chars = len(opportunity_summary)
        total_input = strategy_chars + position_chars + analyses_chars + market_chars + risk_chars + opp_chars
        
        self._log(f"""
📥 INPUT MATERIAL:
   Strategy: {strategy_chars:,} chars
   Position: {position_chars:,} chars
   Topic Analyses: {analyses_chars:,} chars ({len(material['topics'])} topics)
   Market Context: {market_chars:,} chars
   Risk Assessment: {risk_chars:,} chars
   Opportunity Assessment: {opp_chars:,} chars
   ─────────────────────────────
   TOTAL INPUT: {total_input:,} chars (~{total_input//1000}K)
""")
    
    def _log_output_summary(self, analysis: StrategyAnalysis):
        """Log output summary."""
        exec_chars = len(analysis.executive_summary)
        pos_chars = len(analysis.position_analysis)
        risk_chars = len(analysis.risk_analysis)
        opp_chars = len(analysis.opportunity_analysis)
        rec_chars = len(analysis.recommendation)
        total_output = exec_chars + pos_chars + risk_chars + opp_chars + rec_chars
        
        self._log(f"""
📤 OUTPUT SUMMARY:
   Executive Summary: {exec_chars:,} chars
   Position Analysis: {pos_chars:,} chars
   Risk Analysis: {risk_chars:,} chars
   Opportunity Analysis: {opp_chars:,} chars
   Recommendation: {rec_chars:,} chars
   ─────────────────────────────
   TOTAL OUTPUT: {total_output:,} chars (~{total_output//1000}K)
""")
