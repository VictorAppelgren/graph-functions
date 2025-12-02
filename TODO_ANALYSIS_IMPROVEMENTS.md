# TODO: Analysis Rewriter Improvements

## Overview
Improve the analysis rewriting process to create deeper, more consistent, and higher-quality analysis by adding an "improvement suggestions" step before rewriting.

---

## Current Problem
- Rewrites start from scratch without considering what was good/bad about existing analysis
- No systematic way to deepen analysis over time
- Each rewrite is independent, losing continuity

---

## Proposed Solution: "Deepen & Improve" Flow

### New Flow
```python
def analysis_rewriter(topic_id, analysis_type, test=False):
    # 1. Load existing analysis
    existing_analysis = get_existing_analysis(topic_id, analysis_type)
    
    # 2. If analysis exists, run "deepen & improve" LLM first
    if existing_analysis:
        improvement_suggestions = llm_suggest_improvements(
            existing_analysis=existing_analysis,
            new_articles=get_recent_articles(topic_id, analysis_type)
        )
        logger.info(f"Improvement suggestions: {improvement_suggestions}")
    
    # 3. Generate new analysis (with improvement context)
    new_analysis = generate_analysis(
        topic_id=topic_id,
        analysis_type=analysis_type,
        existing_analysis=existing_analysis,
        improvement_focus=improvement_suggestions if existing_analysis else None
    )
    
    # 4. Save
    save_analysis(topic_id, analysis_type, new_analysis)
```

---

## Implementation Tasks

### Task 1: Create `llm_suggest_improvements()` Function
**File:** `src/analysis/policies/suggest_improvements.py` (NEW FILE)

**Purpose:** LLM reviews existing analysis + new articles and suggests what to deepen/improve

**Inputs:**
- `existing_analysis: str` - Current analysis text
- `new_articles: list[dict]` - Recent articles (last 5-10)
- `topic_name: str` - For context

**Output:**
- `ImprovementSuggestions` model with:
  - `gaps: list[str]` - What's missing or shallow
  - `new_developments: list[str]` - New info not reflected
  - `strengthen_areas: list[str]` - What to deepen
  - `overall_focus: str` - Main improvement direction

**Prompt Focus:**
- Identify weak/shallow sections
- Spot new developments not reflected
- Suggest specific areas to deepen
- Keep suggestions actionable (2-3 bullet points)

**LLM Tier:** MEDIUM (needs to understand analysis + articles)

---

### Task 2: Create Pydantic Model
**File:** `src/llm/models.py`

```python
class ImprovementSuggestions(BaseModel):
    """Suggestions for improving existing analysis."""
    
    gaps: list[str] = Field(
        description="Gaps or shallow areas in current analysis (2-3 items)"
    )
    
    new_developments: list[str] = Field(
        description="New developments from recent articles not reflected (2-3 items)"
    )
    
    strengthen_areas: list[str] = Field(
        description="Areas to deepen or strengthen (2-3 items)"
    )
    
    overall_focus: str = Field(
        description="Main improvement direction in 1 sentence"
    )
```

---

### Task 3: Create Improvement Prompt
**File:** `src/llm/prompts/suggest_improvements.py` (NEW FILE)

**Prompt Structure:**
```
SYSTEM_MISSION + SYSTEM_CONTEXT

You are reviewing an existing analysis to suggest improvements.

TOPIC: {topic_name}

EXISTING ANALYSIS:
{existing_analysis}

NEW ARTICLES (last 5):
{formatted_articles}

TASK:
Identify 2-3 specific improvements for each category:
1. GAPS - What's missing or too shallow?
2. NEW DEVELOPMENTS - What new info isn't reflected?
3. STRENGTHEN - What areas need deepening?
4. OVERALL FOCUS - Main improvement direction

Be specific and actionable. Focus on substance, not style.
```

---

### Task 4: Modify `analysis_rewriter()`
**File:** `src/analysis/orchestration/analysis_rewriter.py`

**Changes:**
1. Add import: `from src.analysis.policies.suggest_improvements import llm_suggest_improvements`
2. Add logic to call improvement suggestions if analysis exists
3. Pass improvement context to main analysis generation
4. Add logging for improvement suggestions
5. Add stats tracking: `master_statistics(analysis_improvement_suggestions_generated=1)`

