# graph_nodes/topic_taxonomy_classifier.py
"""
Topic taxonomy classifier for proposed Topic nodes.
- Adapts the style of graph_articles/category_identifier.py but for topics.
- Maps to one of: ["macro_driver","asset","policy","geography","company","industry_vertical","ambiguous"].
- Returns STRICT JSON object: {"category": str, "motivation": str}
"""
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from utils.app_logging import get_logger
from src.llm.system_prompts import SYSTEM_MISSION

logger = get_logger(__name__)

CATEGORIES = [
    "macro_driver",
    "asset",
    "policy",
    "geography",
    "company",
    "industry_vertical",
    "ambiguous",
]

prompt_template = """
{system_mission}

YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC TAXONOMY CLASSIFIER working on the Saga Graph—a trading-focused macro knowledge graph.

TASK:
- Classify the proposed topic into EXACTLY ONE of: {categories}
- Output ONLY a single JSON object with EXACTLY two fields:
    - 'category': one of {categories}
    - 'motivation': Short justification for the category (first field in the object)

STRICT RULES:
- "industry_vertical" = sectors/sub-sectors/operational niches (e.g., packaging, logistics, advertising, sterilized packaging).
- If the topic is not clearly a macro driver, asset, policy, geography, or company, choose "ambiguous".
- Be strict; quality over recall. If in doubt, do NOT place in macro/asset/policy/geography/company.
- Output STRICT JSON. NO arrays, NO extra fields, NO commentary.

TOPIC CANDIDATE:
- id: {topic_id}
- name: {topic_name}
- type: {topic_type}
- motivation: {motivation}

ARTICLE SUMMARY (optional context):
{summary}

EXAMPLE OUTPUT:
{{"motivation": "Rates policy anchor, impacts asset pricing.", "category": "macro_driver"}}

YOUR RESPONSE (STRICT JSON ONLY):
"""

prompt = PromptTemplate(
    input_variables=["system_mission", "categories", "topic_id", "topic_name", "topic_type", "motivation", "summary"],
    template=prompt_template,
)


def classify_topic_category(
    topic_id: str,
    topic_name: str,
    topic_type: str,
    motivation: str,
    article_summary: str = "",
):
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "categories": ", ".join(CATEGORIES),
        "topic_id": topic_id or "",
        "topic_name": topic_name or "",
        "topic_type": topic_type or "",
        "motivation": motivation or "",
        "summary": article_summary or "",
    })
    logger.info("Topic category result: %s", result)
    if isinstance(result, dict):
        # Normalize keys order to motivation first if needed by callers
        category = result.get("category")
        motivation = result.get("motivation")
        return category, motivation
    else:
        # Fail fast
        raise ValueError(f"Category classifier returned invalid structure: {result}")

# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    demo = classify_topic_category(
        topic_id="us_inflation",
        topic_name="US Inflation",
        topic_type="macro",
        motivation="Inflation drives monetary policy and market pricing.",
        article_summary="US CPI rises above expectations; markets reprice Fed path.",
    )
    print(demo)