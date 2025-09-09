"""
Minimal EURUSD Article Import Utility

Purpose:
- Reset the Neo4j graph database
- Seed anchor nodes (incl. EURUSD) and anchor relationships
- Iterate raw article JSON files under data/raw_news/
- For each article, run a SIMPLE-tier (Ollama llama3.1) YES/NO relevance check for EURUSD swing trading
- If relevant, add the article to the graph using add_article(article_id)

Strict constraints:
- Fail-fast, minimal code; no fallback/silent handling
- Use paths.get_raw_news_dir() exclusively for raw data paths
- Use existing add_article() without modification
- Log concise progress and a final summary

Run:
    python -m dev_scripts.import_eurusd_articles

Note:
- Requires Neo4j running and env vars for connection (NEO4J_*) as used by graph_db.db_driver
- Requires Ollama running locally with model "llama3.1" per model_config SIMPLE tier
"""
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from pathlib import Path
from utils.app_logging import get_logger
from paths import get_raw_news_dir
from src.llm.llm_router import get_medium_llm
from src.articles.ingest_article import add_article
from src.articles.article_text_formatter import extract_text_from_json_article
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = get_logger(__name__)

def is_relevant_to_eurusd_swing(llm, formatted_text: str) -> bool:
    if not formatted_text or not formatted_text.strip():
        raise ValueError("Empty formatted_text passed to relevance check")

    # Extend this function to use get_all_nodes to get all nodes
    # create a list of all id
    # Then extend the promp to take in all nodes and have it say if the article is relevant to any of the nodes
    # return the node that it is more relevant to
    # if a low quality article, return None
    # So that we extend this to map out all not only the EURUSD node! 

    prompt_template = """
    {system_mission}
    {system_context}

    You are an expert FX macro analyst. Determine if the article below is directly relevant to EURUSD swing trading (multi-day to multi-week).
    Criteria: Macro/ECB/Fed policy, rate differentials, Eurozone/US growth/inflation, risk sentiment, flows affecting EURUSD.
    Respond ONLY with a single line of strict JSON: {{"relevant": "yes"}} or {{"relevant": "no"}}. No explanation, no extra text.

    Article:
    {article}
    """
    prompt = PromptTemplate.from_template(prompt_template)
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    try:
        result = chain.invoke({
            "article": formatted_text,
            "system_mission": SYSTEM_MISSION,
            "system_context": SYSTEM_CONTEXT,
        })
        logger.info("----- results relevance check: ------")
        logger.info(result)
        logger.info("----- end results relevance check ------")
    except Exception as e:
        logger.warning(f"LLM relevance check failed to produce valid JSON: {e}")
        return False
    if result is None:
        return False
    val = result.get("relevant", "").strip().lower()
    if val == "yes":
        return True
    if val == "no":
        return False
    return False

def iter_raw_article_files():
    base = get_raw_news_dir()
    if not base.exists():
        raise FileNotFoundError(f"Raw news base dir does not exist: {base}")
    for day_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
        for fp in sorted(day_dir.glob("*.json")):
            yield fp

def load_article_from_file(fp: Path):
    with fp.open("r") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], dict):
        return obj["data"]
    return obj

def main():
    llm = get_medium_llm()
    total = 0
    relevant = 0
    added = 0
    skipped = 0
    for fp in iter_raw_article_files():
        total += 1
        article_id = fp.stem
        try:
            article_obj = load_article_from_file(fp)
            formatted = extract_text_from_json_article(article_obj)
            if is_relevant_to_eurusd_swing(llm, formatted):
                relevant += 1
                result = add_article(article_id)
                if isinstance(result, dict) and result.get("status") == "added":
                    added += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        except Exception as e:
            logger.error(f"Error processing {article_id} at {fp}: {e}")
            raise
    logger.info(f"EURUSD Import complete | total={total}, relevant={relevant}, added={added}, skipped={skipped}")

if __name__ == "__main__":
    main()
