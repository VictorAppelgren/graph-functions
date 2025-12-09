"""
Improvement Analyzer Agent

Compares old vs. new articles to guide rewrite.
"""

import json
from pydantic import BaseModel, Field
from typing import List
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.improvement_analyzer.graph_strategy import explore_graph
from src.analysis_agents.improvement_analyzer.prompt import IMPROVEMENT_ANALYZER_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import StrOutputParser


class ImprovementGuidance(BaseModel):
    """Output model for Improvement Analyzer"""
    preserve_insights: List[str] = Field(
        default=[],
        max_items=3,
        description="Insights to preserve from existing analysis"
    )
    deepen_areas: List[str] = Field(
        default=[],
        max_items=3,
        description="Areas that need more depth"
    )
    update_areas: List[str] = Field(
        default=[],
        max_items=3,
        description="Areas invalidated by new articles"
    )
    gaps: List[str] = Field(
        default=[],
        max_items=3,
        description="Missing topics from new articles"
    )


class ImprovementAnalyzerAgent(BaseAgent):
    """
    Agent 0A: Improvement Analyzer
    
    Compares existing analysis with new articles to guide rewrite.
    """
    
    def __init__(self):
        super().__init__("ImprovementAnalyzer")
    
    def run(self, topic_id: str, section: str, **kwargs) -> ImprovementGuidance:
        """
        Analyze improvements needed.
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section (fundamental/medium/current)
        
        Returns:
            ImprovementGuidance with preserve/deepen/update/gaps
        """
        self._log(f"Analyzing improvements for {topic_id}/{section}")
        
        # Step 1: Explore graph
        graph_data = explore_graph(topic_id, section)
        
        # If no existing analysis, skip
        if not graph_data.get("existing_analysis"):
            self._log("No existing analysis - skipping")
            return ImprovementGuidance()
        
        old_articles = graph_data.get("old_articles", [])
        new_articles = graph_data.get("new_articles", [])
        
        # If no new articles, skip
        if not new_articles:
            self._log("No new articles - skipping")
            return ImprovementGuidance()
        
        self._log(f"Comparing {len(old_articles)} old articles vs {len(new_articles)} new articles")
        if old_articles:
            self._log(f"Old articles: {[a.get('id', 'unknown')[:20] for a in old_articles[:3]]}")
        if new_articles:
            self._log(f"New articles: {[a.get('id', 'unknown')[:20] for a in new_articles[:3]]}")
        
        # Step 2: Format data for LLM
        existing_analysis = graph_data.get("existing_analysis", "")[:1000]  # Limit length
        old_articles_str = self._format_articles(graph_data.get("old_articles", []))
        new_articles_str = self._format_articles(graph_data.get("new_articles", []))
        
        # Step 3: Call LLM
        prompt = IMPROVEMENT_ANALYZER_PROMPT.format(
            topic_name=graph_data.get("topic_name", topic_id),
            topic_id=topic_id,
            section=section,
            existing_analysis=existing_analysis,
            old_articles=old_articles_str,
            new_articles=new_articles_str
        )
        
        self._log("==== INPUT SUMMARY ====")
        self._log(f"Existing analysis: {len(existing_analysis)} chars")
        self._log(f"Old articles: {len(old_articles)}, new articles: {len(new_articles)}")
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
            
            self._log(f"Found guidance: {len(data.get('preserve_insights', []))} preserve, "
                     f"{len(data.get('deepen_areas', []))} deepen, "
                     f"{len(data.get('update_areas', []))} update, "
                     f"{len(data.get('gaps', []))} gaps")
            
            return ImprovementGuidance(
                preserve_insights=data.get("preserve_insights", []),
                deepen_areas=data.get("deepen_areas", []),
                update_areas=data.get("update_areas", []),
                gaps=data.get("gaps", [])
            )
            
        except Exception as e:
            self._log(f"Failed to parse LLM response: {e}")
            return ImprovementGuidance()
    
    def _format_articles(self, articles: List[dict]) -> str:
        """Format articles for prompt"""
        if not articles:
            return "No articles"
        
        lines = []
        for i, art in enumerate(articles[:10], 1):  # Limit to 10
            lines.append(f"{i}. ID: {art['id']}")
            lines.append(f"   Summary: {art.get('summary', '')[:150]}...")
            lines.append(f"   Published: {art.get('published_at', 'Unknown')}")
            lines.append("")
        
        return "\n".join(lines)


# Convenience function for testing
def run_improvement_analyzer(topic_id: str, section: str) -> ImprovementGuidance:
    """Run improvement analyzer agent"""
    agent = ImprovementAnalyzerAgent()
    return agent.run(topic_id, section)


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        topic_id = sys.argv[1]
        section = sys.argv[2] if len(sys.argv) > 2 else "fundamental"
        result = run_improvement_analyzer(topic_id, section)
        print(f"\n=== IMPROVEMENT GUIDANCE ===")
        print(f"\nPreserve:")
        for i, item in enumerate(result.preserve_insights, 1):
            print(f"{i}. {item}")
        print(f"\nDeepen:")
        for i, item in enumerate(result.deepen_areas, 1):
            print(f"{i}. {item}")
        print(f"\nUpdate:")
        for i, item in enumerate(result.update_areas, 1):
            print(f"{i}. {item}")
        print(f"\nGaps:")
        for i, item in enumerate(result.gaps, 1):
            print(f"{i}. {item}")