**Pseudocode:**
```python
def analysis_rewriter(topic_id, analysis_type, test=False):
    # Load existing
    existing = get_existing_analysis(topic_id, analysis_type)
    
    improvement_context = None
    if existing:
        # Get recent articles for this section
        recent_articles = get_recent_articles_for_section(
            topic_id=topic_id,
            timeframe=analysis_type,
            limit=5
        )
        
        # Get improvement suggestions
        suggestions = llm_suggest_improvements(
            existing_analysis=existing,
            new_articles=recent_articles,
            topic_name=get_topic_name(topic_id)
        )
        
        improvement_context = format_improvement_context(suggestions)
        logger.info(f"Improvement suggestions: {suggestions.overall_focus}")
        master_statistics(analysis_improvement_suggestions_generated=1)
    
    # Generate analysis (pass improvement context)
    new_analysis = generate_analysis_with_context(
        topic_id=topic_id,
        analysis_type=analysis_type,
        improvement_focus=improvement_context
    )
    
    # Save
    save_analysis(topic_id, analysis_type, new_analysis)
```

---

### Task 5: Modify Analysis Generation Prompts
**File:** `src/llm/prompts/analysis_*.py` (multiple files)

**Add to each analysis prompt:**
```python
# If improvement_focus is provided, add to prompt:
if improvement_focus:
    prompt += f"""
    
    IMPROVEMENT FOCUS:
    {improvement_focus}
    
    Pay special attention to these areas when writing the analysis.
    """
```

---

### Task 6: Add Helper Function
**File:** `src/analysis/orchestration/analysis_rewriter.py`

```python
def get_recent_articles_for_section(
    topic_id: str,
    timeframe: str,
    limit: int = 5
) -> list[dict]:
    """
    Get recent articles for a specific timeframe section.
    
    Returns articles with:
    - id
    - summary
    - published_at
    - importance scores
    """
    query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
    WHERE r.timeframe = $timeframe
    ORDER BY a.published_at DESC
    LIMIT $limit
    RETURN 
        a.id as id,
        a.summary as summary,
        a.published_at as published_at,
        r.importance_risk as risk,
        r.importance_opportunity as opp,
        r.importance_trend as trend,
        r.importance_catalyst as cat
    """
    # Execute and return
```

---

### Task 7: Add Statistics Tracking
**File:** `src/observability/pipeline_logging.py`

**Add counter:**
```python
class AnalysisStats(BaseModel):
    # ... existing fields ...
    improvement_suggestions_generated: int = 0
```

**Add parameter to `master_statistics()`:**
```python
def master_statistics(
    # ... existing params ...
    analysis_improvement_suggestions_generated: int = 0,
):
    # ... existing logic ...
    if analysis_improvement_suggestions_generated:
        t.analysis.improvement_suggestions_generated += analysis_improvement_suggestions_generated
```

---

## Testing Strategy

### Unit Tests
1. Test `llm_suggest_improvements()` with sample analysis + articles
2. Test improvement context formatting
3. Test analysis generation with/without improvement context

### Integration Tests
1. Run full rewrite flow with existing analysis
2. Verify improvement suggestions are generated
3. Verify new analysis incorporates suggestions

### Manual Testing
1. Pick a topic with existing analysis
2. Add new tier-3 article
3. Trigger rewrite
4. Review logs for improvement suggestions
5. Compare old vs new analysis

---

## Rollout Plan

### Phase 1: Build & Test (Local)
- [ ] Create all new files
- [ ] Write unit tests
- [ ] Test locally with test mode

### Phase 2: Deploy & Monitor (Server)
- [ ] Deploy to server
- [ ] Monitor stats for `improvement_suggestions_generated`
- [ ] Review sample rewrites for quality

### Phase 3: Tune & Optimize
- [ ] Adjust prompt based on results
- [ ] Tune number of articles to include
- [ ] Consider caching improvement suggestions

---

## Open Questions

1. **LLM Cost:** Extra LLM call per rewrite - acceptable?
2. **Article Count:** How many recent articles to include? (5? 10?)
3. **Scope:** Only for tier-3 rewrites, or all rewrites?
4. **Caching:** Should we cache improvement suggestions for X minutes?

---

## Success Metrics

- [ ] Improvement suggestions generated > 0 per day
- [ ] Analysis quality subjectively better (manual review)
- [ ] Rewrites incorporate new developments more consistently
- [ ] Analysis depth increases over time

---

## Notes

- This is a QUALITY improvement, not a bug fix
- Can be implemented incrementally
- Should not break existing rewrite flow
- Falls back gracefully if improvement step fails
