"""
Relationship Re-evaluation Maintenance Job

Re-evaluates existing topic-to-topic relationships to potentially reclassify
them using the expanded 5-type system (INFLUENCES, CORRELATES_WITH, PEERS,
COMPONENT_OF, HEDGES).

Logic:
1. Fetch all existing topic relationships
2. For each relationship, ask LLM: "Given these two topics, what is the
   CORRECT relationship type?"
3. If LLM suggests a different type → update the relationship
4. Track stats on changes made

This is a one-time migration script but can be re-run safely (idempotent).

Usage:
    from src.maintenance.relationship_reeval import run_relationship_reeval
    stats = run_relationship_reeval()  # Re-evaluate all relationships
    stats = run_relationship_reeval(limit=50)  # Test with 50 relationships
"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from src.graph.neo4j_client import run_cypher
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from src.observability.stats_client import track
from utils.app_logging import get_logger

logger = get_logger(__name__)


class RelationshipReclassification(BaseModel):
    """LLM response for relationship re-evaluation."""
    correct_type: str = Field(default="", description="The correct relationship type")
    confidence: str = Field(default="low", description="high, medium, or low")
    reasoning: str = Field(default="", description="Why this type is correct")


RECLASSIFY_PROMPT = """You are a world-class macro/markets relationship architect.

Given two topics and their CURRENT relationship type, determine if the type is CORRECT
or if it should be reclassified to a different type.

=============================================================================
THE 5 CANONICAL RELATIONSHIP TYPES
=============================================================================

1. INFLUENCES (directional: A → B)
   A causes changes in B. A shock to A predictably moves B.
   Examples: fed_policy → ust10y, oil_prices → us_inflation, china_gdp → copper

2. CORRELATES_WITH (symmetric: A ↔ B)
   A and B move together without clear causality.
   Examples: copper ↔ iron_ore, em_fx ↔ risk_sentiment, aud ↔ commodity_prices

3. PEERS (symmetric: A ↔ B)
   A and B are functional substitutes or compete for the same capital.
   Examples: spx ↔ ndx, wti ↔ brent, fed_policy ↔ ecb_policy

4. COMPONENT_OF (directional: A → B, child to parent)
   A is literally part of B. A is a constituent of B.
   Examples: aapl → spx, germany_gdp → eu_gdp, tech_sector → spx

5. HEDGES (symmetric: A ↔ B)
   A provides protection against B. They move inversely in stress.
   Examples: gold ↔ inflation, vix ↔ spx, usd ↔ em_equities, jpy ↔ risk_sentiment

=============================================================================
DECISION TREE (USE IN ORDER)
=============================================================================

1. Is A literally part of B? → COMPONENT_OF
2. Does A cause B to move? → INFLUENCES
3. Do they move inversely / hedge each other? → HEDGES
4. Are they substitutes/competitors? → PEERS
5. Do they co-move without clear cause? → CORRELATES_WITH

=============================================================================
CURRENT RELATIONSHIP TO EVALUATE
=============================================================================

SOURCE TOPIC: {source_name} (id: {source_id})
TARGET TOPIC: {target_name} (id: {target_id})
CURRENT TYPE: {current_type}

=============================================================================
YOUR TASK
=============================================================================

Determine the CORRECT relationship type. If the current type is wrong, specify
the correct one. Consider:
- Is the direction correct? (for INFLUENCES and COMPONENT_OF)
- Is this really a hedge relationship that was misclassified as correlation?
- Are these actually peers that were misclassified?

