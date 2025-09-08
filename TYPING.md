# Type Checking in SAGA Graph

This document explains the strict typing system implemented in SAGA Graph, following the "fail fast, fail loud" principle.

## Overview

SAGA Graph uses **MyPy with strict typing rules** to ensure code quality and prevent runtime errors. The type system is configured to be unforgiving - it catches type issues early rather than allowing them to cause problems later.

## Configuration Files

### `mypy.ini` - Main Configuration
- **Strict mode enabled** - All type checking rules enforced
- **Module-specific rules** - Different strictness levels per module type
- **Error reporting** - Detailed error codes and column numbers

### `pre-commit-config.yaml` - Automated Checks
- **Pre-commit hooks** - Type checking runs before every commit
- **Code formatting** - Black and isort for consistent style
- **Additional checks** - File formatting, JSON/YAML validation

### `config/pyproject.toml` - Project Integration
- **Development dependencies** - MyPy and type stubs
- **Tool configuration** - Alternative MyPy config location

## Type System Components

### 1. Graph Database Types (`graph_db/types.py`)

**Strongly typed Neo4j entities:**
```python
from graph_db.types import TopicNode, ArticleNode

# Clear structure - IDE knows all properties
topic: TopicNode = get_topic_by_id('eurusd')
print(topic['name'])  # Type safe, autocomplete works
```

**Available types:**
- `TopicNode` - Topic node properties
- `ArticleNode` - Article node properties  
- `Relationship` - Edge properties
- `CountResult` - Query count returns
- `IdResult` - ID-only query results

### 2. Enhanced Database Driver (`graph_db/db_driver.py`)

**Typed query methods:**
```python
# Instead of unclear run_cypher() results
topics: List[TopicNode] = get_topics(limit=10, status='active')
exists: bool = node_exists('Topic', 'id', 'eurusd')
count: int = count_nodes('Topic', 'n.status = $status', {'status': 'active'})
```

**Available methods:**
- `get_topics()` → `List[TopicNode]`
- `get_topic_by_id()` → `Optional[TopicNode]`
- `get_articles()` → `List[ArticleNode]`
- `count_nodes()` → `int`
- `node_exists()` → `bool`
- `execute_write()` → `List[Neo4jRecord]`

## Strictness Levels by Module

### Level 1: Maximum Strictness
**Modules:** `graph_db/*`, `utils/*`
- All type annotations required
- No `Any` types allowed (except explicit)
- All function signatures must be complete

### Level 2: Business Logic Strictness  
**Modules:** `*_llm.py`, entry points
- Function signatures required
- Return types enforced
- Some flexibility for LLM chain types

### Level 3: Moderate Strictness
**Modules:** Scripts, backfill utilities
- Type annotations encouraged
- Missing annotations warned but not blocked

### Level 4: Lenient
**Modules:** Tests, external integrations
- Basic type checking only
- Focus on preventing obvious errors

## Development Workflow

### 1. Setup (One Time)
```bash
# Install development dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install

# Verify setup
make typecheck
```

### 2. Daily Development
```bash
# Before coding - run type checks
make typecheck

# During development - format code  
make format

# Before committing - run all checks
make pre-commit
```

### 3. Type Checking Commands
```bash
# Standard type check
python scripts/typecheck.py
make typecheck

# Strict checking (all modules)
make typecheck-strict

# Watch mode (reruns on file changes)
make typecheck-watch
```

## Common Type Patterns

### 1. Function Signatures
```python
# GOOD: Complete type annotations
def process_topic(topic_id: str, limit: Optional[int] = None) -> List[ArticleNode]:
    return get_articles(limit=limit, topic_id=topic_id)

# BAD: Missing types  
def process_topic(topic_id, limit=None):
    return get_articles(limit=limit, topic_id=topic_id)
```

### 2. Neo4j Query Results
```python
# GOOD: Use typed methods
topics: List[TopicNode] = get_topics(status='active')
for topic in topics:
    print(f"Topic: {topic['name']}")  # Type safe

# BAD: Raw queries with unclear results
results = run_cypher("MATCH (t:Topic) WHERE t.status = 'active' RETURN t")
for r in results:
    topic = r.get('t', {})  # What properties does this have?
    print(f"Topic: {topic.get('name', 'Unknown')}")  # Error prone
```

