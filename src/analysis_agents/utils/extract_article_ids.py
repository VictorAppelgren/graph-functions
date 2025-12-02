"""
Extract Article IDs and Topic References from Text

Utility to extract citations from generated text:
- Article IDs: (ABC123XYZ)
- Topic references: (Topic:fed_policy.executive_summary)

Ensures we track which sources were actually used in agent outputs.
"""

import re
from typing import List, Set, Dict


def extract_article_ids(text: str) -> List[str]:
    """
    Extract all 9-character alphanumeric article IDs from text.
    
    Looks for the citation format: (ABC123XYZ)
    
    Args:
        text: Text containing article citations
        
    Returns:
        List of unique article IDs found (deduplicated, preserving order)
    
    Examples:
        >>> extract_article_ids("Article (ABC123XYZ) shows...")
        ['ABC123XYZ']
        
        >>> extract_article_ids("Multiple (ABC123XYZ)(DEF456GHI) sources")
        ['ABC123XYZ', 'DEF456GHI']
    """
    if not text:
        return []
    
    # Pattern: (9 alphanumeric characters)
    # Must be exactly 9 characters, alphanumeric only
    pattern = r'\(([A-Z0-9]{9})\)'
    
    matches = re.findall(pattern, text)
    
    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_ids = []
    for article_id in matches:
        if article_id not in seen:
            seen.add(article_id)
            unique_ids.append(article_id)
    
    return unique_ids


def extract_article_ids_from_list(texts: List[str]) -> List[str]:
    """
    Extract article IDs from a list of text strings.
    
    Args:
        texts: List of text strings
        
    Returns:
        List of unique article IDs found across all texts
    """
    all_ids: Set[str] = set()
    
    for text in texts:
        ids = extract_article_ids(text)
        all_ids.update(ids)
    
    return sorted(list(all_ids))


def validate_article_id(article_id: str) -> bool:
    """
    Validate that a string is a valid 9-character article ID.
    
    Args:
        article_id: String to validate
        
    Returns:
        True if valid article ID format
    """
    if not article_id or len(article_id) != 9:
        return False
    
    return article_id.isalnum() and article_id.isupper()


def extract_topic_references(text: str) -> List[Dict[str, str]]:
    """
    Extract topic references from text.
    
    Looks for the citation format: (Topic:topic_id.field_name)
    
    Args:
        text: Text containing topic citations
        
    Returns:
        List of dicts with 'topic_id' and 'field' keys (deduplicated)
    
    Examples:
        >>> extract_topic_references("(Topic:fed_policy.executive_summary) shows...")
        [{'topic_id': 'fed_policy', 'field': 'executive_summary'}]
        
        >>> extract_topic_references("(Topic:dxy.drivers) and (Topic:ecb_policy.analysis)")
        [{'topic_id': 'dxy', 'field': 'drivers'}, {'topic_id': 'ecb_policy', 'field': 'analysis'}]
    """
    if not text:
        return []
    
    # Pattern: (Topic:topic_id.field_name)
    # topic_id: lowercase letters, numbers, underscores
    # field_name: lowercase letters, underscores
    pattern = r'\(Topic:([a-z0-9_]+)\.([a-z_]+)\)'
    
    matches = re.findall(pattern, text)
    
    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_refs = []
    
    for topic_id, field in matches:
        key = f"{topic_id}.{field}"
        if key not in seen:
            seen.add(key)
            unique_refs.append({
                'topic_id': topic_id,
                'field': field
            })
    
    return unique_refs


def extract_topic_references_from_list(texts: List[str]) -> List[Dict[str, str]]:
    """
    Extract topic references from a list of text strings.
    
    Args:
        texts: List of text strings
        
    Returns:
        List of unique topic references found across all texts
    """
    all_refs: Dict[str, Dict[str, str]] = {}
    
    for text in texts:
        refs = extract_topic_references(text)
        for ref in refs:
            key = f"{ref['topic_id']}.{ref['field']}"
            all_refs[key] = ref
    
    return list(all_refs.values())
