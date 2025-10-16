# User Strategies

Simple file-based strategy storage with automatic versioning.

---

## API Endpoints

```bash
POST   /strategies                    # Create strategy
GET    /strategies?username=X         # List user's strategies  
GET    /strategies/{id}?username=X    # Get full strategy
PUT    /strategies/{id}               # Update strategy
DELETE /strategies/{id}?username=X    # Delete (archive) strategy
```

---

## Create Strategy

```bash
POST /strategies
{
  "username": "Victor",
  "asset_primary": "EURUSD",
  "strategy_text": "EUR strength driven by ECB hawkish pivot...",
  "position_text": "Long from 1.0850, size 2% portfolio, stop at 1.0750",
  "target": "1.1200"
}
```

---

## Strategy Schema

```json
{
  "id": "strategy_001",
  "created_at": "2025-10-13T10:00:00+02:00",
  "updated_at": "2025-10-13T10:00:00+02:00",
  "version": 1,
  
  "asset": {
    "primary": "EURUSD",
    "related": []
  },
  
  "user_input": {
    "strategy_text": "User's thesis...",
    "position_text": "Position details...",
    "target": "1.1200"
  },
  
  "analysis": {
    "generated_at": null,
    "fundamental": "",
    "current": "",
    "risks": "",
    "drivers": "",
    "supporting_evidence": [],
    "contradicting_evidence": []
  }
}
```

---

## File Structure

```
API/users/
├── Victor/
│   ├── strategy_001.json
│   ├── strategy_002.json
│   └── archive/
│       └── strategy_001_20251013_101745.json
└── William/
    ├── strategy_001.json
    └── archive/
```

---

## Key Features

- **Auto-versioning**: Every update archives old version
- **Auto-incrementing IDs**: `strategy_001`, `strategy_002`, etc.
- **Fail-fast**: Raises exceptions on errors
- **Atomic writes**: No partial updates

---

## Testing

```bash
python test_strategy_api.py
```

---

## Phase 2: Custom Analysis

The `analysis` section will be populated by custom analysis engine.

**See `CUSTOM_ANALYSIS_PLAN.md` for implementation details.**

Key steps:
1. Discover related topics from graph
2. Collect articles and existing analysis
3. Generate 4 custom sections (fundamental, current, risks, drivers)
4. Classify supporting vs contradicting evidence
5. Update strategy JSON

---

## Implementation

**Core:** `user_data_manager.py`  
**API:** `api_main_v2.py` (strategy routes)  
**Plan:** `CUSTOM_ANALYSIS_PLAN.md` (Phase 2)
