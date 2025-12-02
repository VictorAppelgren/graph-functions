"""
Position Analyzer Agent

Analyzes user's current position, exposure, and market alignment.
"""

from typing import Dict, Any
from pydantic import BaseModel
from src.strategy_agents.base_agent import BaseStrategyAgent
from src.strategy_agents.position_analyzer.prompt import POSITION_ANALYZER_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import StrOutputParser


class PositionAnalysis(BaseModel):
    """Output model for position analysis."""
    exposure_summary: str  # Long/short, size, duration
    risk_factors: str  # Key risks to position
    opportunity_factors: str  # Opportunities aligned with position
    market_alignment: str  # How position aligns with current market


class PositionAnalyzerAgent(BaseStrategyAgent):
    """
    Agent that analyzes user's current position and exposure.
    
    MISSION: Assess position exposure, risks, opportunities, and market alignment.
    """
    
    def __init__(self):
        super().__init__("PositionAnalyzer")
    
    def run(
        self,
        strategy_text: str,
        position_text: str,
        topic_analyses: Dict[str, Any],
        market_contexts: Dict[str, str],
        **kwargs
    ) -> PositionAnalysis:
        """
        Analyze user's position.
        
        Args:
            strategy_text: User's strategy description
            position_text: User's current position
            topic_analyses: Analyses for relevant topics
            market_contexts: Market data for relevant topics
        
        Returns:
            PositionAnalysis with exposure, risks, opportunities, market alignment
        """
        self._log(f"Analyzing position | topics={len(topic_analyses)}")
        
        # Format topic analyses for prompt
        analyses_str = self._format_topic_analyses(topic_analyses, market_contexts)
        
        # Build prompt
        prompt = POSITION_ANALYZER_PROMPT.format(
            strategy_text=strategy_text,
            position_text=position_text,
            topic_analyses=analyses_str
        )
        
        # Call LLM
        llm = get_llm(ModelTier.COMPLEX)
        parser = StrOutputParser()
        chain = llm | parser
        
        response = chain.invoke(prompt)
        
        # Parse response into structured format
        # For now, return as single string (can enhance later)
        self._log("Position analysis complete")
        
        return PositionAnalysis(
            exposure_summary=self._extract_section(response, "EXPOSURE SUMMARY"),
            risk_factors=self._extract_section(response, "RISK FACTORS"),
            opportunity_factors=self._extract_section(response, "OPPORTUNITY FACTORS"),
            market_alignment=self._extract_section(response, "MARKET ALIGNMENT")
        )
    
    def _format_topic_analyses(
        self,
        topic_analyses: Dict[str, Any],
        market_contexts: Dict[str, str]
    ) -> str:
        """Format topic analyses for prompt."""
        lines = []
        
        for topic_id, analysis in topic_analyses.items():
            lines.append(f"\n{'='*70}")
            lines.append(f"TOPIC: {topic_id}")
            lines.append(f"{'='*70}")
            
            # Market context
            if topic_id in market_contexts:
                lines.append(f"\nMARKET DATA:")
                lines.append(market_contexts[topic_id])
            
            # Current analysis
            if "current" in analysis:
                lines.append(f"\nCURRENT ANALYSIS (0-3 weeks):")
                lines.append(analysis["current"][:500])
            
            # Medium analysis
            if "medium" in analysis:
                lines.append(f"\nMEDIUM ANALYSIS (3-6 months):")
                lines.append(analysis["medium"][:500])
        
        return "\n".join(lines)
    
    def _extract_section(self, response: str, section_name: str) -> str:
        """Extract a section from the LLM response."""
        # Simple extraction - look for section headers
        lines = response.split("\n")
        section_lines = []
        in_section = False
        
        for line in lines:
            if section_name.upper() in line.upper():
                in_section = True
                continue
            elif in_section and line.strip().startswith("==="):
                break
            elif in_section and line.strip():
                section_lines.append(line)
        
        return "\n".join(section_lines).strip() or "Not specified"
