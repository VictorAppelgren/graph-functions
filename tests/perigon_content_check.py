"""Perigon content depth smoke test.

Run this to quickly verify whether the Perigon API key returns full-length
article bodies or only truncated excerpts.

Usage:
    python tests/perigon_content_check.py
    python -m tests.perigon_content_check
"""

import argparse
import os
import sys
from textwrap import indent, shorten
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.clients.perigon.news_api_client import NewsApiClient  # noqa: E402

TRUNCATION_MARKERS: Tuple[str, ...] = (
    "… [+]",
    "... [+]",
    "[+]",
    "Continue reading",
    "continue reading",
    "subscription",
)
MIN_FULL_CONTENT_CHARS = 1_200
DEFAULT_QUERIES = [
    "Federal Reserve rate hike",
    "Artificial intelligence regulation",
]


def analyze_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect an article payload and flag whether the body looks truncated."""

    content = (article.get("content") or "").strip()
    length = len(content)
    markers = [m for m in TRUNCATION_MARKERS if m.lower() in content.lower()]
    paywall_flag = bool(article.get("source", {}).get("paywall"))

    reasons: List[str] = []
    if not content:
        reasons.append("empty content field")
    if length and length < MIN_FULL_CONTENT_CHARS:
        reasons.append(f"short body ({length} chars < {MIN_FULL_CONTENT_CHARS})")
    if markers:
        # Deduplicate markers while preserving order
        seen = []
        for marker in markers:
            if marker not in seen:
                seen.append(marker)
        reasons.append(f"marker(s): {', '.join(seen)}")
    if paywall_flag:
        reasons.append("source marked paywall=true")

    truncated = bool(reasons)
    return {
        "title": article.get("title", "Untitled"),
        "url": article.get("url"),
        "source": article.get("source", {}).get("name")
        or article.get("source", {}).get("domain"),
        "length": length,
        "truncated": truncated,
        "reasons": reasons,
        "snippet": shorten(content, 180) if content else "",
        "keys": sorted(article.keys()),
    }


def run_check(queries: List[str], max_results: int) -> bool:
    client = NewsApiClient()
    full_articles = 0
    total_articles = 0
    truncated_articles = 0
    full_by_source: Dict[str, int] = {}
    truncated_by_source: Dict[str, int] = {}

    QUERY_SEP = "\n" + "=" * 70
    ARTICLE_SEP = "-" * 70
    FINAL_SEP = "=" * 70

    for query in queries:
        print(f"{QUERY_SEP}")
        print(f"🔍 Query: {query!r} (max_results={max_results})")
        response = client.search_articles(query, max_results=max_results)
        articles = response.get("articles", [])

        if not articles:
            print("⚠️ No articles returned for this query.")
            continue

        for idx, article in enumerate(articles, start=1):
            total_articles += 1
            analysis = analyze_article(article)
            status = "FULL ✅" if not analysis["truncated"] else "TRUNCATED ⚠️"
            if not analysis["truncated"]:
                full_articles += 1
                source_key = analysis["source"] or "Unknown"
                full_by_source[source_key] = full_by_source.get(source_key, 0) + 1
            else:
                truncated_articles += 1
                source_key = analysis["source"] or "Unknown"
                truncated_by_source[source_key] = (
                    truncated_by_source.get(source_key, 0) + 1
                )

            print(f"\n{ARTICLE_SEP}")
            print(f"[{idx}] {analysis['title']}")
            print(f"    Source: {analysis['source'] or 'Unknown'}")
            print(f"    Length: {analysis['length']} chars | Status: {status}")
            print(f"    Keys: {', '.join(analysis['keys'])}")
            if analysis["reasons"]:
                print(f"    Reasons: {', '.join(analysis['reasons'])}")
            if analysis["url"]:
                print(f"    URL: {analysis['url']}")
            if analysis["snippet"]:
                print(f"    Snippet: {analysis['snippet']}")

            content = (article.get("content") or "").strip()
            if content:
                print("\n    Content:\n")
                print(indent(content, "        "))

            summary = (article.get("summary") or "").strip()
            if summary:
                print("\n    Summary:\n")
                print(indent(summary, "        "))

    print("\n====================================================================")
    print(f"Processed {total_articles} articles across {len(queries)} query set(s).")
    print(f"Full-length articles detected: {full_articles}")
    print(f"Truncated articles detected: {truncated_articles}")

    def _summarize(label: str, counter: Dict[str, int]) -> None:
        if not counter:
            print(f"{label}: none")
            return
        sorted_items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        summary_str = ", ".join(f"{count} from {source}" for source, count in sorted_items)
        print(f"{label}: {summary_str}")

    print(f"\n{FINAL_SEP}")
    print("SUMMARY")
    print(f"{FINAL_SEP}")
    _summarize("Full articles", full_by_source)
    _summarize("Truncated articles", truncated_by_source)
    print(FINAL_SEP)

    if full_articles == 0:
        print(
            "❌ All sampled articles appear truncated. Check Perigon plan/API key or"
            " try different queries."
        )
        return False

    print("✅ At least one article looked full-length. Perigon access appears good.")
    print(FINAL_SEP)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Perigon content depth check")
    parser.add_argument(
        "-q",
        "--query",
        action="append",
        help="Add a query to test (can be supplied multiple times).",
    )
    parser.add_argument(
        "-n",
        "--max-results",
        type=int,
        default=5,
        help="Maximum articles to fetch per query (default: 5)",
    )
    args = parser.parse_args()

    queries = args.query if args.query else DEFAULT_QUERIES
    success = run_check(queries, max_results=args.max_results)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
