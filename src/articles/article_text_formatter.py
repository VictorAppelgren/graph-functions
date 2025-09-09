"""
Extracts and formats all relevant text from a raw_news JSON article for LLM input or downstream processing.
"""
from typing import Dict, Any

import logging

def extract_text_from_json_article(article: Dict[str, Any]) -> str:
    """
    Given a loaded article JSON object, extract and format:
      - Title
      - Main content
      - All scraped data (e.g., description, keywords, taxonomies, categories, sentiment)
      - Argos summary (if present)
    Returns a single, well-formatted string with clear labels for each section.
    """
    logger = logging.getLogger(__name__)
    # Simple char-budget cap: ~4 chars ≈ 1 token; 40k tokens => ~160k chars
    MAX_TOKENS = 40_000
    CHARS_PER_TOKEN = 4
    BUDGET = MAX_TOKENS * CHARS_PER_TOKEN

    lines = []
    found = []
    used = 0

    def fits_and_add(segment: str) -> bool:
        nonlocal used
        # account for newline between lines when joining
        need = len(segment) if not lines else 1 + len(segment)
        if used + need > BUDGET:
            return False
        lines.append(segment)
        used += need
        return True
    # Title
    title = article.get("title")
    if title:
        if fits_and_add(f"Title: {title}"):
            found.append('title')
        else:
            return "\n".join(lines)
    # Content
    content = article.get("content")
    if content:
        if fits_and_add(f"Content: {content}"):
            found.append('content')
        else:
            return "\n".join(lines)
    # Description
    description = article.get("description")
    if description:
        if fits_and_add(f"Description: {description}"):
            found.append('description')
        else:
            return "\n".join(lines)
    # Argos summary
    argos_summary = article.get("argos_summary")
    if argos_summary:
        if fits_and_add(f"Argos Summary: {argos_summary}"):
            found.append('argos_summary')
        else:
            return "\n".join(lines)
    # Categories
    categories = article.get("categories")
    if categories and isinstance(categories, list):
        cat_names = ", ".join([c.get("name", "") for c in categories if isinstance(c, dict)])
        if cat_names:
            if fits_and_add(f"Categories: {cat_names}"):
                found.append(f'categories({len(categories)})')
            else:
                return "\n".join(lines)
    # Taxonomies
    taxonomies = article.get("taxonomies")
    if taxonomies and isinstance(taxonomies, list):
        taxo_names = ", ".join([t.get("name", "") for t in taxonomies if isinstance(t, dict)])
        if taxo_names:
            if fits_and_add(f"Taxonomies: {taxo_names}"):
                found.append(f'taxonomies({len(taxonomies)})')
            else:
                return "\n".join(lines)
    # Keywords
    keywords = article.get("keywords")
    if keywords and isinstance(keywords, list):
        kw_names = ", ".join([k.get("name", "") for k in keywords if isinstance(k, dict)])
        if kw_names:
            if fits_and_add(f"Keywords: {kw_names}"):
                found.append(f'keywords({len(keywords)})')
            else:
                return "\n".join(lines)
    # Sentiment
    sentiment = article.get("sentiment")
    if sentiment and isinstance(sentiment, dict):
        sent_parts = []
        for k, v in sentiment.items():
            sent_parts.append(f"{k.capitalize()}: {v}")
        segment = "Sentiment: " + ", ".join(sent_parts)
        if fits_and_add(segment):
            found.append('sentiment')
        else:
            return "\n".join(lines)
    # Scraped sources
    scraped_sources = article.get("scraped_sources")
    if scraped_sources and isinstance(scraped_sources, list):
        included = 0
        for i, s in enumerate(scraped_sources, 1):
            url = s.get("url")
            text = s.get("text")
            if url or text:
                segment = f"Scraped Source {i}: {url if url else ''} {text if text else ''}".strip()
                if fits_and_add(segment):
                    included += 1
                else:
                    return "\n".join(lines)
        found.append(f'scraped_sources({included})')
    # Add any other fields as necessary
    logger.info(f"extract_text_from_json_article grabbed: {', '.join(found) if found else 'nothing'}")
    return "\n".join(lines)
