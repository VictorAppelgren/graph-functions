"""
Risk Assessor Agent

MISSION: Identify ALL risks in user's strategy and position.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from src.strategy_agents.base_agent import BaseStrategyAgent
from src.strategy_agents.risk_assessor.prompt import RISK_ASSESSOR_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT


class Risk(BaseModel):
    """Single risk assessment."""
    description: str = Field(description="Clear description of the risk")
    probability: str = Field(description="low, medium, or high")
    impact: str = Field(description="Potential impact with price levels or % loss")
    timeframe: str = Field(description="When this could materialize")
    mitigation: str = Field(description="What to watch, how to hedge")


class RiskAssessment(BaseModel):
    """Complete risk assessment output."""
    position_risks: List[Risk] = Field(description="Risks in current position")
    market_risks: List[Risk] = Field(description="Risks from market conditions")
    thesis_risks: List[Risk] = Field(description="Risks in strategy thesis")
    execution_risks: List[Risk] = Field(description="Timing and execution risks")
    overall_risk_level: str = Field(description="low, medium, high, or critical")
    key_risk_summary: str = Field(description="2-3 sentence summary of top risks")


class RiskAssessorAgent(BaseStrategyAgent):
    """
    Agent that identifies risks in user's strategy and position.
    
    MISSION: Comprehensive risk analysis across position, market, thesis, and execution.
    """
    
    def __init__(self):
        super().__init__("RiskAssessor")
    
    def run(self, material_package: Dict[str, Any], **kwargs) -> RiskAssessment:
        """
        Assess risks in user's strategy.
        
        Args:
            material_package: Complete material from material_builder
        
        Returns:
            RiskAssessment with all identified risks
        """
        self._log("Assessing strategy risks")
        
        # Format material for prompt
        topic_analyses = self._format_topic_analyses(material_package["topics"])
        market_context = self._format_market_context(material_package["topics"])
        
        # Log input summary
        self._log_input_summary(material_package, topic_analyses, market_context)
        
        # Build prompt
        prompt = RISK_ASSESSOR_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            user_strategy=material_package["user_strategy"],
            position_text=material_package["position_text"],
            topic_analyses=topic_analyses,
            market_context=market_context
        )
        
        # Get LLM assessment
        llm = get_llm(ModelTier.COMPLEX)
        assessment = run_llm_decision(llm, prompt, RiskAssessment)
        
        total_risks = (
            len(assessment.position_risks) +
            len(assessment.market_risks) +
            len(assessment.thesis_risks) +
            len(assessment.execution_risks)
        )
        
        # Log output summary
        self._log_output_summary(assessment, total_risks)
        
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
    
    def _log_output_summary(self, assessment: RiskAssessment, total_risks: int):
        """Log output summary."""
        self._log(f"""
📤 OUTPUT SUMMARY:
   Total Risks Identified: {total_risks}
   - Position Risks: {len(assessment.position_risks)}
   - Market Risks: {len(assessment.market_risks)}
   - Thesis Risks: {len(assessment.thesis_risks)}
   - Execution Risks: {len(assessment.execution_risks)}
   ─────────────────────────────
   Overall Risk Level: {assessment.overall_risk_level.upper()}
   Key Summary: {assessment.key_risk_summary[:100]}...
""")
