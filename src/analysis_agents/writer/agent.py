"""
Writer Agent

Writes initial analysis draft using all guidance from pre-writing agents.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.writer.graph_strategy import explore_graph
from src.analysis_agents.writer.prompt import WRITER_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from langchain_core.output_parsers import StrOutputParser


class WriterOutput(BaseModel):
    """Output model for Writer"""
    analysis_text: str = Field(
        description="The written analysis"
    )


class WriterAgent(BaseAgent):
    """
    Writer Agent
    
    Writes initial analysis draft using pre-writing guidance.
    """
    
    def __init__(self):
        super().__init__("Writer")
    
    def run(
        self, 
        topic_id: str, 
        section: str,
        section_focus: str = "",
        pre_writing_results: Dict[str, Any] = None,
        **kwargs
    ) -> WriterOutput:
        """
        Write analysis draft.
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section (fundamental/medium/current)
            section_focus: Section focus text (horizon, style, goals)
            pre_writing_results: Results from pre-writing agents
        
        Returns:
            WriterOutput with analysis text
        """
        self._log(f"Writing analysis for {topic_id}/{section}")
        
        # Step 1: Get material from graph
        graph_data = explore_graph(topic_id, section)
        
        if not graph_data.get("articles"):
            self._log("No articles found - cannot write")
            return WriterOutput(analysis_text="No articles available for analysis.")
        
        self._log(f"Writing with {len(graph_data['articles'])} articles")
        
        # Step 2: Load market context
        from src.market_data.loader import get_market_context_for_prompt
        market_context = get_market_context_for_prompt(topic_id)
        
        # Step 3: Format material
        material = self._format_material(graph_data)
        
        # Step 4: Format pre-writing guidance
        pre_writing_guidance = self._format_pre_writing_guidance(pre_writing_results or {})
        
        # Step 5: Call LLM
        prompt = WRITER_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus or "Write comprehensive analysis",
            market_context=market_context,
            pre_writing_guidance=pre_writing_guidance,
            material=material,
            asset_name=graph_data.get("topic_name", topic_id),
            asset_id=topic_id
        )
        
        llm = get_llm(ModelTier.COMPLEX)
        parser = StrOutputParser()
        chain = llm | parser
        
        response = chain.invoke(prompt)
        
        self._log(f"Analysis written: {len(response)} characters")
        return WriterOutput(analysis_text=response)
    
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
