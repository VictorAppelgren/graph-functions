relevance_gate_llm_prompt = """
    THE KNOWLEDGE SYSTEM YOU ARE WORKING WITH AIMS TO DO THE FOLLOWING:
    {system_mission}
    {system_context}

    You are a strict relevance gate for topic-section enrichment.

    TOPIC: {topic_name}

    SECTION FOCUS: {focus}

    CURRENT SECTION COVERAGE (recent, non-hidden):
    {existing_summaries}

    CANDIDATE ARTICLE (to consider adding):
    {article_text}

    TASK:
    - Judge whether the candidate substantively complements or improves the section coverage for the topic.
    - Reject if redundant, off-topic, or low-signal relative to CURRENT SECTION COVERAGE.
    - Consider diversity and recency of angles.

    Output ONLY a JSON object with exactly:
      - motivation: short one-sentence justification (first field)
      - relevant: true/false

    EXAMPLE OUTPUT:
    {{"motivation": "Adds a fresh perspective on X not covered by current articles.", "relevant": true}}

    YOUR RESPONSE:
    """