Respond with JSON:
{{
    "correct_type": "INFLUENCES" | "CORRELATES_WITH" | "PEERS" | "COMPONENT_OF" | "HEDGES",
    "confidence": "high" | "medium" | "low",
    "reasoning": "Brief explanation of why this type is correct"
}}
"""


def get_all_topic_relationships() -> list[dict]:
    """Fetch all existing topic-to-topic relationships."""
    query = """
    MATCH (source:Topic)-[r]->(target:Topic)
    WHERE type(r) IN ['INFLUENCES', 'CORRELATES_WITH', 'PEERS', 'COMPONENT_OF', 'HEDGES']
    RETURN
        source.id as source_id,
        source.name as source_name,
        target.id as target_id,
        target.name as target_name,
        type(r) as rel_type,
        elementId(r) as rel_element_id
    """
    result = run_cypher(query, {})
    return result or []


def reclassify_relationship(
    source_id: str,
    source_name: str,
    target_id: str,
    target_name: str,
    current_type: str
) -> Optional[RelationshipReclassification]:
    """Ask LLM to evaluate if this relationship has the correct type."""
    llm = get_llm(ModelTier.SIMPLE)
    chain = llm | JsonOutputParser()

    prompt = RECLASSIFY_PROMPT.format(
        source_id=source_id,
        source_name=source_name,
        target_id=target_id,
        target_name=target_name,
        current_type=current_type
    )

    try:
        result = run_llm_decision(
            chain=chain,
            prompt=prompt,
            model=RelationshipReclassification,
            logger=logger
        )
        return result
    except Exception as e:
        logger.warning(f"LLM reclassification failed for {source_id} -> {target_id}: {e}")
        return None


def update_relationship_type(
    source_id: str,
    target_id: str,
    old_type: str,
    new_type: str
) -> bool:
    """
    Update relationship type by deleting old and creating new.

    Neo4j doesn't allow changing relationship types in-place,
    so we delete and recreate.
    """
    # Delete old relationship
    delete_query = f"""
    MATCH (source:Topic {{id: $source_id}})-[r:{old_type}]->(target:Topic {{id: $target_id}})
    DELETE r
    RETURN count(r) as deleted
    """
    delete_result = run_cypher(delete_query, {
        "source_id": source_id,
        "target_id": target_id
    })

    if not delete_result or delete_result[0].get("deleted", 0) == 0:
        logger.warning(f"Could not delete old relationship {source_id} -{old_type}-> {target_id}")
        return False

    # Create new relationship
    create_query = f"""
    MATCH (source:Topic {{id: $source_id}}), (target:Topic {{id: $target_id}})
    CREATE (source)-[r:{new_type}]->(target)
    SET r.reclassified_at = datetime(),
        r.reclassified_from = $old_type
    RETURN r
    """
    create_result = run_cypher(create_query, {
        "source_id": source_id,
        "target_id": target_id,
        "old_type": old_type
    })

    return create_result is not None and len(create_result) > 0


def run_relationship_reeval(
    limit: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """
    Re-evaluate all topic relationships and reclassify if needed.

    Args:
        limit: Max relationships to process (None = all)
        dry_run: If True, don't actually update, just report what would change

    Returns:
        Stats dict with counts of changes by type
    """
    relationships = get_all_topic_relationships()
    total = len(relationships)

    if limit:
        relationships = relationships[:limit]

    logger.info(f"Starting relationship re-evaluation: {len(relationships)} relationships (total in DB: {total})")
    if dry_run:
        logger.info("DRY RUN MODE - no changes will be made")

    track("relationship_reeval_started", f"total={len(relationships)}, dry_run={dry_run}")

    stats = {
        "total": len(relationships),
        "unchanged": 0,
        "reclassified": 0,
        "failed": 0,
        "changes": {
            "INFLUENCES_to_HEDGES": 0,
            "INFLUENCES_to_PEERS": 0,
            "INFLUENCES_to_COMPONENT_OF": 0,
            "INFLUENCES_to_CORRELATES_WITH": 0,
            "CORRELATES_WITH_to_HEDGES": 0,
            "CORRELATES_WITH_to_PEERS": 0,
            "CORRELATES_WITH_to_INFLUENCES": 0,
            "CORRELATES_WITH_to_COMPONENT_OF": 0,
            "other": 0
        }
    }

    for i, rel in enumerate(relationships, start=1):
        source_id = rel["source_id"]
        source_name = rel["source_name"]
        target_id = rel["target_id"]
        target_name = rel["target_name"]
        current_type = rel["rel_type"]

        logger.info(f"[{i}/{len(relationships)}] Evaluating: {source_name} -{current_type}-> {target_name}")

        # Get LLM assessment
        assessment = reclassify_relationship(
            source_id=source_id,
            source_name=source_name,
            target_id=target_id,
            target_name=target_name,
            current_type=current_type
        )

        if not assessment:
            stats["failed"] += 1
            continue

        correct_type = assessment.correct_type

        # Check if type needs to change
        if correct_type == current_type:
            logger.info(f"  -> UNCHANGED ({assessment.confidence} confidence): {assessment.reasoning[:80]}...")
            stats["unchanged"] += 1
            continue

        # Type change needed
        change_key = f"{current_type}_to_{correct_type}"
        if change_key in stats["changes"]:
            stats["changes"][change_key] += 1
        else:
            stats["changes"]["other"] += 1

        logger.info(f"  -> RECLASSIFY: {current_type} → {correct_type} ({assessment.confidence})")
        logger.info(f"     Reason: {assessment.reasoning}")

        if not dry_run:
            success = update_relationship_type(
                source_id=source_id,
                target_id=target_id,
                old_type=current_type,
                new_type=correct_type
            )
            if success:
                stats["reclassified"] += 1
                track("relationship_reclassified", f"{source_id} -{current_type}-> -{correct_type}-> {target_id}")
            else:
                stats["failed"] += 1
        else:
            stats["reclassified"] += 1  # Count as "would reclassify" in dry run

    # Log summary
    logger.info(f"\n{'='*60}")
    logger.info("RELATIONSHIP RE-EVALUATION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total evaluated: {stats['total']}")
    logger.info(f"Unchanged: {stats['unchanged']}")
    logger.info(f"Reclassified: {stats['reclassified']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info(f"\nChanges by type:")
    for change_type, count in stats["changes"].items():
        if count > 0:
            logger.info(f"  {change_type}: {count}")
    logger.info(f"{'='*60}")

    track("relationship_reeval_completed", f"reclassified={stats['reclassified']},unchanged={stats['unchanged']}")

    return stats


if __name__ == "__main__":
    import sys
    import os

    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
        PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    from utils.env_loader import load_env
    load_env()

    import argparse
    parser = argparse.ArgumentParser(description="Re-evaluate relationship types")
    parser.add_argument("--limit", type=int, help="Max relationships to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update, just report")
    args = parser.parse_args()

    stats = run_relationship_reeval(limit=args.limit, dry_run=args.dry_run)
    print(stats)
