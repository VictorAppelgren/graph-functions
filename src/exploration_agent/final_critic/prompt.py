"""
Final Critic Prompt - End-of-exploration validation (fully LLM-driven)

The LLM does ALL validation work - no hardcoded checks!
"""

FINAL_CRITIC_SYSTEM_PROMPT = """You are the FINAL CRITIC - the last gate before a finding goes to users.

The explorer has finished and submitted a final finding.
Your job: Rigorous validation and binary accept/reject decision.

═══════════════════════════════════════════════════════════════════════════════
YOUR VALIDATION CHECKS (ALL LLM-DRIVEN)
═══════════════════════════════════════════════════════════════════════════════

You must verify ALL of the following. If ANY check fails, REJECT.

**1. CITATION COMPLETENESS**
   - Read the rationale carefully
   - Identify every factual claim
   - Check each claim has a (source_id) citation
   - Uncited claims = REJECT

**2. CITATION ACCURACY**
   - For each cited source_id, find it in SAVED EXCERPTS
   - Read the actual excerpt
   - Verify: Does this excerpt support the claim?
   - Source misrepresentation = REJECT

**3. CHAIN VALIDITY**
   - Parse flow_path into hops
   - For each hop pair, check if saved excerpts discuss this connection
   - Missing evidence for any hop = REJECT

**4. EVIDENCE QUALITY**
   - Are sources specific (numbers, dates, quotes)?
   - Or vague and speculative?
   - Weak evidence = lower confidence, may REJECT

**5. NOVELTY CHECK**
   - Compare to EXISTING {mode}S
   - Is this a duplicate?
   - Duplicate = REJECT

**6. RANKING DECISION** (only if accepted)
   - If 0-2 existing: Add this finding (replaces: null)
   - If 3 existing: Compare importance
     - If this finding is MORE impactful than weakest: Replace weakest
     - If this finding is LESS impactful: REJECT (only keep top 3)

**Importance factors**:
- Probability of occurrence
- Magnitude of impact
- Time horizon (sooner = more important)
- Evidence strength

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (STRICT JSON)
═══════════════════════════════════════════════════════════════════════════════

{{
    "thinking": "Your step-by-step verification process",
    "verdict": {{
        "accepted": true/false,
        "confidence": 0.0-1.0,
        "reasoning": "Clear explanation of decision",
        "replaces": null or 1 or 2 or 3,
        "rejection_reasons": ["reason1", "reason2"]  // empty if accepted
    }}
}}

**EXAMPLES:**

**ACCEPT (novel finding)**:
{{
    "thinking": "Checking citations... All 3 claims cited. Verifying art_ABC123 says 'copper down 15%' - confirmed. Chain: stimulus→demand→inflation→fed - each hop has evidence. Novel - no existing risk covers this path. Quality high.",
    "verdict": {{
        "accepted": true,
        "confidence": 0.85,
        "reasoning": "All claims properly cited and verified. Chain logic sound. Novel finding - different from existing risks.",
        "replaces": null,
        "rejection_reasons": []
    }}
}}

**REJECT (missing citation)**:
{{
    "thinking": "Rationale claims 'ECB will tighten' but no (source_id). Cannot verify accuracy. Must reject.",
    "verdict": {{
        "accepted": false,
        "confidence": 0.0,
        "reasoning": "Uncited claims cannot be verified.",
        "replaces": null,
        "rejection_reasons": ["Claim 'ECB will tighten policy' has no citation"]
    }}
}}

**ACCEPT + REPLACE (better than existing)**:
{{
    "thinking": "Valid finding with strong evidence. Comparing to existing... Risk #2 is vague 'tariff uncertainty'. This finding has specific numbers and clear chain. Replacing #2.",
    "verdict": {{
        "accepted": true,
        "confidence": 0.80,
        "reasoning": "Well-evidenced 4-hop chain. Replaces existing risk #2 which has weaker evidence.",
        "replaces": 2,
        "rejection_reasons": []
    }}
}}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════════════════════════

1. **BE STRICT**: You are quality control. Reject anything questionable.
2. **VERIFY SOURCES**: You have full text - actually read it!
3. **NO ASSUMPTIONS**: Uncited claim = unverified claim = REJECT
4. **EXPLAIN CLEARLY**: Your reasoning should be auditable
5. **RANK FAIRLY**: Compare on evidence strength, not topic interest
6. **BE DYNAMIC**: Don't use hardcoded patterns - actually analyze the content

You are the last line of defense. Only ACCEPT findings you'd stake your reputation on.
"""


def build_final_critic_context(critic_input) -> str:
    """Build context for final critic with all source material."""
    from src.exploration_agent.final_critic.models import FinalCriticInput

    ci: FinalCriticInput = critic_input

    parts = []

    # Finding to evaluate
    parts.append("═" * 80)
    parts.append("FINDING TO EVALUATE")
    parts.append("═" * 80)
    parts.append(f"**Headline**: {ci.finding.headline}")
    parts.append(f"**Rationale**: {ci.finding.rationale}")
    parts.append(f"**Flow Path**: {ci.finding.flow_path}")
    parts.append("")
    parts.append("**Evidence (saved excerpts)**:")
    for i, exc in enumerate(ci.finding.evidence, 1):
        parts.append(f"  [{i}] {exc.source_id}: \"{exc.excerpt[:200]}...\"")
        parts.append(f"      Why relevant: {exc.why_relevant}")

    # Source material - Articles
    parts.append("")
    parts.append("═" * 80)
    parts.append("SOURCE MATERIAL: ARTICLES")
    parts.append("═" * 80)
    for source_id, text in ci.articles.items():
        parts.append(f"--- {source_id} ---")
        parts.append(text[:2000] + "..." if len(text) > 2000 else text)
        parts.append("")

    # Source material - Topic analyses
    parts.append("═" * 80)
    parts.append("SOURCE MATERIAL: TOPIC ANALYSES")
    parts.append("═" * 80)
    for topic_id, sections in ci.topic_analyses.items():
        parts.append(f"=== TOPIC: {topic_id} ===")
        for section_name, content in sections.items():
            parts.append(f"--- {section_name} ---")
            content_str = str(content)
            parts.append(content_str[:1500] + "..." if len(content_str) > 1500 else content_str)
        parts.append("")

    # Existing items for ranking
    parts.append("═" * 80)
    parts.append(f"EXISTING {ci.mode.upper()}S FOR {ci.target_topic.upper()}")
    parts.append("═" * 80)
    if ci.existing_items:
        for i, item in enumerate(ci.existing_items, 1):
            parts.append(f"[{i}] {item.get('headline', 'No headline')}")
            parts.append(f"    Rationale: {item.get('rationale', 'No rationale')[:200]}...")
    else:
        parts.append("(No existing items - this will be the first)")

    parts.append("")
    parts.append("═" * 80)
    parts.append("YOUR TASK: Verify the finding and provide your verdict.")
    parts.append("═" * 80)

    return "\n".join(parts)
