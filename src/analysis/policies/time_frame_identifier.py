from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger

logger = get_logger(__name__)

def find_time_frame(article_text: dict): # TODO
    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS TIME FRAME IDENTIFIER working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - For the article and node below, output a JSON object with two fields:
            - 'motivation': Justification for the time frame assignment (1-2 sentences, first field)
            - 'horizon': MUST be EXACTLY one of: fundamental | medium | current
        - Output ONLY the JSON object, no extra text. If unsure, say so in 'motivation' but you MUST still choose one of: fundamental | medium | current. NEVER invent other labels.

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "The article discusses long-term structural drivers relevant to this node.", "horizon": "fundamental"}},
        {{"motivation": "The article is focused on immediate events affecting this node.", "horizon": "current"}}

        IF TIME FRAME IS DIFFICULT TO ASSESS, SAY THAT IN MOTIVATION, BUT STILL OUTPUT ONE OF: fundamental | medium | current. DEFAULT TOWARDS 'fundamental' IF UNSURE.

        YOUR RESPONSE:
    """
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke({
        "article_text": article_text,
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })

    #logger.info("----- results time frame identifier: ------")
    #logger.info(result)
    #logger.info("----- end results time frame identifier ------")

    if isinstance(result, dict):
        motivation = result.get("motivation")
        horizon = result.get("horizon")
        # Minimal, fail-fast validation
        allowed = {"fundamental", "medium", "current"}
        if isinstance(horizon, str):
            horizon_norm = horizon.strip().lower()
        else:
            horizon_norm = None
        if horizon_norm not in allowed:
            raise ValueError(f"Invalid horizon '{horizon}'. Must be one of: fundamental | medium | current")
        return motivation, horizon_norm
    else:
        raise ValueError("Time frame identifier returned non-dict result")

# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    # Fake data for quick test
    article = {"data": {"article_text": "US inflation surged to a 40-year high in June, affecting bond yields."}}
    motivation, horizon = find_time_frame(article)
    print("Motivation:", motivation)
    print("Horizon:", horizon)