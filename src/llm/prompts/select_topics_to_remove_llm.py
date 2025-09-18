select_topics_to_remove_llm_prompt = """
{system_mission}
{system_context}

You are selecting Topic IDs to remove to meet capacity.
Output must be ONLY valid JSON. No prose, no markdown, no backticks, no comments.

{format_instructions}

Return exactly this JSON shape:
{{"ids_to_remove": ["<id1>", "<id2>", "..."]}}

Hard requirements:
- Return a maximum {remove_count} unique IDs.
- Each ID MUST be from the whitelist candidate_ids (see below).
- Do NOT include any other fields.
- Do NOT include explanations or extra text.
- If you include anything other than the exact JSON object, your answer will be discarded.

Selection policy (for decision quality; do not output this):
- Prefer the lowest importance first (ascending).
- Break ties by oldest last_updated first (ascending time).
- If importance or last_updated is missing, treat importance=0 and last_updated="1970-01-01T00:00:00".

Candidate whitelist (you may ONLY output IDs from this list):
candidate_ids = {candidate_ids}

Candidate details (context only, do not output):
{candidates}

Interest scope (for guidance only; do not output this):
{scope_text}
THESE ARE THE ONLY INTERESTS WE HAVE! SO ANYTHING NOT FULLY RELEVANT TO THESE TOPICS SHOULD BE REMOVED! 

FOCUS ON IDENTIFYING THE LEAST INTERESTING TOPICS TO REMOVE.

Now output ONLY the JSON object described above.
"""