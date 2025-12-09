from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT

llm_select_one_new_link_prompt = """
    {system_mission}
    {system_context}

    YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.
    
    PERSPECTIVE-NEUTRAL LINKING:
    - Links connect persistent analytical anchors (assets, policies, drivers)
    - "Fed Policy" INFLUENCES "EURUSD" (not "Fed Dovish Risk" influences anything)
    - Focus on structural causal/correlational relationships between persistent topics
    
    TASK:
    - Given the source topic, candidate topics, and existing links, propose the single strongest missing link.
    - If NO strong link exists, output: {{"motivation": "", "type": "", "source": "", "target": ""}}
    - If a strong link exists, output a complete JSON object with all required fields.
    
    CRITICAL REQUIREMENTS:
    - ALWAYS output valid JSON, even if empty
    - NEVER output null, undefined, or non-JSON responses
    - ALL four fields are REQUIRED: "motivation", "type", "source", "target"
    - Use empty strings ("") if no link should be created

    CANONICAL LINK TYPES (YOU MUST USE EXACTLY ONE OF THESE STRINGS):

    {link_type_descriptions}

    HARD CONSTRAINTS ON "type":
    - The "type" field MUST be one of: "INFLUENCES", "CORRELATES_WITH", "PEERS", "COMPONENT_OF".
    - NEVER output "DRIVES", "DRIVEN_BY", "IMPACTS", "RELATED_TO", or any other relationship label.
    - If you think "A drives B" or "A impacts B", you MUST output "INFLUENCES" with direction A → B.
    - If you think "A is driven by B", you MUST flip the direction and output B INFLUENCES A.

    EXAMPLE OUTPUTS:
    Strong link:
    {{"motivation": "ECB policy directly influences EUR/USD exchange rate through interest rate differentials.",
      "type": "INFLUENCES", "source": "ecb_policy", "target": "eurusd"}}

    No link:
    {{"motivation": "", "type": "", "source": "", "target": ""}}
    
    SOURCE TOPIC:
    {source_name} (id: {source_id})
    
    CANDIDATE TOPICS:
    {candidate_lines}
    
    CURRENT LINKS:
    {existing_links}
    
    RESPOND WITH VALID JSON ONLY - NO OTHER TEXT:
    """