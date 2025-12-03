"""
Generate a single actionable question for the dashboard based on strategy analysis.
SUPER SIMPLE: One question, risk-focused, clickable to start chat.
"""

from src.llm.llm_openai import call_llm


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
    
    # Combine all analysis sections
    analysis_text = "\n\n".join([
        f"## {section.replace('_', ' ').title()}\n{content}"
        for section, content in analysis_dict.items()
        if content and len(str(content).strip()) > 0
    ])
    
    prompt = f"""You are a risk-focused financial analyst. Generate ONE actionable question for the user's dashboard.

ASSET: {asset_name}

USER'S STRATEGY:
{strategy_text}

LATEST ANALYSIS:
{analysis_text}

Generate ONE question that:
- Is specific to their strategy and the latest analysis
- Focuses on risks, catalysts, or key decisions
- Is actionable (what to watch, when to act, what changed)
- Is concise (max 150 characters)
- Starts with "What", "Which", "How", or "When"

Output ONLY the question, nothing else. No quotes, no explanation.
"""
    
    question = call_llm(
        system_prompt="You generate concise, actionable questions for financial dashboards.",
        user_prompt=prompt,
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=50
    )
    
    # Clean up
    question = question.strip().strip('"').strip("'")
    
    # Truncate if too long
    if len(question) > 150:
        question = question[:147] + "..."
    
    return question
