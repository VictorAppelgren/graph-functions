from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from llm.llm_router import get_medium_llm
from llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger

logger = get_logger(__name__)

def find_impact(article_text: dict):
    
    logger.info(f"Article text: {article_text[:200]}{'...' if len(article_text) > 200 else ''}")
    
    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS IMPACT ASSESSOR working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - For the article and node below, output a SINGLE JSON OBJECT with exactly these two fields:
            - 'motivation': Reason for the score (1-2 sentences, first field)
            - 'score': Impact score ('hidden' if not relevant, or 1=low, 2=medium, 3=high)
        - Output ONLY the JSON object, no extra text, no array. If unsure, motivation should say so, and for the score parameter, do your best to assign a score.

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "The article directly impacts this node by reporting a major event.", "score": 3}}
        {{"motivation": "The article is not relevant to this node's scope.", "score": "hidden"}}

        IF IMPACT IS DIFFICULT TO ASSESS, SAY THAT IN MOTIVATION, BUT STILL DO YOUR BEST TO OUTPUT A SCORE. CHOOSE A SCORE! BUT IF DIFFICULT PICK A LOW ONE.

        YOUR RESPONSE:
    """
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_medium_llm()
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke({
        "article_text": article_text,
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })

    #logger.info("----- results impact identifier: ------")
    #logger.info(result)
    #logger.info("----- end results impact identifier ------")

    # Strict fail-fast validation
    if not isinstance(result, dict):
        logger.error(f"Impact identifier: LLM did not return a JSON object. Got: {result}")
        raise ValueError("Impact identifier: LLM did not return a JSON object.")
    if "motivation" not in result or "score" not in result:
        logger.error(f"Impact identifier: Missing required fields in LLM response: {result}")
        raise ValueError("Impact identifier: Missing required fields in LLM response.")
    motivation = result["motivation"]
    score = result["score"]
    return motivation, score
        
# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    # Fake data for quick test
    article = {"data": {"article_text": "US inflation surged to a 40-year high in June, affecting bond yields."}}
    motivation, score = find_impact(article)
    print("Motivation:", motivation)
    print("Score:", score)