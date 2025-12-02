"""
Source Checker Agent

Verifies factual accuracy and citation correctness.
"""

from pydantic import BaseModel, Field
from src.analysis_agents.base_agent import BaseAgent
from src.analysis_agents.source_checker.prompt import SOURCE_CHECKER_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from langchain_core.output_parsers import StrOutputParser


class SourceCheckFeedback(BaseModel):
    """Output model for Source Checker"""
    feedback: str = Field(
        description="Factual corrections needed"
    )


class SourceCheckerAgent(BaseAgent):
    """
    Source Checker Agent
    
    Verifies factual accuracy and citation correctness.
    """
    
    def __init__(self):
        super().__init__("SourceChecker")
    
    def run(
        self, 
        draft: str,
        material: str,
        section_focus: str,
        critic_feedback: str,
        asset_name: str,
        asset_id: str,
        **kwargs
    ) -> SourceCheckFeedback:
        """
        Check sources and facts.
        
        Args:
            draft: Analysis draft to check
            material: Source material
            section_focus: Section focus text
            critic_feedback: Feedback from critic
            asset_name: Asset name
            asset_id: Asset ID
        
        Returns:
            SourceCheckFeedback with factual corrections
        """
        self._log(f"Checking sources for {asset_name}")
        
        # Load market context
        from src.market_data.loader import get_market_context_for_prompt
        market_context = get_market_context_for_prompt(asset_id)
        
        # Call LLM
        prompt = SOURCE_CHECKER_PROMPT.format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            section_focus=section_focus,
            market_context=market_context,
            material=material[:2000],  # Limit material length
            draft=draft,
            critic_feedback=critic_feedback,
            asset_name=asset_name,
            asset_id=asset_id
        )
        
        llm = get_llm(ModelTier.COMPLEX)
        parser = StrOutputParser()
        chain = llm | parser
        
        response = chain.invoke(prompt)
        
        self._log(f"Source check complete: {len(response)} characters")
        return SourceCheckFeedback(feedback=response)


# Convenience function
def run_source_checker(
    draft: str,
    material: str,
    section_focus: str,
    critic_feedback: str,
    asset_name: str,
    asset_id: str
) -> SourceCheckFeedback:
    """Run source checker agent"""
    agent = SourceCheckerAgent()
    return agent.run(draft, material, section_focus, critic_feedback, asset_name, asset_id)


if __name__ == "__main__":
    # Test
    print("Source Checker agent - use via orchestrator or full pipeline")
