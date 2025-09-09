from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from llm.llm_router import get_medium_llm
from llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger

logger = get_logger(__name__)

def validate_article_topic_relevance(article: dict, topic_name: str, topic_id: str):
    """Deep LLM validation: does this article truly provide value to this topic?"""
    
    summary = article["argos_summary"]
    title = article.get("title", "")
    
    logger.info(f"Validating relevance: article '{title[:50]}...' to topic '{topic_name}' ({topic_id})")

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS FINANCIAL ANALYST validating if an article provides genuine value to a specific investment topic in the Saga Graph. This validation determines whether to create a knowledge graph connection.

        TASK:
        - Analyze if the article provides meaningful, actionable insights for the given topic
        - Consider: direct relevance, analytical depth, market impact, investment implications
        - Output ONLY a single valid JSON object with EXACTLY two fields:
            - 'should_link' (required): Boolean true/false for whether to create the graph connection
            - 'motivation' (required): Short reasoning (1-2 sentences) defending your decision

        ARTICLE TITLE: {title}
        ARTICLE SUMMARY: {summary}
        
        TARGET TOPIC: {topic_name} (ID: {topic_id})

        EXAMPLES:
        {{"should_link": true, "motivation": "Article provides specific inflation data and Fed policy implications directly relevant to US monetary policy analysis."}}
        {{"should_link": false, "motivation": "Article mentions topic briefly but lacks analytical depth or actionable investment insights."}}

        STRICT JSON FORMAT. NO EXTRA TEXT. ONLY THE JSON OBJECT WITH 2 FIELDS.
        YOUR RESPONSE:
    """
    
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_medium_llm()
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    
    result = chain.invoke({
        "title": title,
        "summary": summary, 
        "topic_name": topic_name,
        "topic_id": topic_id,
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })
    
    if isinstance(result, str):
        import json
        result = json.loads(result)
    
    should_link = result.get('should_link', False)
    motivation = result.get('motivation', '')
    
    logger.info(f"Validation result: link={should_link}, motivation={motivation[:200]}{'...' if len(motivation) > 200 else ''}")
    return should_link, motivation


# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    article = {
        "title": "Fed Raises Interest Rates by 0.75% to Combat Inflation",
        "argos_summary": "The Federal Reserve raised interest rates by 75 basis points to 3.25%, the largest increase since 1994, as inflation remains near 40-year highs."
    }
    
    should_link, motivation = validate_article_topic_relevance(
        article, "US Interest Rates", "us_interest_rates"
    )
    print(f"Should Link: {should_link}")
    print(f"Motivation: {motivation}")
