# Custom User Analysis System

Expert-level, personalized analysis for user trading strategies.

---

## Overview

Generates Financial Times quality analysis tailored to each user's specific thesis, position, and target by leveraging the entire graph and existing topic analysis.

---

## Architecture

```
src/custom_user_analysis/
├── strategy_analyzer.py          # Main orchestrator
├── topic_discovery.py             # Map user asset → graph topics
├── material_collector.py          # Collect analysis from topics
├── evidence_classifier.py         # Supporting vs contradicting
└── prompts/
    ├── executive_summary_prompt.py # Ultra-concise synthesis (3-4 sentences)
    ├── fundamental_prompt.py      # Long-term structural analysis
    ├── current_prompt.py          # Near-term catalysts
    ├── risks_prompt.py            # Threat identification
    └── drivers_prompt.py          # Cross-asset synthesis
```

---

## Usage

### Generate Analysis
```python
from src.custom_user_analysis.strategy_analyzer import generate_custom_user_analysis

generate_custom_user_analysis(
    username="Victor",
    strategy_id="strategy_001"
)
```

### Command Line
```bash
python src/custom_user_analysis/strategy_analyzer.py Victor strategy_001
```

### Test
```bash
python tests/test_custom_user_analysis.py
```

---

## Pipeline Flow

1. **Load Strategy** - Read user's thesis, position, target from JSON
2. **Topic Discovery** - Map user's asset to graph topics via LLM
3. **Material Collection** - Selectively gather analysis from topics
4. **Analysis Generation** - Generate 5 sections via expert prompts
5. **Evidence Classification** - Separate supporting vs contradicting
6. **Save Results** - Update strategy JSON (auto-archives old version)

---

## Analysis Sections

### 0. Executive Summary ⭐ NEW
- **Ultra-concise synthesis** (3-4 sentences only)
- Clear verdict: Does analysis support or contradict thesis?
- Key catalyst: Single most important driver
- Critical risk: Biggest threat to thesis
- Actionable recommendation: What to do next
- **Tone:** Decisive, actionable, specific
- **Generated:** Last (synthesizes all 4 sections below)

### 1. Fundamental Analysis
- Long-term structural drivers
- Path to target assessment
- Thesis validation
- Structural risks
- **Tone:** Authoritative, multi-year perspective

### 2. Current Analysis
- Near-term catalysts (0-3 weeks)
- Immediate probability assessment
- Cross-asset signals
- Invalidation triggers
- **Tone:** Urgent, actionable

### 3. Risks Analysis
- Top 5 risks ranked by probability × impact
- Contradicting evidence
- Scenario analysis
- Invalidation framework
- **Tone:** Balanced, objective

### 4. Drivers Analysis
- Supporting drivers (3-5)
- Contradicting drivers (2-3)
- Cross-asset dynamics
- Net assessment
- **Tone:** Sophisticated synthesis

---

## Prompt Standards

All prompts follow **Financial Times editorial quality**:

- ✅ Authoritative and precise
- ✅ Maximum information density
- ✅ Professional conviction
- ✅ Evidence-based with citations (9-char IDs)
- ✅ Asset-specific focus
- ✅ No hedging language
- ✅ Decision-useful intelligence

---

## Material Collection Strategy

**PRIMARY TOPICS** (2-4 topics)
- ✅ All sections: fundamental, medium, current, drivers, executive_summary

**DRIVER TOPICS** (3-6 topics)
- ✅ Current + drivers only

**CORRELATED TOPICS** (up to 5 topics)
- ✅ Current only

**Token Budget:** ~10K tokens of material per analysis

---

## Evidence Classification

Each analysis section classified as:
- **Supporting** - Aligns with user's thesis
- **Contradicting** - Opposes user's view
- **Neutral** - Not directly relevant

Top 10 of each saved to strategy JSON with:
- Topic name
- Section name
- Key insight (1 sentence)
- Confidence score

---

## Output Structure

Updated strategy JSON:
```json
{
  "asset": {
    "primary": "USD Currency",
    "related": ["dxy", "eurusd", "fed_policy", "ecb_policy"]
  },
  "analysis": {
    "generated_at": "2025-10-13T12:00:00+02:00",
    "executive_summary": "Analysis supports USD depreciation thesis. Fed rate cuts (UZY94UM7H) compress real-rate differential by 15-25bp, the primary catalyst for USD weakness. Critical risk is unexpected Fed hawkishness or ECB dovish pivot (A5LPH3RBB). Enter short USD positions when DXY breaks 101.5, targeting 1.065 EURUSD.",
    "fundamental": "Expert analysis...",
    "current": "Expert analysis...",
    "risks": "Expert analysis...",
    "drivers": "Expert analysis...",
    "supporting_evidence": [...],
    "contradicting_evidence": [...]
  }
}
```

---

## Performance

- **Generation Time:** 90-120 seconds per strategy
- **LLM Calls:** 5 major (executive summary + 4 sections) + ~10 classification calls
- **Token Usage:** ~60K tokens per strategy
- **Cost:** ~$0.60-1.20 per analysis (GPT-4)

---

## Testing

Run test with Victor's actual strategy:
```bash
python tests/test_custom_user_analysis.py
```

Verifies:
- ✅ Topic discovery works
- ✅ Material collection succeeds
- ✅ All 4 sections generated
- ✅ Evidence classified
- ✅ Strategy JSON updated
- ✅ Old version archived

---

## Key Features

### ✅ Asset Agnostic
- Works with any asset type (FX, commodities, rates, equities)
- No hardcoded asset-specific logic
- LLM maps user's free-text to graph topics

### ✅ Flexible Material Collection
- Adapts to available analysis
- Truncates if too long
- Prioritizes relevant sections

### ✅ Expert-Level Prompts
- Financial Times quality
- Professional tone throughout
- Maximum insight density
- Specific citations

### ✅ Fail-Fast Design
- Raises exceptions on errors
- Comprehensive logging
- Statistics tracking
- No silent failures

---

## Integration

### API Endpoint (Future)
```python
@app.post("/strategies/{strategy_id}/generate-analysis")
def generate_analysis(strategy_id: str, username: str):
    generate_custom_user_analysis(username, strategy_id)
    return {"success": True}
```

### Batch Job (Future)
```python
# Daily at 5 AM
for user in all_users:
    for strategy in user_strategies:
        generate_custom_user_analysis(user, strategy)
```

---

## Notes

- Reuses existing graph infrastructure
- Leverages topic analysis already generated
- Follows SAGA_V3 principles (fail-fast, IDs-only, stateless)
- All prompts in dedicated directory for easy updates
- Professional quality suitable for institutional use
