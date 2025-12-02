"""
Critic Agent

Provides high-signal feedback to upgrade analysis to world-class quality.
"""

from pydantic import BaseModel, Field
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.critic.prompt import CRITIC_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from langchain_core.output_parsers import StrOutputParser


class CriticFeedback(BaseModel):
    """Output model for Critic"""
    feedback: str = Field(
        description="Actionable feedback to improve analysis"
    )


class CriticAgent(BaseAgent):
    """
    Critic Agent
    
    Reviews analysis draft and provides actionable feedback.
    """
    
    def __init__(self):
        super().__init__("Critic")
    
    def run(
        self, 
        draft: str,
        material: str,
        section_focus: str,
        asset_name: str,
        asset_id: str,
        **kwargs
    ) -> CriticFeedback:
        """
        Review analysis and provide feedback.
        
        Args:
            draft: Analysis draft to review
            material: Source material used
            section_focus: Section focus text
            asset_name: Asset name
            asset_id: Asset ID
        
        Returns:
            CriticFeedback with actionable improvements
        """
        self._log(f"Reviewing analysis for {asset_name}")
        
        # Load market context
        from src.market_data.loader import get_market_context_for_prompt
        market_context = get_market_context_for_prompt(asset_id)
        
        # Call LLM
        prompt = CRITIC_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            market_context=market_context,
            material=material[:2000],  # Limit material length
            draft=draft,
            asset_name=asset_name,
            asset_id=asset_id
        )
        
        llm = get_llm(ModelTier.COMPLEX)
        parser = StrOutputParser()
        chain = llm | parser
        
        response = chain.invoke(prompt)
        
        self._log(f"Feedback generated: {len(response)} characters")
        return CriticFeedback(feedback=response)


# Convenience function
def run_critic(
    draft: str,
    material: str,
    section_focus: str,
    asset_name: str,
    asset_id: str
) -> CriticFeedback:
    """Run critic agent"""
    agent = CriticAgent()
    return agent.run(draft, material, section_focus, asset_name, asset_id)


if __name__ == "__main__":
    # Test
    print("Critic agent - use via orchestrator or full pipeline")
