"""
Depth Finder Agent

Deep dives into articles to find causal chain and quantification opportunities.
"""

from pydantic import BaseModel, Field
from typing import List
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.depth_finder.graph_strategy import explore_graph
from src.analysis_agents.depth_finder.prompt import DEPTH_FINDER_PROMPT
from src.analysis_agents.utils.extract_article_ids import extract_article_ids_from_list, extract_topic_references_from_list
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision


class DepthOpportunities(BaseModel):
    """Output model for Depth Finder"""
    causal_chain_opportunities: List[str] = Field(
        default=[],
        max_items=3,
        description="Opportunities to build explicit A→B→C chains"
    )
    quantification_targets: List[str] = Field(
        default=[],
        max_items=3,
        description="Vague claims that should be quantified"
    )
    article_ids_used: List[str] = Field(
        default=[],
        description="Article IDs cited in the opportunities"
    )
    topic_references_used: List[dict] = Field(
        default=[],
        description="Topic references cited (e.g., fed_policy.executive_summary)"
    )


class DepthLLMRaw(BaseModel):
    causal_chain_opportunities: List[str] = Field(default=[])
    quantification_targets: List[str] = Field(default=[])


class DepthFinderAgent(BaseAgent):
    """
    Agent 0D: Depth Finder
    
    Deep dives into articles to find causal chains and quantification opportunities.
    """
    
    def __init__(self):
        super().__init__("DepthFinder")
    
    def run(self, topic_id: str, section: str, section_focus: str = "") -> DepthOpportunities:
        """
        Find depth opportunities (causal chains, quantification).
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section (fundamental/medium/current)
            section_focus: Section focus text (horizon, style, goals)
            
        Returns:
            DepthOpportunities with chains, targets, and article IDs
        """
        self._log(f"Deep diving articles for {topic_id}/{section}")
        
        # Step 1: Explore graph
        graph_data = explore_graph(topic_id, section)
        
        if not graph_data.get("articles"):
            self._log("No articles found - skipping")
            return DepthOpportunities()
        
        self._log(f"Analyzing {len(graph_data['articles'])} articles")
        
        # Step 2: Load market context
        from src.market_data.loader import get_market_context_for_prompt
        market_context = get_market_context_for_prompt(topic_id)
        
        # Step 3: Format data for LLM
        articles_str = self._format_articles(graph_data.get("articles", []))
        
        # Step 4: Call LLM
        prompt = DEPTH_FINDER_PROMPT.format(
            topic_name=graph_data.get("topic_name", topic_id),
            topic_id=topic_id,
            section=section,
            section_focus=section_focus or "Deep analysis",
            market_context=market_context,
            articles=articles_str
        )
        
        self._log("==== INPUT SUMMARY ====")
        self._log(f"Articles: {len(graph_data.get('articles', []))}")
        self._log(f"Prompt length: {len(prompt)} chars, ~{len(prompt)//4} tokens")
        self._log("==== END INPUT SUMMARY ====")
        self._log("")

        # Use MEDIUM tier for depth finding (article analysis, not reasoning)
        llm = get_llm(ModelTier.MEDIUM)
        raw = run_llm_decision(chain=llm, prompt=prompt, model=DepthLLMRaw)
        self._log("Using MEDIUM tier for depth analysis")
        
        chains = raw.causal_chain_opportunities or []
        quants = raw.quantification_targets or []
        
        if len(chains) > 3:
            self._log(f"Truncating causal_chain_opportunities from {len(chains)} to 3")
            chains = chains[:3]
        if len(quants) > 3:
            self._log(f"Truncating quantification_targets from {len(quants)} to 3")
            quants = quants[:3]
        
        self._log(f"Found {len(chains)} causal chains, {len(quants)} quantification targets")
        
        all_text = chains + quants
        article_ids = extract_article_ids_from_list(all_text)
        topic_refs = extract_topic_references_from_list(all_text)
        
        if article_ids:
            self._log(f"Article IDs used: {', '.join(article_ids[:5])}{'...' if len(article_ids) > 5 else ''}")
        if topic_refs:
            topic_strs = [f"{r['topic_id']}.{r['field']}" for r in topic_refs]
            self._log(f"Topic references used: {', '.join(topic_strs[:5])}{'...' if len(topic_strs) > 5 else ''}")
        
        return DepthOpportunities(
            causal_chain_opportunities=chains,
            quantification_targets=quants,
            article_ids_used=article_ids,
            topic_references_used=topic_refs
        )
    
    def _format_articles(self, articles: List[dict]) -> str:
        """Format articles for prompt"""
        if not articles:
            return "No articles available"
        
        lines = []
        for i, art in enumerate(articles, 1):
            lines.append(f"{i}. ID: {art['id']}")
            lines.append(f"   Source: {art.get('source', 'Unknown')}")
            lines.append(f"   Published: {art.get('published_at', 'Unknown')}")
            
            # Use full summary if available
            summary = art.get('full_summary') or art.get('summary', '')
            lines.append(f"   Summary: {summary[:400]}...")
            
            if art.get('motivation'):
                lines.append(f"   Motivation: {art['motivation'][:200]}...")
            
            if art.get('implications'):
                lines.append(f"   Implications: {art['implications'][:200]}...")
            
            # Perspective scores
            scores = []
            if art.get('risk', 0) >= 2:
                scores.append(f"Risk:{art['risk']}")
            if art.get('opportunity', 0) >= 2:
                scores.append(f"Opp:{art['opportunity']}")
            if art.get('trend', 0) >= 2:
                scores.append(f"Trend:{art['trend']}")
            if art.get('catalyst', 0) >= 2:
                scores.append(f"Cat:{art['catalyst']}")
            
            if scores:
                lines.append(f"   Perspectives: {', '.join(scores)}")
            
            lines.append("")
        
        return "\n".join(lines)


# Convenience function for testing
def run_depth_finder(topic_id: str, section: str) -> DepthOpportunities:
    """Run depth finder agent"""
    agent = DepthFinderAgent()
    return agent.run(topic_id, section)


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        topic_id = sys.argv[1]
        section = sys.argv[2] if len(sys.argv) > 2 else "fundamental"
        result = run_depth_finder(topic_id, section)
        print(f"\n=== DEPTH OPPORTUNITIES ===")
        print(f"\nCausal Chains:")
        for i, chain in enumerate(result.causal_chain_opportunities, 1):
            print(f"{i}. {chain}")
        print(f"\nQuantification Targets:")
        for i, quant in enumerate(result.quantification_targets, 1):
            print(f"{i}. {quant}")
