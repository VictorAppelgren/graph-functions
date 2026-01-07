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
        
        llm = get_llm(ModelTier.SIMPLE)
        
        # Parse structured output
        mapping = run_llm_decision(
            llm,
            prompt,
            TopicMapping
        )
        
        # Step 4: STRICT validation - only exact matches against Neo4j topic IDs
        valid_ids = {t["id"] for t in topic_list}
        
        # Filter to only valid IDs (exact string match)
        primary = [tid for tid in mapping.primary_topics if tid in valid_ids]
        drivers = [tid for tid in mapping.driver_topics if tid in valid_ids]
        
        # Log what was filtered out
        filtered_count = len(mapping.primary_topics) + len(mapping.driver_topics) - len(primary) - len(drivers)
        if filtered_count > 0:
            self._log(f"⚠️ Filtered {filtered_count} invalid topic IDs from LLM response", level="warning")
        
        self._log(f"Topics discovered | primary={len(primary)} drivers={len(drivers)}")

        # Step 5: Expand with ALL graph relationship types
        related = self._discover_related_topics(primary, drivers, valid_ids, graph_data)

        self._log(
            f"Related topics via graph | correlated={len(related['correlated'])} "
            f"hedges={len(related['hedges'])} peers={len(related['peers'])} "
            f"influenced={len(related['influenced'])} influencers={len(related['influencers'])}"
        )

        return {
            "primary": primary,
            "drivers": drivers,
            "correlated": related["correlated"],
            "hedges": related["hedges"],
            "peers": related["peers"],
            "influenced": related["influenced"],
            "influencers": related["influencers"],
            "reasoning": mapping.reasoning
        }
    
    def _format_topic_list(self, topics: List[Dict]) -> str:
        """Format topic list for LLM prompt."""
        lines = []
        for t in topics[:150]:  # Limit to avoid token overflow
            lines.append(f"  {t['id']} | {t['name']}")
        return "\n".join(lines)
    
    def _discover_related_topics(
        self,
        primary_topic_ids: List[str],
        driver_topic_ids: List[str],
        valid_ids: set,
        graph_data: Dict
    ) -> Dict[str, List[str]]:
        """
        Discover related topics via ALL graph relationship types.

        Returns:
            {
                "correlated": [...],  # co-moving topics
                "hedges": [...],      # risk offset topics
                "peers": [...],       # substitute/competitor topics
                "influenced": [...],  # topics driven by primaries
                "influencers": [...]  # topics that drive primaries
            }
        """
        if not primary_topic_ids:
            return {"correlated": [], "hedges": [], "peers": [], "influenced": [], "influencers": []}

        relationships = graph_data.get("relationships", {})
        all_selected = set(primary_topic_ids + driver_topic_ids)

        def collect_related(rel_key: str, max_count: int = 5) -> List[str]:
            """Collect related topics from a relationship type."""
            rel_dict = relationships.get(rel_key, {})
            related = []
            for topic_id in primary_topic_ids:
                if topic_id in rel_dict:
                    related.extend(rel_dict[topic_id])
            # Deduplicate, validate, exclude already selected
            related = list(set(related))
            related = [tid for tid in related if tid in valid_ids and tid not in all_selected]
            return related[:max_count]

        return {
            "correlated": collect_related("correlates_with", 5),
            "hedges": collect_related("hedges", 3),
            "peers": collect_related("peers", 3),
            "influenced": collect_related("influences", 3),
            "influencers": collect_related("influenced_by", 3)
        }