### 3. Optional Values
```python
# GOOD: Explicit None handling
topic: Optional[TopicNode] = get_topic_by_id(topic_id)
if topic is not None:
    return topic['name']
return "Topic not found"

# BAD: Implicit assumptions
topic = get_topic_by_id(topic_id)
return topic['name']  # Could crash if topic is None
```

### 4. LLM Helper Returns
```python
# GOOD: Tuple returns with types
def analyze_sentiment_llm(article_id: str) -> tuple[str, float]:
    # ... LLM logic
    return sentiment, confidence

# Usage with unpacking
sentiment, confidence = analyze_sentiment_llm(article_id)
```

## Error Examples and Fixes

### 1. Missing Return Type
```python
# ERROR: Function is missing a return type annotation
def get_active_topics():  # mypy error
    return get_topics(status='active')

# FIX: Add return type
def get_active_topics() -> List[TopicNode]:
    return get_topics(status='active')
```

### 2. Incompatible Types
```python
# ERROR: Argument 1 to "get_topics" has incompatible type "int"; expected "Optional[int]"
topics = get_topics(limit="10")  # mypy error

# FIX: Use correct type
topics = get_topics(limit=10)
```

### 3. Potential None Access
```python
# ERROR: Item "None" of "Optional[TopicNode]" has no attribute "__getitem__"
topic = get_topic_by_id('eurusd')
name = topic['name']  # mypy error - topic could be None

# FIX: Handle None case
topic = get_topic_by_id('eurusd')
if topic:
    name = topic['name']
else:
    name = "Unknown"
```

## Integration with SAGA Principles

### 1. Fail Fast, Fail Loud
- Type errors caught at development time, not runtime
- No silent failures from wrong assumptions about data structure
- Clear error messages with specific locations

### 2. Explicit Data Flows
- Function signatures show exactly what goes in and comes out
- No hidden state in type annotations
- Clear ownership of data transformations

### 3. Minimalism
- Type annotations document intent without extra complexity
- Typed methods replace ad-hoc query patterns
- Single source of truth for data structures

## Migration Guide

### Phase 1: Core Infrastructure (✅ Complete)
- ✅ `graph_db/` modules fully typed
- ✅ `db_driver.py` with typed methods
- ✅ Base type definitions in `types.py`

### Phase 2: LLM Helpers (Next)
- Add return type annotations to all `*_llm.py` functions
- Use tuple returns instead of dicts where possible
- Ensure JSON parsing has typed outputs

### Phase 3: Entry Points
- Type `main.py` and major scripts
- Add type annotations to orchestration functions
- Ensure error handling is typed

### Phase 4: Utilities and Backfills
- Add types to utility functions
- Type backfill scripts
- Complete test coverage with types

## Tools and Commands

### Available Commands
```bash
make help              # Show all commands
make typecheck         # Run type checking
make typecheck-strict  # Maximum strictness
make format           # Format code
make lint             # Run linting
make pre-commit       # All pre-commit hooks
make clean            # Clean cache files
```

### VS Code Integration
Add to `.vscode/settings.json`:
```json
{
    "python.linting.mypyEnabled": true,
    "python.linting.enabled": true,
    "python.linting.mypyArgs": ["--config-file", "mypy.ini"]
}
```

### PyCharm Integration
1. Go to Settings → Tools → External Tools
2. Add MyPy tool pointing to `scripts/typecheck.py`
3. Enable type checking inspections

## Benefits Achieved

### 1. **Developer Experience**
- 🎯 **Autocomplete** - IDE knows exact structure of all data
- 🔍 **Error Detection** - Catch mistakes before running code  
- 📚 **Self-Documentation** - Types explain what functions do

### 2. **Code Quality**
- 🛡️ **Runtime Safety** - Fewer crashes from type mismatches
- 🔄 **Refactoring Confidence** - Types ensure changes don't break contracts
- 🎨 **Consistency** - Standardized patterns across codebase

### 3. **Team Collaboration**
- 📝 **Clear Interfaces** - Function signatures are contracts
- 🤝 **Easier Onboarding** - New developers understand data flow
- 🔒 **Maintainability** - Changes have predictable effects

The strict typing system transforms SAGA Graph from a dynamic Python codebase into a robust, predictable system that fails fast and provides clear feedback to developers.