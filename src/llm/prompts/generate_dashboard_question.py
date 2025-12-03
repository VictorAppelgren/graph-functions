"""
Generate a single actionable question for the dashboard based on strategy analysis.
SUPER SIMPLE: One question, risk-focused, clickable to start chat.
"""

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier


def generate_dashboard_question(strategy_text: str, analysis_dict: dict, asset_name: str) -> str:
    """
    Generate ONE actionable question based on strategy + analysis.
    
    Args:
        strategy_text: User's strategy/position/thesis
        analysis_dict: All analysis sections (dict of section_name -> content)
        asset_name: Asset/topic name (e.g., "EURUSD")
    
    Returns:
        str: Single question (max 150 chars)
    """
    
    # Extract key summary from analysis
    risk_summary = ""
    opp_summary = ""
    
    if "risk_assessment" in analysis_dict and isinstance(analysis_dict["risk_assessment"], dict):
        risk_summary = analysis_dict["risk_assessment"].get("key_risk_summary", "")
    
    if "opportunity_assessment" in analysis_dict and isinstance(analysis_dict["opportunity_assessment"], dict):
        opp_summary = analysis_dict["opportunity_assessment"].get("key_summary", "")
    
    if "final_analysis" in analysis_dict and isinstance(analysis_dict["final_analysis"], dict):
        exec_summary = analysis_dict["final_analysis"].get("executive_summary", "")
    else:
        exec_summary = ""
    
    prompt = f"""You are a risk-focused financial analyst. Generate ONE actionable question for the user's dashboard.

ASSET: {asset_name}

USER'S STRATEGY:
{strategy_text}

KEY RISKS:
{risk_summary}

KEY OPPORTUNITIES:
{opp_summary}

EXECUTIVE SUMMARY:
{exec_summary}

Generate ONE question that:
- Is specific to their strategy and the latest analysis
- Focuses on risks, catalysts, or key decisions
- Is actionable (what to watch, when to act, what changed)
- Is concise (max 150 characters)
- Starts with "What", "Which", "How", or "When"

Output ONLY the question, nothing else. No quotes, no explanation.
"""
    
    llm = get_llm(tier=ModelTier.MEDIUM)
    response = llm.invoke(prompt)
    question = response.content.strip()
    
    # Clean up
    question = question.strip('"').strip("'")
    
    # Truncate if too long
    if len(question) > 150:
        question = question[:147] + "..."
    
    return question
