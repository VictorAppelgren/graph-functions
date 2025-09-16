"""
LLM-driven categorization of articles in the context of a node.
"""
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from typing import cast, Any, Literal
import json

logger = get_logger(__name__)

CategoryName = Literal[
    "macro_event",
    "earnings",
    "regulation",
    "policy_statement",
    "central_bank_action",
    "economic_data",
    "geopolitical",
    "company_update",
    "market_commentary",
    "other",
]

class CategoryItem(BaseModel):
    """Expected shape of one category output from the LLM."""
    model_config = ConfigDict(extra="forbid")
    motivation: str = Field(min_length=1, max_length=400)
    name: CategoryName


def _coerce_to_obj_or_list(raw: Any) -> list[dict[str, Any]]:
    """Accept dict | list[dict] | JSON string and coerce to list[dict]."""
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        # ensure list of dicts
        if not all(isinstance(x, dict) for x in raw):
            raise TypeError("Expected list of objects from LLM")
        return cast(list[dict[str, Any]], raw)
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list) and all(isinstance(x, dict) for x in parsed):
            return cast(list[dict[str, Any]], parsed)
        raise TypeError("Parsed JSON was not an object or array of objects")
    raise TypeError(f"Unsupported LLM output type: {type(raw).__name__}")

def _sanitize_categories(raw: Any) -> list[CategoryItem]:
    """Parse, validate, and normalize the LLM categories output."""
    objs = _coerce_to_obj_or_list(raw)
    items: list[CategoryItem] = []
    for obj in objs:
        try:
            item = CategoryItem.model_validate(obj)
        except ValidationError:
            # Skip invalid entries rather than blowing up; or re-raise if you prefer strictness
            continue
        # normalize motivation (trim & collapse whitespace)
        item.motivation = " ".join(item.motivation.split())[:400]
        items.append(item)
    return items

def find_category(article_text: str) -> tuple[str | None, CategoryName | None]:
    """
    Ask the LLM to assign categories to an article and return the first (motivation, name).

    Returns:
        (motivation, name) where both may be None if parsing/validation failed.
    """
    categories: list[CategoryName] = [
        "macro_event",
        "earnings",
        "regulation",
        "policy_statement",
        "central_bank_action",
        "economic_data",
        "geopolitical",
        "company_update",
        "market_commentary",
        "other",
    ]

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS CATEGORY IDENTIFIER working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - For the article below, output a JSON array of category objects. Each object MUST have:
            - 'motivation' (first field): Short justification for the category assignment
            - 'name': Category name (one of: {categories})
        - Output ONLY the JSON array, no extra text. If unsure, use name="other" and explain why in motivation.

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        [{{"motivation": "The article discusses a major inflation print.", "name": "macro_event"}}]
    """

    prompt = PromptTemplate(
        input_variables=["article_text", "categories", "system_mission", "system_context"],
        template=prompt_template,
    )

    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    raw = chain.invoke({
        "article_text": article_text,
        "categories": ", ".join(categories),
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })

    items = _sanitize_categories(raw)
    if not items:
        return (None, None)

    first = items[0]
    return (first.motivation, first.name)