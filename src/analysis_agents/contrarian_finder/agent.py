"""
Contrarian Finder Agent

Challenges consensus by exploring contrarian (negatively correlated) assets.
"""

import json
from pydantic import BaseModel, Field
from typing import List
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.contrarian_finder.graph_strategy import explore_graph
from src.analysis_agents.contrarian_finder.prompt import CONTRARIAN_FINDER_PROMPT
from src.analysis_agents.utils.extract_article_ids import extract_article_ids_from_list, extract_topic_references_from_list
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import StrOutputParser


class ContrarianAngles(BaseModel):
    """Output model for Contrarian Finder"""
    consensus_view: str = Field(
        default="",
        description="What the market believes"
    )
    contrarian_opportunities: List[str] = Field(
        default=[],
        max_items=2,
        description="Contrarian angles with evidence"
    )
    article_ids_used: List[str] = Field(
        default=[],
        description="Article IDs cited in the opportunities"
    )
    topic_references_used: List[dict] = Field(
        default=[],
        description="Topic references cited (e.g., fed_policy.executive_summary)"
    )


class ContrarianFinderAgent(BaseAgent):
    """
    Agent 0C: Contrarian Finder
    
    Explores contrarian assets to challenge consensus.
    """
    
    def __init__(self):
        super().__init__("ContrarianFinder")
    
    def run(self, topic_id: str, section: str, section_focus: str = "") -> ContrarianAngles:
        """
        Find contrarian angles by exploring negatively correlated assets.
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section (fundamental/medium/current)
            section_focus: Section focus text (horizon, style, goals)
            
        Returns:
            ContrarianAngles with consensus, contrarian views, and article IDs
        """
        self._log(f"Exploring contrarian assets for {topic_id}/{section}")
        
        # Step 1: Explore graph
        graph_data = explore_graph(topic_id, section)
        
        if not graph_data.get("contrarian_assets"):
            self._log("No contrarian assets found - skipping")
            return ContrarianAngles()
        
        self._log(f"Found {len(graph_data['contrarian_assets'])} contrarian assets")
        
        # Step 2: Load market context
        from src.market_data.loader import get_market_context_for_prompt
        market_context = get_market_context_for_prompt(topic_id)
        
        # Step 3: Format data for LLM
        our_analysis = graph_data.get("our_analysis", "No existing analysis")
        contrarian_assets = graph_data.get("contrarian_assets", [])
        contrarian_str = self._format_contrarian_assets(contrarian_assets)
        
        # Step 4: Call LLM
        prompt = CONTRARIAN_FINDER_PROMPT.format(
            topic_name=graph_data.get("topic_name", topic_id),
            topic_id=topic_id,
            section=section,
            section_focus=section_focus or "Contrarian analysis",
            market_context=market_context,
            our_analysis=our_analysis[:500] if our_analysis else "No existing analysis",
            contrarian_assets=contrarian_str
        )
        
        exec_summaries = sum(1 for a in contrarian_assets if a.get("executive_summary"))
        
        self._log("==== INPUT SUMMARY ====")
        self._log(f"Contrarian assets: {len(contrarian_assets)} (executive_summaries: {exec_summaries})")
        self._log(f"Prompt length: {len(prompt)} chars, ~{len(prompt)//4} tokens")
        self._log("==== END INPUT SUMMARY ====")
        self._log("")

        llm = get_llm(ModelTier.COMPLEX)
        parser = StrOutputParser()
        chain = llm | parser
        
        response = chain.invoke(prompt)
        
        # Step 4: Parse response
        try:
            # Try to extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            data = json.loads(json_str)
            
            consensus = data.get("consensus_view", "")
            opportunities = data.get("contrarian_opportunities", [])
            
            self._log(f"Found consensus view and {len(opportunities)} contrarian angles")
            
            # Extract article IDs and topic references from all generated text
            all_text = [consensus] + opportunities
            article_ids = extract_article_ids_from_list(all_text)
            topic_refs = extract_topic_references_from_list(all_text)
            
            if article_ids:
                self._log(f"Article IDs used: {', '.join(article_ids[:5])}{'...' if len(article_ids) > 5 else ''}")
            if topic_refs:
                topic_strs = [f"{r['topic_id']}.{r['field']}" for r in topic_refs]
                self._log(f"Topic references used: {', '.join(topic_strs[:5])}{'...' if len(topic_strs) > 5 else ''}")
            
            return ContrarianAngles(
                consensus_view=consensus,
                contrarian_opportunities=opportunities,
                article_ids_used=article_ids,
                topic_references_used=topic_refs
            )
            
        except Exception as e:
            self._log(f"Failed to parse LLM response: {e}")
            return ContrarianAngles(consensus_view="", contrarian_opportunities=[], article_ids_used=[], topic_references_used=[])
    
    def _format_contrarian_assets(self, contrarian: List[dict]) -> str:
        """Format contrarian assets for prompt"""
        if not contrarian:
            return "No contrarian assets available"
        
        lines = []
        for i, asset in enumerate(contrarian, 1):
            lines.append(f"{i}. ASSET: {asset['topic_name']} ({asset['topic_id']})")
            
            if asset.get('analysis'):
                lines.append(f"   Analysis: {asset['analysis'][:400]}...")
            
            if asset.get('executive_summary'):
                lines.append(f"   Executive Summary: {asset['executive_summary'][:400]}...")
            
            lines.append("")
        
        return "\n".join(lines)


# Convenience function for testing
def run_contrarian_finder(topic_id: str, section: str) -> ContrarianAngles:
    """Run contrarian finder agent"""
    agent = ContrarianFinderAgent()
    return agent.run(topic_id, section)


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        topic_id = sys.argv[1]
        section = sys.argv[2] if len(sys.argv) > 2 else "fundamental"
        result = run_contrarian_finder(topic_id, section)
        print(f"\n=== CONTRARIAN ANGLES ===")
        print(f"Consensus: {result.consensus_view}")
        print(f"\nContrarian Opportunities:")
        for i, opp in enumerate(result.contrarian_opportunities, 1):
            print(f"{i}. {opp}")
