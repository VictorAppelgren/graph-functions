"""
Topic Mapper Agent

Maps user's free-text asset description and strategy to actual graph topics using LLM.
Converts custom_user_analysis/topic_discovery.py to agent pattern.
"""

from typing import Dict, List
from pydantic import BaseModel
from src.strategy_agents.base_agent import BaseStrategyAgent
from src.strategy_agents.topic_mapper.graph_strategy import explore_graph
from src.strategy_agents.topic_mapper.prompt import TOPIC_MAPPER_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from langchain_core.output_parsers import StrOutputParser


class TopicMapping(BaseModel):
    """Output model for topic discovery."""
    primary_topics: List[str]
    driver_topics: List[str]
    reasoning: str


class TopicMapperAgent(BaseStrategyAgent):
    """
    Agent that maps user strategies to relevant graph topics.
    
    MISSION: Identify primary assets, driver topics, and correlated topics
    that are relevant to the user's trading strategy.
    """
    
    def __init__(self):
        super().__init__("TopicMapper")
    
    def run(
        self,
        asset_text: str,
        strategy_text: str,
        position_text: str = "",
        **kwargs
    ) -> Dict[str, List[str]]:
        """
        Discover relevant topics from graph based on user's strategy.
        
        Args:
            asset_text: User's asset description (e.g., "EURUSD", "US market")
            strategy_text: User's strategy description
            position_text: User's current position (optional)
        
        Returns:
            {
                "primary": ["eurusd", "dxy"],
                "drivers": ["fed_policy", "ecb_policy"],
                "correlated": ["usdjpy", "gbpusd"],
                "reasoning": "..."
            }
        """
        self._log(f"Mapping strategy to topics | asset={asset_text[:30]}")
        
        # Step 1: Get all available topics from graph
        graph_data = explore_graph()
        topic_list = graph_data.get("topics", [])
        
        if not topic_list:
            self._log("No topics found in graph", level="error")
            return {
                "primary": [],
                "drivers": [],
                "correlated": [],
                "reasoning": "No topics available in graph"
            }
        
        self._log(f"Found {len(topic_list)} topics in graph")
        
        # Step 2: Format topics for LLM
        topics_str = self._format_topic_list(topic_list)
        
        # Step 3: Call LLM with prompt
        prompt = TOPIC_MAPPER_PROMPT.format(
            asset_text=asset_text,
            strategy_text=strategy_text,
            position_text=position_text or "Not specified",
            topics_list=topics_str
        )
        
        llm = get_llm(ModelTier.COMPLEX)
        
        # Parse structured output
        mapping = run_llm_decision(
            llm,
            prompt,
            TopicMapping
        )
        
        # Step 4: Validate topic IDs exist
        valid_ids = {t["id"] for t in topic_list}
        primary = [tid for tid in mapping.primary_topics if tid in valid_ids]
        drivers = [tid for tid in mapping.driver_topics if tid in valid_ids]
        
        if not primary:
            self._log(f"No valid primary topics found for asset: {asset_text}", level="warning")
            # Fallback: try to find exact match
            primary = [t["id"] for t in topic_list if asset_text.lower() in t["name"].lower()][:1]
        
        self._log(f"Topics discovered | primary={len(primary)} drivers={len(drivers)}")
        
        # Step 5: Expand with graph relationships (correlated topics)
        correlated = self._discover_correlated_topics(primary, valid_ids, graph_data)
        
        return {
            "primary": primary,
            "drivers": drivers,
            "correlated": correlated,
            "reasoning": mapping.reasoning
        }
    
    def _format_topic_list(self, topics: List[Dict]) -> str:
        """Format topic list for LLM prompt."""
        lines = []
        for t in topics[:150]:  # Limit to avoid token overflow
            lines.append(f"  {t['id']} | {t['name']}")
        return "\n".join(lines)
    
    def _discover_correlated_topics(
        self,
        primary_topic_ids: List[str],
        valid_ids: set,
        graph_data: Dict,
        limit: int = 5
    ) -> List[str]:
        """
        Discover correlated topics via graph relationships.
        Returns up to `limit` correlated topic IDs.
        """
        if not primary_topic_ids:
            return []
        
        # Get correlations from graph_data (already fetched)
        correlations = graph_data.get("correlations", {})
        
        correlated = []
        for topic_id in primary_topic_ids:
            if topic_id in correlations:
                correlated.extend(correlations[topic_id])
        
        # Deduplicate and filter valid
        correlated = list(set(correlated))
        correlated = [tid for tid in correlated if tid in valid_ids and tid not in primary_topic_ids]
        
        return correlated[:limit]
