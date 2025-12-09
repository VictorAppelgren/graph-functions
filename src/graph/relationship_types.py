"""Canonical topic–topic relationship types for the Saga graph.

These are the ONLY allowed relationship labels between Topic nodes.
Use these exact strings in all LLM prompts and Cypher queries.

IMPORTANT CONSTRAINTS (FOR PROMPTS AND CODE):
- Valid relationship type strings are ONLY: "INFLUENCES", "CORRELATES_WITH", "PEERS", "COMPONENT_OF".
- NEVER use "DRIVES", "DRIVEN_BY", "IMPACTS", "RELATED_TO" or any other verb as a relationship label.
- If you would naturally say "A drives B" or "A impacts B", you MUST encode it as "A INFLUENCES B".

The descriptions below can be injected into prompts to help an LLM
choose the correct relationship type and direction.
"""

INFLUENCES = "INFLUENCES"
CORRELATES_WITH = "CORRELATES_WITH"
PEERS = "PEERS"
COMPONENT_OF = "COMPONENT_OF"

# Human-readable descriptions keyed by canonical relationship name.
# Safe to use directly in prompts.
RELATIONSHIP_DESCRIPTIONS = {
    INFLUENCES: (
        "INFLUENCES: A → B means changes in A are a primary causal driver of B. "
        "Use this when you would say 'B is driven by A' or 'A impacts B'. "
        "Directional: encode 'A drives B' as A INFLUENCES B."
    ),
    CORRELATES_WITH: (
        "CORRELATES_WITH: A ↔ B move together / are statistically correlated in a "
        "stable, economically meaningful way. Symmetric: use when co-movement is "
        "important but causality is unclear or two-way."
    ),
    PEERS: (
        "PEERS: A ↔ B are close functional substitutes, competitors, or play the "
        "same structural role (same 'slot' in a portfolio or system). Symmetric: "
        "examples include major indices, mega-cap tech peers, or rival banks."
    ),
    COMPONENT_OF: (
        "COMPONENT_OF: A → B means A is a component or member of B (child → parent). "
        "Use for index/sector/aggregate membership, not generic influence."
    ),
}
