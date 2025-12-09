"""
Writer Agent (UNIFIED VERSION)

Handles ALL writing scenarios with one unified method:
- Fresh write (no prior analysis)
- Update with new data (has prior analysis)
- Fix invalid IDs (has prior draft + error feedback)
- Quality rewrite (has prior draft + critic/source feedback)
"""

from pydantic import BaseModel, Field
from typing import Dict, Any
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.writer.graph_strategy import explore_graph
from src.analysis_agents.writer.prompt import (
    WRITER_PROMPT,
    build_previous_analysis_section,
    build_correction_section,
    get_task_instruction,
)
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.market_data.loader import get_market_context_for_prompt
from langchain_core.output_parsers import StrOutputParser


class WriterOutput(BaseModel):
    """Output model for Writer"""
    analysis_text: str = Field(
        description="The written analysis"
    )


class WriterAgent(BaseAgent):
    """
    Writer Agent (UNIFIED VERSION)
    
    Single entry point for all writing scenarios.
    """
    
    def __init__(self):
        super().__init__("Writer")
    
    # =========================================================================
    # UNIFIED WRITE METHOD - handles ALL scenarios
    # =========================================================================
    
    def write(
        self,
        topic_id: str,
        section: str,
        material: str,
        section_focus: str = "",
        pre_writing_results: Dict[str, Any] | None = None,
        previous_analysis: str | None = None,
        invalid_ids_feedback: str | None = None,
        critic_feedback: str | None = None,
        source_feedback: str | None = None,
    ) -> WriterOutput:
        """
        UNIFIED write method for ALL scenarios.
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section name
            material: Source material (articles + prior sections)
            section_focus: Section focus text
            pre_writing_results: Results from pre-writing agents
            previous_analysis: Existing analysis to update/fix (optional)
            invalid_ids_feedback: Error message about invalid IDs (optional)
            critic_feedback: Feedback from Critic agent (optional)
            source_feedback: Feedback from SourceChecker agent (optional)
        
        Returns:
            WriterOutput with analysis text
        """
        # Determine scenario for logging
        scenario = self._determine_scenario(
            previous_analysis, invalid_ids_feedback, critic_feedback, source_feedback
        )
        
        self._log(f"")
        self._log(f"{'='*60}")
        self._log(f"📝 WRITER: {topic_id}/{section}")
        self._log(f"   Scenario: {scenario}")
        self._log(f"{'='*60}")
        
        # Build dynamic sections
        previous_section = build_previous_analysis_section(previous_analysis)
        correction_section = build_correction_section(
            invalid_ids_feedback, critic_feedback, source_feedback
        )
        
        # Get task instruction based on context
        task_instruction = get_task_instruction(
            asset_name=topic_id,
            has_previous=bool(previous_analysis),
            has_invalid_ids=bool(invalid_ids_feedback),
            has_feedback=bool(critic_feedback or source_feedback),
        )
        
        # Format pre-writing guidance
        pre_writing_guidance = self._format_pre_writing_guidance(pre_writing_results or {})
        
        # Load market context
        market_context = get_market_context_for_prompt(topic_id)
        
        # Build the full prompt
        prompt = WRITER_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus or "Write comprehensive analysis",
            market_context=market_context,
            pre_writing_guidance=pre_writing_guidance,
            material=material,
            previous_analysis_section=previous_section,
            correction_section=correction_section,
            task_instruction=task_instruction,
            asset_name=topic_id,
            asset_id=topic_id,
        )
        
        # Log input summary
        self._log_input_summary(
            material=material,
            previous_analysis=previous_analysis,
            invalid_ids_feedback=invalid_ids_feedback,
            critic_feedback=critic_feedback,
            source_feedback=source_feedback,
            pre_writing_results=pre_writing_results,
            prompt=prompt,
        )
        
        # Invoke LLM
        llm = get_llm(ModelTier.COMPLEX)
        parser = StrOutputParser()
        chain = llm | parser
        
        response = chain.invoke(prompt)
        
        self._log(f"✅ Output: {len(response):,} chars")
        self._log(f"{'='*60}")
        self._log(f"")
        
        return WriterOutput(analysis_text=response)
    
    def _determine_scenario(
        self,
        previous_analysis: str | None,
        invalid_ids_feedback: str | None,
        critic_feedback: str | None,
        source_feedback: str | None,
    ) -> str:
        """Determine which scenario we're in for logging."""
        if invalid_ids_feedback:
            return "🔧 FIX_INVALID_IDS"
        if critic_feedback or source_feedback:
            return "🔄 QUALITY_REWRITE"
        if previous_analysis:
            return "📈 UPDATE_EXISTING"
        return "🆕 FRESH_WRITE"
    
    def _log_input_summary(
        self,
        material: str,
        previous_analysis: str | None,
        invalid_ids_feedback: str | None,
        critic_feedback: str | None,
        source_feedback: str | None,
        pre_writing_results: Dict[str, Any] | None,
        prompt: str,
    ) -> None:
        """Log detailed input summary."""
        self._log("==== INPUT SUMMARY ====")
        self._log(f"   Material: {len(material):,} chars")
        
        if previous_analysis:
            self._log(f"   Previous analysis: {len(previous_analysis):,} chars")
        
        if invalid_ids_feedback:
            self._log(f"   ⚠️ Invalid IDs feedback: {len(invalid_ids_feedback):,} chars")
        
        if critic_feedback:
            self._log(f"   Critic feedback: {len(critic_feedback):,} chars")
        
        if source_feedback:
            self._log(f"   Source feedback: {len(source_feedback):,} chars")
        
        # Count pre-writing results
        if pre_writing_results:
            synth_count = 0
            depth_count = 0
            contrarian_count = 0
            
            if "synthesis" in pre_writing_results and pre_writing_results["synthesis"]:
                syn = pre_writing_results["synthesis"]
                if hasattr(syn, "opportunities"):
                    synth_count = len(syn.opportunities)
            
            if "depth" in pre_writing_results and pre_writing_results["depth"]:
                depth = pre_writing_results["depth"]
                if hasattr(depth, "causal_chain_opportunities"):
                    depth_count = len(depth.causal_chain_opportunities)
            
            if "contrarian" in pre_writing_results and pre_writing_results["contrarian"]:
                con = pre_writing_results["contrarian"]
                if hasattr(con, "contrarian_opportunities"):
                    contrarian_count = len(con.contrarian_opportunities)
            
            self._log(f"   Pre-writing: synth={synth_count}, depth={depth_count}, contrarian={contrarian_count}")
        
        self._log(f"   Total prompt: {len(prompt):,} chars (~{len(prompt)//4:,} tokens)")
        self._log("==== END INPUT SUMMARY ====")
    
    # =========================================================================
    # LEGACY METHODS - kept for backwards compatibility
    # =========================================================================
    
    def run(
        self, 
        topic_id: str, 
        section: str,
        section_focus: str = "",
        pre_writing_results: Dict[str, Any] = None,
        **kwargs
    ) -> WriterOutput:
        """
        Legacy method - explores graph and writes.
        Use write() for the unified approach.
        """
        self._log(f"[LEGACY] Writing analysis for {topic_id}/{section}")
        
        # Get material from graph
        graph_data = explore_graph(topic_id, section)
        
        if not graph_data.get("articles"):
            self._log("No articles found - cannot write")
            return WriterOutput(analysis_text="No articles available for analysis.")
        
        # Format material
        material = self._format_material(graph_data)
        
        # Use unified write method
        return self.write(
            topic_id=topic_id,
            section=section,
            material=material,
            section_focus=section_focus,
            pre_writing_results=pre_writing_results,
        )
    
    def run_with_material(
        self,
        topic_id: str,
        section: str,
        material: str,
        section_focus: str = "",
        pre_writing_results: Dict[str, Any] | None = None,
        **kwargs,
    ) -> WriterOutput:
        """
        Legacy method - writes with provided material.
        Use write() for the unified approach.
        """
        self._log(f"[LEGACY] run_with_material for {topic_id}/{section}")
        
        return self.write(
            topic_id=topic_id,
            section=section,
            material=material,
            section_focus=section_focus,
            pre_writing_results=pre_writing_results,
        )
    
    def _format_material(self, graph_data: dict) -> str:
        """Format graph data for prompt with crystal clear structure"""
        lines = []
        
        lines.append("="*70)
        lines.append("📰 PRIMARY ARTICLES FOR THIS SECTION")
        lines.append("="*70)
        
        # Articles
        articles = graph_data.get("articles", [])
        if articles:
            for i, art in enumerate(articles, 1):
                lines.append(f"\nARTICLE {i}: ({art['id']})")
                lines.append(f"Source: {art.get('source', 'Unknown')}")
                lines.append(f"Published: {art.get('published_at', 'Unknown')}")
                
                # Use full summary if available
                summary = art.get('full_summary') or art.get('summary', '')
                lines.append(f"\nSummary:")
                lines.append(summary)
                
                if art.get('motivation'):
                    lines.append(f"\nMotivation: {art['motivation']}")
                
                if art.get('implications'):
                    lines.append(f"Implications: {art['implications']}")
                
                lines.append("-" * 70)
        else:
            lines.append("\nNo articles available.")
        
        # Related topics for synthesis
        related_topics = graph_data.get("related_topics", [])
        if related_topics:
            lines.append("\n" + "="*70)
            lines.append("🔗 RELATED TOPICS (for synthesis)")
            lines.append("="*70)
            
            for rt in related_topics[:5]:  # Limit to 5 most relevant
                lines.append(f"\n{rt.get('name', 'Unknown')} ({rt.get('relationship', 'RELATED')})")
                # Show relevant analysis from related topic
                for field in ['fundamental', 'medium', 'current', 'drivers']:
                    content = rt.get(field)
                    if content:
                        lines.append(f"  {field}: {content}")  # NO TRUNCATION!
                        break  # Show only first available section
                lines.append("-" * 70)
        
        # Existing analysis sections (for context)
        existing = graph_data.get("existing_analysis", {})
        if any(existing.values()):
            lines.append("\n" + "="*70)
            lines.append("📊 EXISTING ANALYSIS (for context)")
            lines.append("="*70)
            
            for section_name, content in existing.items():
                if content:
                    lines.append(f"\n{section_name.upper().replace('_', ' ')}:")
                    lines.append(content)  # NO TRUNCATION!
                    lines.append("-" * 70)
        
        return "\n".join(lines)
    
    def _format_pre_writing_guidance(self, results: Dict[str, Any]) -> str:
        """Format pre-writing agent results for prompt with clear structure"""
        if not results:
            return "No pre-writing guidance available."
        
        lines = []
        lines.append("="*70)
        lines.append("💡 PRE-WRITING AGENT GUIDANCE")
        lines.append("="*70)
        
        # Synthesis Scout
        if "synthesis" in results and results["synthesis"]:
            syn = results["synthesis"]
            if syn.opportunities:
                lines.append("\n🔗 SYNTHESIS OPPORTUNITIES (MUST USE):")
                for i, opp in enumerate(syn.opportunities, 1):
                    lines.append(f"  {i}. {opp}")
                
                # Show what sources were used
                if hasattr(syn, 'article_ids_used') and syn.article_ids_used:
                    lines.append(f"\n  Articles referenced: {', '.join(f'({aid})' for aid in syn.article_ids_used[:5])}")
                if hasattr(syn, 'topic_references_used') and syn.topic_references_used:
                    topic_strs = [f"(Topic:{r['topic_id']}.{r['field']})" for r in syn.topic_references_used[:5]]
                    lines.append(f"  Topics referenced: {', '.join(topic_strs)}")
                lines.append("")
        
        # Depth Finder
        if "depth" in results and results["depth"]:
            depth = results["depth"]
            if depth.causal_chain_opportunities or depth.quantification_targets:
                lines.append("🔍 DEPTH OPPORTUNITIES:")
                
                if depth.causal_chain_opportunities:
                    lines.append("  Causal Chains:")
                    for i, chain in enumerate(depth.causal_chain_opportunities, 1):
                        lines.append(f"    {i}. {chain}")
                
                if depth.quantification_targets:
                    lines.append("  Quantification Targets:")
                    for i, target in enumerate(depth.quantification_targets, 1):
                        lines.append(f"    {i}. {target}")
                
                # Show what sources were used
                if hasattr(depth, 'article_ids_used') and depth.article_ids_used:
                    lines.append(f"\n  Articles referenced: {', '.join(f'({aid})' for aid in depth.article_ids_used[:5])}")
                if hasattr(depth, 'topic_references_used') and depth.topic_references_used:
                    topic_strs = [f"(Topic:{r['topic_id']}.{r['field']})" for r in depth.topic_references_used[:5]]
                    lines.append(f"  Topics referenced: {', '.join(topic_strs)}")
                lines.append("")
        
        # Contrarian Finder
        if "contrarian" in results and results["contrarian"]:
            con = results["contrarian"]
            if con.consensus_view or con.contrarian_opportunities:
                lines.append("⚡ CONTRARIAN ANGLES (EXPLORE):")
                if con.consensus_view:
                    lines.append(f"  Consensus: {con.consensus_view}")
                if con.contrarian_opportunities:
                    lines.append("  Contrarian Views:")
                    for i, opp in enumerate(con.contrarian_opportunities, 1):
                        lines.append(f"    {i}. {opp}")
                
                # Show what sources were used
                if hasattr(con, 'article_ids_used') and con.article_ids_used:
                    lines.append(f"\n  Articles referenced: {', '.join(f'({aid})' for aid in con.article_ids_used[:5])}")
                if hasattr(con, 'topic_references_used') and con.topic_references_used:
                    topic_strs = [f"(Topic:{r['topic_id']}.{r['field']})" for r in con.topic_references_used[:5]]
                    lines.append(f"  Topics referenced: {', '.join(topic_strs)}")
                lines.append("")
        
        lines.append("="*70)
        return "\n".join(lines) if lines else "No pre-writing guidance available."


# Convenience function
def run_writer(
    topic_id: str, 
    section: str,
    section_focus: str = "",
    pre_writing_results: Dict[str, Any] = None
) -> WriterOutput:
    """Run writer agent"""
    agent = WriterAgent()
    return agent.run(topic_id, section, section_focus, pre_writing_results)


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        topic_id = sys.argv[1]
        section = sys.argv[2] if len(sys.argv) > 2 else "fundamental"
        result = run_writer(topic_id, section)
        print(f"\n=== ANALYSIS ===")
        print(result.analysis_text)
