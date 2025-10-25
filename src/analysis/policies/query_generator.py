"""
LLM-driven wide query generation for a new topic.
"""
from __future__ import annotations
import logging
import json
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from typing import Any, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.runnables import Runnable
from src.llm.sanitizer import run_llm_decision, WideQueryModel

logger = app_logging.get_logger("analysis.query_generator")


class WideQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # motivation optional but nice to have
    motivation: str | None = Field(default=None, max_length=400)
    # query is required for a “success”; when the model can’t produce one, set to None
    query: str | None


def _coerce_json_object(raw: Any) -> dict[str, Any]:
    """Accept dict or JSON string and return a dict, else raise."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")


def _sanitize_wide_query(raw: Any, logger: logging.Logger) -> WideQuery:
    data = _coerce_json_object(raw)

    # allow models that output only {"query": "..."} (motivation omitted)
    try:
        wq = WideQuery.model_validate(data)
    except ValidationError as e:
        logger.warning("WideQuery schema validation failed: %s", str(e)[:200])
        # graceful fallback: no query
        return WideQuery(motivation=None, query=None)

    # normalize motivation
    if wq.motivation:
        wq.motivation = " ".join(wq.motivation.split())[:400]

    # normalize query (strip empties to None)
    if wq.query is not None:
        q = wq.query.strip()
        wq.query = q if q else None

    return wq


def create_wide_query(article_text: str) -> dict[str, Any]:
    """
    Uses LLM to generate a wide boolean search query for a given article/topic.
    Returns: {"motivation": str|None, "query": str|None}
    """
    logger.info("Generating wide query from article text for topic")

    llm = get_llm(ModelTier.MEDIUM)

    prompt = f"""You are a boolean search query expert for financial markets and macro topics.

TASK: Create a wide boolean search query for this topic.

TOPIC:
{article_text}

INSTRUCTIONS:
1. Generate a boolean query using OR, AND, NOT operators
2. Include synonyms, abbreviations, and related terms
3. Make it WIDE to catch all relevant articles
4. Keep it focused on the core topic

EXAMPLES (covering different asset classes):

Topic: "US Dollar"
Query: ("USD" OR "US Dollar" OR "US$" OR "dollar" OR "DXY" OR "dollar index") AND ("Fed" OR "Federal Reserve" OR "monetary policy" OR "interest rates" OR "forex" OR "FX" OR "currency")

Topic: "Fed Policy"
Query: ("Fed" OR "Federal Reserve" OR "FOMC" OR "Powell" OR "Fed policy" OR "Federal Open Market Committee") AND ("interest rates" OR "monetary policy" OR "rate hike" OR "rate cut" OR "QE" OR "quantitative easing" OR "tightening" OR "dot plot" OR "Fed funds")

Topic: "S&P 500"
Query: ("S&P 500" OR "SPX" OR "SP500" OR "S&P" OR "Standard & Poor's 500") AND ("stocks" OR "equities" OR "market" OR "rally" OR "selloff" OR "earnings" OR "valuation" OR "index")

Topic: "US 10Y Treasury Yield"
Query: ("10-year" OR "10Y" OR "10 year" OR "Treasury yield" OR "UST10Y" OR "benchmark yield") AND ("bonds" OR "fixed income" OR "rates" OR "yield curve" OR "duration" OR "debt")

Topic: "Brent Crude Oil"
Query: ("Brent" OR "Brent crude" OR "oil" OR "crude oil" OR "petroleum") AND ("energy" OR "OPEC" OR "supply" OR "demand" OR "refining" OR "barrel" OR "WTI" OR "commodities")

Topic: "Gold"
Query: ("gold" OR "XAU" OR "bullion" OR "gold price") AND ("precious metals" OR "safe haven" OR "inflation hedge" OR "commodities" OR "central banks" OR "jewelry demand")

Topic: "US Inflation"
Query: ("inflation" OR "CPI" OR "consumer prices" OR "price growth" OR "PCE") AND ("United States" OR "US" OR "USA" OR "America" OR "Fed" OR "Federal Reserve") AND NOT ("Europe" OR "China" OR "Japan")

Topic: "ECB Policy"
Query: ("ECB" OR "European Central Bank" OR "Lagarde" OR "Eurozone central bank") AND ("monetary policy" OR "interest rates" OR "rate decision" OR "PEPP" OR "APP" OR "TLTRO" OR "deposit rate")

Topic: "China Exports"
Query: ("China" OR "Chinese" OR "PRC") AND ("exports" OR "trade" OR "shipments" OR "overseas sales" OR "trade balance" OR "customs data") AND ("goods" OR "manufacturing" OR "supply chain")

Topic: "US Unemployment Rate"
Query: ("unemployment" OR "jobless rate" OR "unemployment rate" OR "U3" OR "labor market") AND ("United States" OR "US" OR "USA" OR "BLS" OR "Bureau of Labor Statistics") AND ("jobs" OR "employment" OR "payrolls")

YOUR TURN:
Respond with ONLY this JSON format (no markdown, no extra text):
{{
  "motivation": "Brief explanation of query strategy",
  "query": "your boolean query here"
}}"""

    r = run_llm_decision(chain=llm, prompt=prompt, model=WideQueryModel, logger=logger)

    # If you prefer to return the model, change return type to WideQuery
    return r.model_dump()
