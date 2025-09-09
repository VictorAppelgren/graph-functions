"""
LLM-driven categorization of articles in the context of a node.
"""
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from llm.llm_router import get_medium_llm
from llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger

logger = get_logger(__name__)

def find_category(article_text: dict):
    
    # logger.info(f"article_text: {article_text}")

    categories = [
        "macro_event: Major macroeconomic event (e.g., inflation print, GDP, jobs report)",
        "earnings: Company earnings or financial results",
        "regulation: Regulatory change or legal development",
        "policy_statement: Official statement from a policymaker or institution",
        "central_bank_action: Central bank decision or intervention",
        "economic_data: Any economic data release not covered above",
        "geopolitical: Geopolitical event or risk",
        "company_update: Company news not related to earnings (e.g., M&A, product launch)",
        "market_commentary: Market analysis, opinion, or commentary",
        "other: Only if truly none of the above fit, and never as a catch-all"
    ]
    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS CATEGORY IDENTIFIER working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - For the article and node below, output a JSON array of category objects. Each object MUST have:
            - 'motivation': Short justification for the category assignment (first field)
            - 'name': Category name (one of: {categories})
        - Output ONLY the JSON array, no extra text. If unsure, output a motivation saying so and and for the name parameter, output "other".

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "The article discusses a major inflation print, which is a macroeconomic event relevant to this node.", "name": "macro_event"}},
        {{"motivation": "The article discusses nothing relevant to this node.", "name": "other"}}]

        IF NO CATEGORY APPLIES, SAY THAT IN MOTIVATION, AND OUTPUT "other" FOR THE NAME PARAMETER.

        YOUR RESPONSE:
    """
    prompt = PromptTemplate(
        input_variables=["article_text", "categories", "system_mission", "system_context"],
        template=prompt_template,
    )

    llm = get_medium_llm()
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke({
        "article_text": article_text,
        "categories": ", ".join(categories),
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })

    #logger.info("----- results category identifier: ------")
    #logger.info(result)
    #logger.info("----- end results category identifier ------")

    if isinstance(result, list):
        motivation = result[0].get("motivation")
        name = result[0].get("name")
        return motivation, name
    elif isinstance(result, dict):
        motivation = result.get("motivation")
        name = result.get("name")
        return motivation, name
    else:
        return None, None

# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    # Fake data for quick test
    article = {"data": {"article_text": "US inflation surged to a 40-year high in June, affecting bond yields."}}
    node_name = "us_inflation"
    motivation, name = find_category(article, node_name)
    print("Motivation:", motivation)
    print("Name:", name)