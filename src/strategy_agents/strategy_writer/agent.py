"""
Strategy Writer Agent

MISSION: Write world-class personalized strategy analysis.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from src.strategy_agents.base_agent import BaseStrategyAgent
from src.strategy_agents.strategy_writer.prompt import (
    STRATEGY_WRITER_PROMPT,
    SECTION_REWRITE_PROMPT,
    SHARED_CITATION_AND_METHODOLOGY,
)
from langchain_core.output_parsers import StrOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT


class StrategyAnalysis(BaseModel):
    """Complete strategy analysis output."""
    executive_summary: str = Field(
        description=(
            "High-compression overview of the strategy: current status vs market, core thesis, "
            "conviction, and primary recommendation in 3-4 elite, information-dense sentences."
        )
    )
    position_analysis: str = Field(
        description=(
            "Deep position readout: entry vs current market, sizing, time-in-trade, P&L context, "
            "and how the live or potential position expresses the thesis across timeframes."
        )
    )
    risk_analysis: str = Field(
        description=(
            "Cohesive narrative of the top risks across position, market, thesis, and execution, "
            "with levels, probabilities, mechanisms, and what to watch to avoid blind spots."
        )
    )
    opportunity_analysis: str = Field(
        description=(
            "Synthesis of the strongest asymmetric opportunities and trade expressions, with "
            "levels, catalysts, timing, and how they compound or hedge the core view."
        )
    )
    recommendation: str = Field(
        description=(
            "Crystal-clear action plan: hold/add/reduce/exit, concrete levels and time windows, "
            "and how to adapt as data comes in, written as if the trader executes on it today."
        )
    )
    scenarios_and_catalysts: str = Field(
        description=(
            "Bull/base/bear (and tail, if relevant) scenario map with probability-weighted paths, "
            "linked to an event and catalyst timeline and explicit triggers for upgrades, "
            "downgrades, or thesis invalidation."
        )
    )
    structuring_and_risk_management: str = Field(
        description=(
            "How to structure and risk-manage the trade: instrument choices, sizing frameworks, "
            "volatility and options tactics, hedges and correlated overlays, and execution/" 
            "liquidity guidance at a professional PM level."
        )
    )
    context_and_alignment: str = Field(
        description=(
            "How this strategy fits into the wider world: market positioning and flows, "
            "alignment vs house view and macro backdrop, and portfolio-level context such as "
            "concentration, diversification, and net exposure impact."
        )
    )


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
        # Determine mode from material package (canonical flag if present)
        has_position = material_package.get("has_position")
        if has_position is None:
            has_position = bool(material_package.get("position_text", "").strip())
        mode_label = "ACTIVE POSITION ANALYSIS" if has_position else "THESIS MONITORING (no active position)"
        self._log(f"Mode: {mode_label}")

        if has_position:
            analysis_mode = (
                "ACTIVE POSITION ANALYSIS: the user currently has a live position described "
                "in USER POSITION. All sections must speak about the actual trade "
                "(status, PnL, entry vs current price, sizing) using ONLY the provided "
                "strategy, position text, risk assessment, and opportunity assessment."
            )
        else:
            analysis_mode = (
                "THESIS MONITORING (NO ACTIVE POSITION): the user has NO live position. "
                "Your primary job is SCENARIO AND STRATEGIC ANALYSIS: explain what is "
                "going on in the relevant markets/sector, who the key movers and drivers "
                "are, and how bull/base/bear paths and catalysts could unfold over time. "
                "You must NOT describe them as currently long/short, and must NOT invent "
                "specific entries, stops, position sizes, or realized PnL. It is "
                "acceptable to briefly mention ways the thesis could eventually be "
                "expressed (for example, that a situation could reward exposure to "
                "certain assets, sectors, or styles), but do NOT design a full trade "
                "plan or over-emphasize structuring details in this mode. CRITICAL: In "
                "this mode, you MUST begin the EXECUTIVE SUMMARY with a clear sentence "
                "stating that there is no active position and that any trades discussed "
                "are potential future setups only (for example: 'There is currently NO "
                "ACTIVE POSITION; this is a thesis monitoring analysis and any trades are "
                "potential future setups only.'). Across ALL sections, any mention of "
                "losses, stop-loss hits, exposure, or PnL must be explicitly conditional "
                "and forward-looking (e.g. 'a potential position would lose X if...' or "
                "'this setup could trigger stop-losses on a hypothetical trade'), never "
                "written as if a live position is already taking those losses."
            )
        
        # Format all material for prompt
        topic_analyses = self._format_topic_analyses(material_package["topics"])
        market_context = self._format_market_context(material_package["topics"])
        risk_summary = self._format_risk_assessment(risk_assessment)
        opportunity_summary = self._format_opportunity_assessment(opportunity_assessment)
        
        # Log input summary
        self._log_input_summary(material_package, topic_analyses, market_context, risk_summary, opportunity_summary)
        
        # Get articles reference from material package
        articles_reference = material_package.get("articles_reference", "No referenced articles available.")
        
        # Build prompt
        prompt = STRATEGY_WRITER_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            analysis_mode=analysis_mode,
            user_strategy=material_package["user_strategy"],
            position_text=material_package["position_text"],
            topic_analyses=topic_analyses,
            articles_reference=articles_reference,
            market_context=market_context,
            citation_rules=SHARED_CITATION_AND_METHODOLOGY,
            risk_assessment=risk_summary,
            opportunity_assessment=opportunity_summary,
        )
        
        # Get LLM analysis
        llm = get_llm(ModelTier.COMPLEX)
        analysis = run_llm_decision(llm, prompt, StrategyAnalysis)

        # In thesis monitoring mode, de-emphasize the dedicated Position Analysis section
        # so that the frontend can simply hide it based on an empty string.
        if not has_position:
            analysis.position_analysis = ""

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
        scen_chars = len(analysis.scenarios_and_catalysts)
        struct_chars = len(analysis.structuring_and_risk_management)
        ctx_chars = len(analysis.context_and_alignment)
        total_output = (
            exec_chars
            + pos_chars
            + risk_chars
            + opp_chars
            + rec_chars
            + scen_chars
            + struct_chars
            + ctx_chars
        )
        
        self._log(f"""
