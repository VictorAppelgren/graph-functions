"""
Synthesis Scout Agent

Finds cross-topic synthesis opportunities by exploring related topics.
"""

import json
from pydantic import BaseModel, Field
from typing import List
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.synthesis_scout.graph_strategy import explore_graph
from src.analysis_agents.synthesis_scout.prompt import SYNTHESIS_SCOUT_PROMPT
from src.analysis_agents.utils.extract_article_ids import extract_article_ids_from_list, extract_topic_references_from_list
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import StrOutputParser


class SynthesisOpportunities(BaseModel):
    """Output model for Synthesis Scout"""
    opportunities: List[str] = Field(
        default=[],
        max_items=3,
        description="Specific 'A + B = C' synthesis opportunities"
    )
    article_ids_used: List[str] = Field(
        default=[],
        description="Article IDs cited in the opportunities"
    )
    topic_references_used: List[dict] = Field(
        default=[],
        description="Topic references cited (e.g., fed_policy.executive_summary)"
    )


class SynthesisScoutAgent(BaseAgent):
    """
    Agent 0B: Synthesis Scout
    
    Explores related topics to find cross-topic synthesis opportunities.
    """
    
    def __init__(self):
        super().__init__("SynthesisScout")
    
    def run(self, topic_id: str, section: str, section_focus: str = "") -> SynthesisOpportunities:
        """
        Find cross-topic synthesis opportunities.
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section (fundamental/medium/current)
            section_focus: Section focus text (horizon, style, goals)
            
        Returns:
            SynthesisOpportunities with opportunities and article IDs
        """
        self._log(f"Exploring graph for {topic_id}/{section}")
        
        # Step 1: Explore graph
        graph_data = explore_graph(topic_id, section)
        
        if not graph_data.get("related_topics"):
            self._log("No related topics found - skipping")
            return SynthesisOpportunities(opportunities=[])
        
        related_topics = graph_data.get("related_topics", [])
        self._log(f"Found {len(related_topics)} related topics")
        if related_topics:
            topic_names = [t.get('topic_name', 'unknown') for t in related_topics[:5]]
            self._log(f"Related topics: {', '.join(topic_names)}")
        
        # Step 2: Load market context
        from src.market_data.loader import get_market_context_for_prompt
        market_context = get_market_context_for_prompt(topic_id)
        
        # Step 3: Format data for LLM
        topic_articles_str = self._format_articles(graph_data.get("topic_articles", []))
        related_topics_str = self._format_related_topics(graph_data.get("related_topics", []))
        
        # Step 4: Call LLM
        prompt = SYNTHESIS_SCOUT_PROMPT.format(
            topic_name=graph_data.get("topic_name", topic_id),
            topic_id=topic_id,
            section=section,
            section_focus=section_focus or "Multi-perspective synthesis",
            market_context=market_context,
            topic_articles=topic_articles_str,
            related_topics=related_topics_str
        )
        
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
            opportunities = data.get("opportunities", [])
            
            self._log(f"Found {len(opportunities)} synthesis opportunities")
            
            # Extract article IDs and topic references from the generated text
            article_ids = extract_article_ids_from_list(opportunities)
            topic_refs = extract_topic_references_from_list(opportunities)
            
            if article_ids:
                self._log(f"Article IDs used: {', '.join(article_ids[:5])}{'...' if len(article_ids) > 5 else ''}")
            if topic_refs:
                topic_strs = [f"{r['topic_id']}.{r['field']}" for r in topic_refs]
                self._log(f"Topic references used: {', '.join(topic_strs[:5])}{'...' if len(topic_strs) > 5 else ''}")
            
            return SynthesisOpportunities(
                opportunities=opportunities,
                article_ids_used=article_ids,
                topic_references_used=topic_refs
            )
            
        except Exception as e:
            self._log(f"Failed to parse LLM response: {e}")
            return SynthesisOpportunities(opportunities=[], article_ids_used=[], topic_references_used=[])
    
    def _format_articles(self, articles: List[dict]) -> str:
        """Format articles for prompt"""
        if not articles:
            return "No articles available"
        
        lines = []
        for i, art in enumerate(articles[:5], 1):  # Top 5 articles
            lines.append(f"{i}. ID: {art['id']}")
            lines.append(f"   Summary: {art['summary'][:200]}...")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_related_topics(self, related: List[dict]) -> str:
        """Format related topics for prompt"""
        if not related:
            return "No related topics found"
        
        lines = []
        for i, rel in enumerate(related, 1):
            lines.append(f"{i}. TOPIC: {rel['topic_name']} ({rel['topic_id']})")
            
            # Format articles from this related topic
            articles = rel.get('articles', [])
            if articles:
                article_ids = [a['id'] for a in articles[:3]]
                lines.append(f"   Articles ({len(articles)}): {', '.join(article_ids)}")
            else:
                lines.append(f"   Articles: None")
            
            if rel.get('executive_summary'):
                lines.append(f"   Executive Summary: {rel['executive_summary'][:300]}...")
            
            if rel.get('drivers'):
                lines.append(f"   Drivers: {rel['drivers'][:300]}...")
            
            lines.append("")
        
        return "\n".join(lines)


# Convenience function for testing
def run_synthesis_scout(topic_id: str, section: str) -> SynthesisOpportunities:
    """Run synthesis scout agent"""
    agent = SynthesisScoutAgent()
    return agent.run(topic_id, section)


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        topic_id = sys.argv[1]
        section = sys.argv[2] if len(sys.argv) > 2 else "fundamental"
        result = run_synthesis_scout(topic_id, section)
        print(f"\n=== SYNTHESIS OPPORTUNITIES ===")
        for i, opp in enumerate(result.opportunities, 1):
            print(f"{i}. {opp}")
