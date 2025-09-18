select_not_crucial_topics_llm_prompt = """
{system_mission}
{system_context}

You must identify all Topic IDs that are NOT crucial to the macro graph.
A topic IS crucial if it clearly fits the mission and Interest Areas AND maps to market handles with a causal path and catalysts, or adds pillar diversification.
Reject as NOT crucial if off-scope, micro/local with no scalable macro path, no handle mapping, no catalysts, duplicates/near-duplicates, or weak/no pillar contribution.

Output must be ONLY a valid JSON object. No prose, no markdown, no backticks, no comments.
Return exactly this shape:
{{"ids_to_remove": ["<id1>", "<id2>", "..."]}}

Hard requirements:
- All IDs MUST come from the whitelist candidate_ids.
- You may return zero or more IDs.
- Do NOT include any other fields or text.

Whitelist candidate IDs (return only from this list):
candidate_ids = {candidate_ids}

Candidate details (context only, do not output):
{candidates}

Now output ONLY the JSON object described above.
"""