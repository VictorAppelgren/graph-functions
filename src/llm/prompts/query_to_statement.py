"""
Query to Statement Converter

Converts user questions into search statements for vector search.
Questions like "What is happening with Fed rates?" become statements
like "Federal Reserve interest rate policy changes and market impact"
for better semantic matching.
"""

from pydantic import BaseModel
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from utils.app_logging import get_logger

logger = get_logger(__name__)


class SearchStatement(BaseModel):
    statement: str = ""


QUERY_TO_STATEMENT_PROMPT = """Convert this user question/query into a search statement.

The statement should:
- Be a declarative statement, NOT a question
- Focus on the key topics and entities
- Be optimized for semantic similarity matching against news articles
- Be concise (1-2 sentences max)

Examples:
- "What's happening with Bitcoin?" -> "Bitcoin price movements and cryptocurrency market developments"
- "How is the Fed affecting markets?" -> "Federal Reserve monetary policy impact on financial markets"
- "Any news on EURUSD?" -> "Euro dollar currency pair exchange rate movements and forex analysis"

User query: {query}

Respond with JSON only:
{{"statement": "your search statement here"}}
"""


def convert_query_to_statement(query: str) -> str:
    """
    Convert a user question to a search statement for better vector search results.

    Args:
        query: User's question or search query

    Returns:
        Optimized search statement for vector search
    """
    # If it's already a statement (no question mark, reasonable length), return as-is
    if "?" not in query and len(query) < 100:
        logger.debug(f"Query looks like statement already, using as-is: {query[:50]}...")
        return query

    llm = get_llm(ModelTier.SIMPLE)
    prompt = QUERY_TO_STATEMENT_PROMPT.format(query=query)

    try:
        result = run_llm_decision(llm, prompt, SearchStatement, retry_once=True, logger=logger)
        statement = result.statement.strip()

        if statement:
            logger.info(f"Converted query to statement: '{query[:40]}...' -> '{statement[:60]}...'")
            return statement
        else:
            logger.warning("Empty statement from LLM, using original query")
            return query

    except Exception as e:
        logger.warning(f"Query conversion failed ({e}), using original query")
        return query


if __name__ == "__main__":
    # Test the converter
    test_queries = [
        "What is happening with Federal Reserve interest rates?",
        "How is AI disrupting finance?",
        "Any news on inflation in Europe?",
        "EURUSD movements",  # Already a statement
        "What are the implications of rising oil prices on emerging markets?",
    ]

    print("=" * 60)
    print("Query to Statement Converter Test")
    print("=" * 60)

    for query in test_queries:
        print(f"\nQuery: {query}")
        statement = convert_query_to_statement(query)
        print(f"Statement: {statement}")
