"""
Topic Mapper - Graph Strategy

MISSION: Get all available topics and their relationships from the graph.
Returns ALL 5 relationship types with direction semantics for strategy mapping.
"""

from typing import Dict, List
from src.graph.ops.topic import get_all_topics
from src.graph.neo4j_client import run_cypher


def explore_graph() -> Dict:
    """
    Get all available topics and ALL relationship types.

    Returns:
        {
            "topics": List[{"id": str, "name": str}],
            "relationships": {
                "influences": Dict[str, List[str]],      # topic_id -> [topics it INFLUENCES]
                "influenced_by": Dict[str, List[str]],   # topic_id -> [topics that INFLUENCE it]
                "correlates_with": Dict[str, List[str]], # symmetric co-movement
                "peers": Dict[str, List[str]],           # symmetric substitutes/competitors
                "components": Dict[str, List[str]],      # topic_id -> [its COMPONENTS]
                "part_of": Dict[str, List[str]],         # topic_id -> [topics it's PART OF]
                "hedges": Dict[str, List[str]]           # symmetric risk offsets
            }
        }
    """

    # Get all topics using helper function
    topics_result = get_all_topics(fields=["id", "name"])

    if not topics_result:
        return {
            "topics": [],
            "relationships": {
                "influences": {},
                "influenced_by": {},
                "correlates_with": {},
                "peers": {},
                "components": {},
                "part_of": {},
                "hedges": {}
            }
        }

    topics = [
        {"id": row["id"], "name": row["name"]}
        for row in topics_result
    ]

    # Get ALL relationship types with direction
    relationships_query = """
    // INFLUENCES (directional: source drives target)
    OPTIONAL MATCH (t1:Topic)-[:INFLUENCES]->(t2:Topic)
    WITH collect({source: t1.id, target: t2.id}) as influences_raw

    // CORRELATES_WITH (symmetric)
    OPTIONAL MATCH (t1:Topic)-[:CORRELATES_WITH]-(t2:Topic)
    WITH influences_raw, collect(DISTINCT {t1: t1.id, t2: t2.id}) as correlates_raw

    // PEERS (symmetric)
    OPTIONAL MATCH (t1:Topic)-[:PEERS]-(t2:Topic)
    WITH influences_raw, correlates_raw, collect(DISTINCT {t1: t1.id, t2: t2.id}) as peers_raw

    // COMPONENT_OF (directional: child is part of parent)
    OPTIONAL MATCH (child:Topic)-[:COMPONENT_OF]->(parent:Topic)
    WITH influences_raw, correlates_raw, peers_raw,
         collect({child: child.id, parent: parent.id}) as components_raw

    // HEDGES (symmetric)
    OPTIONAL MATCH (t1:Topic)-[:HEDGES]-(t2:Topic)
    WITH influences_raw, correlates_raw, peers_raw, components_raw,
         collect(DISTINCT {t1: t1.id, t2: t2.id}) as hedges_raw

    RETURN influences_raw, correlates_raw, peers_raw, components_raw, hedges_raw
    """

    result = run_cypher(relationships_query, {})

    # Initialize relationship dicts
    relationships = {
        "influences": {},        # topic -> topics it drives
        "influenced_by": {},     # topic -> topics that drive it
        "correlates_with": {},   # symmetric
        "peers": {},             # symmetric
        "components": {},        # parent -> children
        "part_of": {},           # child -> parents
        "hedges": {}             # symmetric
    }

    if result and len(result) > 0:
        row = result[0]

        # Process INFLUENCES (directional)
        for rel in row.get("influences_raw", []):
            if rel.get("source") and rel.get("target"):
                source, target = rel["source"], rel["target"]
                relationships["influences"].setdefault(source, []).append(target)
                relationships["influenced_by"].setdefault(target, []).append(source)

        # Process CORRELATES_WITH (symmetric)
        for rel in row.get("correlates_raw", []):
            if rel.get("t1") and rel.get("t2"):
                t1, t2 = rel["t1"], rel["t2"]
                relationships["correlates_with"].setdefault(t1, []).append(t2)
                relationships["correlates_with"].setdefault(t2, []).append(t1)

        # Process PEERS (symmetric)
        for rel in row.get("peers_raw", []):
            if rel.get("t1") and rel.get("t2"):
                t1, t2 = rel["t1"], rel["t2"]
                relationships["peers"].setdefault(t1, []).append(t2)
                relationships["peers"].setdefault(t2, []).append(t1)

        # Process COMPONENT_OF (directional)
        for rel in row.get("components_raw", []):
            if rel.get("child") and rel.get("parent"):
                child, parent = rel["child"], rel["parent"]
                relationships["components"].setdefault(parent, []).append(child)
                relationships["part_of"].setdefault(child, []).append(parent)

        # Process HEDGES (symmetric)
        for rel in row.get("hedges_raw", []):
            if rel.get("t1") and rel.get("t2"):
                t1, t2 = rel["t1"], rel["t2"]
                relationships["hedges"].setdefault(t1, []).append(t2)
                relationships["hedges"].setdefault(t2, []).append(t1)

        # Deduplicate symmetric relationships
        for key in ["correlates_with", "peers", "hedges"]:
            for topic_id in relationships[key]:
                relationships[key][topic_id] = list(set(relationships[key][topic_id]))

    return {
        "topics": topics,
        "relationships": relationships
    }