📤 OUTPUT SUMMARY:
   Executive Summary: {exec_chars:,} chars
   Position Analysis: {pos_chars:,} chars
   Risk Analysis: {risk_chars:,} chars
   Opportunity Analysis: {opp_chars:,} chars
   Recommendation: {rec_chars:,} chars
   Scenarios & Catalysts: {scen_chars:,} chars
   Structuring & Risk Mgmt: {struct_chars:,} chars
   Context & Alignment: {ctx_chars:,} chars
   ─────────────────────────────
   TOTAL OUTPUT: {total_output:,} chars (~{total_output//1000}K)
""")

    def rewrite_section(
        self,
        section: str,
        current_content: str,
        feedback: str,
        material_package: Dict[str, Any],
    ) -> str:
        """
        Rewrite a single section based on user feedback.
        
        Args:
            section: Section key (e.g., "risk_analysis")
            current_content: Existing section content
            feedback: User's feedback/instructions
            material_package: Complete material from material_builder
        
        Returns:
            Rewritten section content as plain text
        """
        self._log(f"Rewriting section: {section}")
        self._log(f"Feedback: {feedback[:100]}...")
        
        # Format material for prompt
        topic_analyses = self._format_topic_analyses(material_package["topics"])
        articles_reference = material_package.get("articles_reference", "No referenced articles available.")
        
        # Format user feedback section (only include if feedback provided)
        if feedback and feedback.strip():
            user_feedback_section = f"""⚠️ CRITICAL - YOUR PRIMARY DIRECTIVE:
USER FEEDBACK:
{feedback}

You MUST address this feedback in your rewrite."""
        else:
            user_feedback_section = ""
        
        # Build prompt
        prompt = SECTION_REWRITE_PROMPT.format(
            section_name=section,
            current_content=current_content,
            user_feedback_section=user_feedback_section,
            topic_analyses=topic_analyses,
            articles_reference=articles_reference,
            citation_rules=SHARED_CITATION_AND_METHODOLOGY,
        )
        
        # Get LLM response as plain text
        llm = get_llm(ModelTier.COMPLEX)
        parser = StrOutputParser()
        chain = llm | parser
        
        result = chain.invoke(prompt)
        
        self._log(f"Rewritten section: {len(result)} chars")
        
        return result.strip()
