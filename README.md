# SAGA_V3: Single-source Architecture & Guidelines for Saga Graph

---

## 1. Core Principles (God-Tier Minimalism)

- Simplicity First
  - Do the absolute minimum. No extra layers, no abstractions unless strictly necessary.
  - One function does one thing. Names say exactly what it does.

- Fail Fast, Fail Loud
  - Direct indexing for required fields. Never use `.get()` for required keys.
  - No try/except in LLM helpers. Elsewhere, use try/except only at hard I/O boundaries, log error immediately, then re-raise or continue the outer loop.

- Stateless By Design
  - Functions accept IDs-only (e.g., `topic_id`, `article_id`). Load context internally using utils/graph helpers.
  - No hidden state or in-memory counters. All dynamic parameters live on nodes in the graph.

- LLM-First, JSON-First
  - All classification/mapping/rewriting is done via LLMs.
  - Use LangChain 3-part chains: PromptTemplate -> Chat LLM -> OutputParser.
  - JSON output via `JsonOutputParser` for almost all helpers; only use `StrOutputParser` when truly necessary.

- Absolute Imports Everywhere
  - Use the canonical `sys.path` bootstrapping in every script/test (see § 3a).
  - No relative imports `..`.

- Log Everything That Matters
  - Master log: one line per major event (ISO 8601 timestamps).
  - Master stats: daily JSON counters; problems tracked only under `problems`.
  - Tracker: one JSON per major event under `tracker/<event_type>/...`.

- Explicit Dataflows & Ownership
  - Each step’s inputs and outputs are explicit. Ownership is by action filename.
  - Log every major action, decision, and error with timestamps and stable IDs.

- Configurable, Not Hard-Coded
  - Paths, credentials, and schedules live in `config.py` or environment variables.

- Lean Graph, Rich Cold Storage
  - Graph stores metadata, analysis strings, and relationships only.
  - Full article texts and raw payloads live under `data/` and/or vector DB for dedupe.

- Nothing Extra
  - If it’s not strictly required, don’t add it. Simplicity is a hard constraint.

---

## 2. Function & Process Rules

- Minimal Inputs
  - IDs-only. Example: `select_best_articles(topic_id: str, timeframe: str) -> list[dict]` reads `top_n` from the topic node.

- Zero Hidden State
  - No dynamic config in code. Read all dynamic values from the graph.

- No Orchestrators Unless Descriptive and Thin
  - It’s acceptable if a module name includes the word “orchestrator” only when descriptive (e.g., `news_ingestion_orchestrator.py`).
  - Prefer composing standalone, stateless functions from entry scripts rather than building pipelines.

- Returns: Tuples, Not Dicts
  - Multiple values returned as tuples. Callers unpack: `x, y, z = fn(...)`.

---

## 3. Absolute Imports (Canonical Pattern)

- Place this at the top of every entry script/test before any internal import:

```python
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```

- Guarantees absolute imports like `from graph_nodes.add_node import add_node` work from any CWD.

---

## 4. LLM Helper Standard (Strict)

- Naming
  - File and function both end with `_llm`. Example: `identify_article_timeframe_llm/identify_article_timeframe_llm.py`.

- Inputs
  - IDs-only (+ minimal scalars if absolutely necessary). All other context loaded internally.

- Prompt Assembly
  - Always import `SYSTEM_MISSION` and `SYSTEM_CONTEXT` within the helper (do not pass them around).
  - Use `PromptTemplate` (no f-strings).

- Chain Structure
  - `PromptTemplate | ChatLLM | JsonOutputParser` (or `StrOutputParser` if truly free-form).

- Output
  - Expect valid JSON. Prompt must make invalid output impossible.
  - Return multiple values as a tuple.

- Exceptions
  - LLM helpers: 0% try/except allowed.
  - Boundary loops outside helpers may catch, log (problem), then continue.

- Example Skeleton

```python
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from model_config import get_simple_llm
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT

# IDs-only inputs
def identify_article_timeframe_llm(article_id: str, topic_id: str) -> tuple[str, float]:
    prompt = PromptTemplate.from_template(
        """
        {system_mission}
        {system_context}
        STRICT JSON ONLY: {"timeframe":"fundamental|medium|current","confidence":0..1}
        ARTICLE_ID: {article_id}
        TOPIC_ID: {topic_id}
        """
    )
    llm = get_simple_llm()
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    out = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "article_id": article_id,
        "topic_id": topic_id,
    })

    timeframe = out["timeframe"]
    confidence = out["confidence"]
    return timeframe, confidence
```

---

## 5. Logging & Stats Policy (Minimal & Central)

- Master Log (append-only, human-scannable)
  - Format: `ISO8601 | Action | Asset/Topic | Details`
  - ISO 8601 example: `2025-08-29T16:25:57+02:00`
  - Examples:
    - `2025-08-09T04:50:09+00:00 | Saved analysis | eurusd | Saved fundamental_analysis length=3498`
    - `2025-08-09T05:01:43+00:00 | Retrieved articles | gold | Retrieved 10 from API`

- Master Stats (daily file: `master_stats/statistics_YYYY_MM_DD.json`)
  - Update counters for today; store graph snapshot; problems only in `problems`.
  - Problem log function (spec only):
    - Location: `utils/master_stats.py`
    - Signature: `problem_log(component: str, action: str, error_code: str, message: str, topic_id: str|None=None, article_id: str|None=None)`
    - Behavior: load today’s stats, append to `problems[]`, fsync; if missing → raise immediately (fail fast).

- Tracker (one JSON per major event)
  - Path: `tracker/<event_type>/<id>.json`
  - Minimal schema: `{timestamp, event_type, component, action, ids:{topic_id?, article_id?}, details, processed:false}`
  - Save all LLM outputs inline under `details` (no separate artifacts).

---

## 6. Events We Track (Initial Set)

- Ingestion
  - `ingestion_query_started`, `ingestion_query_completed`, `ingestion_query_zero_results`
  - `article_fetched`, `article_fetch_failed`
  - `raw_saved`, `raw_deduplicated`, `raw_load_failed`

- Graph Ops
  - `topic_added`, `topic_removed`
  - `article_added`, `article_removed`
  - `link_about_added`, `link_about_removed`
  - `relationship_influence_added`, `relationship_correlation_added`, `relationship_removed`

- LLM
  - `llm_call`, `llm_output_json_valid`, `llm_output_json_invalid`

- Analysis
  - `should_rewrite_true`, `should_rewrite_false`
  - `rewrite_saved`, `rewrite_skipped_0_articles`
  - `best_articles_selected`, `drivers_aggregated`, `report_aggregated`

- Quality/Policy
  - `duplicates_skipped`, `topic_replacements_decided`

- Meta
  - `stats_rollover_started`, `stats_rollover_completed`

---

## 7. Directory & File Naming Policy (Action-Focused)

- Directories are action-specific when practical; each action has its own directory.
- Files inside mirror the action name. LLM helpers suffix `_llm`.
- LLM helpers live next to their action (no central `llm_helpers/`).
- It is OK if `perigon/` retains `news_ingestion_orchestrator.py` since it’s descriptive; prefer thin composition via simple functions.

### Examples
- `add_article/add_article.py`
- `identify_article_timeframe_llm/identify_article_timeframe_llm.py`
- `add_relationship/add_relationship.py`
- `aggregate_reports/aggregate_reports.py`

### 7a. How to Enter the Process (Entrypoints)

- **Primary loop**
  - File: `main.py`
  - Purpose: Continuous maintenance loop. Schedules ingestion, mapping/linking, rewriting, and aggregation.
  - Requires: a running Neo4j server and valid API keys.

- **News ingestion (on-demand)**
  - File: `perigon/run.py`
  - Purpose: Pull fresh articles via API/scraping and save to raw storage.

- **Reports (ad hoc)**
  - File: `Reports/export_asset_analysis_pdf.py`
  - Purpose: Export PDFs for topics to validate aggregated analyses.

- **Backfills & utilities**
  - Directory: `backfill_scripts/` — `link_orphan_articles.py`, `backfill_topic_importance.py`, `count_topics_by_importance.py`.
  - Purpose: Historical hygiene and counters.

- **Tests (quick checks)**
  - Directory: `tests/` — e.g., `test_add_node.py`, `test_add_article.py`, `test_add_relationship.py`.

### 7b. Functional Areas (What Each Part Does)

- **Topics (add/remove/classify/gate)**
  - Core: add topic, remove topic, create topic query.
  - LLM: classify category, classify priority, gate topic relevance, propose new topic.
  - Policy: decide topic priority.
  - See § 8 mapping for proposed action directories/names.

- **Articles (add/link/identify/validate)**
  - Core: add article, link article to topic.
  - LLM: identify categories, timeframe; evaluate priority; map to topics; validate article-topic relevance.
  - Utilities: keep action-specific helpers close to their action directories.

- **Relationships (topic↔topic)**
  - Core: add influence/correlation links, remove links, list existing links.
  - LLM: find candidate links, select one new link, select link to remove, filter interesting targets.

- **Analysis (format/select/rewrite/aggregate/save)**
  - Build inputs, decide rewrite, select best articles, rewrite with LLM, save results, aggregate drivers and reports.

- **Ingestion (Perigon)**
  - API queries, scraping, raw storage, summarization; thin orchestration in `perigon/`.

- **Utilities**
  - Logging, master stats, text formatting, loaders, timers.

---

## 8. Full System Mapping (Current → Proposed Names)

Note: This is a proposal. No renames are executed by this document.

All modules whose directory starts with `func_` are single-action functions that operate on the graph DB or the pipeline. They are designed to be stateless, take IDs-only as inputs, and follow the SAGA_V3 rules (JSON-first for `_llm` helpers, tuple returns, direct indexing, etc.).

### func_add_topic/
- add_node.py → add_topic/add_topic.py
  - Adds a `:Topic` node with required properties and default operational fields; idempotent safeguards.
- create_query_llm.py → create_topic_query_llm/create_topic_query_llm.py
  - LLM to synthesize a topic’s canonical query specification (JSON-first output).
- priority_policy.py → decide_topic_priority/decide_topic_priority.py
  - Deterministic policy (non-LLM) to set/adjust topic priority.
- propose_new_topic_node.py → propose_new_topic_llm/propose_new_topic_llm.py
  - LLM proposes a new topic candidate with evidence and initial metadata.
- topic_category_classifier.py → classify_topic_category_llm/classify_topic_category_llm.py
  - LLM classification of a topic’s category.
- topic_priority_classifier.py → classify_topic_priority_llm/classify_topic_priority_llm.py
  - LLM classification of a topic’s priority class.
- topic_relevance_gate.py → gate_topic_relevance_llm/gate_topic_relevance_llm.py
  - LLM relevance/gating for topic activation.

### func_remove_topic/
- remove_node.py → remove_topic/remove_topic.py
  - Removes a `:Topic` and associated edges safely.

### func_add_article/
- add_article.py → add_article/add_article.py
  - Creates `:Article` nodes with normalized fields.
- link_article.py → link_article_to_topic/link_article_to_topic.py
  - Creates `(:Article)-[:ABOUT]->(:Topic)` idempotently.
- category_identifier.py → identify_article_categories_llm/identify_article_categories_llm.py
  - LLM-based article category identification.
- time_frame_identifier.py → identify_article_timeframe_llm/identify_article_timeframe_llm.py
  - LLM-based temporal horizon classification.
- impact_identifier.py → evaluate_article_priority_llm/evaluate_article_priority_llm.py
  - LLM-based priority/impact assessment.
- node_identifier.py → map_article_to_topics_llm/map_article_to_topics_llm.py
  - LLM mapping of article to candidate topics.
- topic_relevance_validator.py → validate_article_topic_relevance_llm/validate_article_topic_relevance_llm.py
  - LLM validation of article-topic pair relevance.

### func_add_relationships/
- add_link.py → add_relationship/add_relationship.py
  - Creates or updates inter-topic relationships (`INFLUENCES`, `CORRELATES_WITH`, `PEERS`) with idempotent safeguards.
- get_existing_links.py → get_existing_links/get_existing_links.py
  - Lists existing topic↔topic edges for a given topic.
- find_relationships.py → find_relationships_llm/find_relationships_llm.py
  - LLM discovers candidate inter-topic relationships.
- llm_select_one_new_link.py → select_one_new_relationship_llm/select_one_new_relationship_llm.py
  - LLM picks the single best new relationship to add now.
- llm_select_link_to_remove.py → select_relationship_to_remove_llm/select_relationship_to_remove_llm.py
  - LLM selects an existing relationship to remove.
- llm_filter_all_interesting_topics.py → filter_interesting_topics_llm/filter_interesting_topics_llm.py
  - LLM filters the universe of topics to a shortlist for linking.

### func_remove_relationship/
- remove_relationship.py → remove_relationship/remove_relationship.py
  - Removes inter-topic relationships safely (handles bidirectional pairs where applicable).

### func_analysis/
- analysis_input_formatter.py → analysis_input_formatter/analysis_input_formatter.py (keep)
  - Builds normalized, LLM-ready inputs using IDs-only.
- analysis_rewriter_llm.py → analysis_rewriter_llm/analysis_rewriter_llm.py
  - LLM rewrites analysis sections (JSON-first or strongly structured string).
- analysis_rewriter.py → rewrite_analysis/rewrite_analysis.py
  - Non-LLM glue around applying rewrites.
- analysis_saver.py → save_analysis/save_analysis.py
  - Persists analysis fields onto topic nodes.
- best_articles_selector.py → select_best_articles/select_best_articles.py
  - Selects best supporting articles for a topic/timeframe.
- driver_aggregator.py → aggregate_driver_analyses/aggregate_driver_analyses.py
  - Aggregates driver-specific insights.
- report_aggregator.py → aggregate_reports/aggregate_reports.py
  - Builds final report structures per topic.
- should_rewrite_llm.py → should_rewrite_llm/should_rewrite_llm.py
  - LLM decision if a rewrite is warranted.
- should_rewrite.py → decide_should_rewrite/decide_should_rewrite.py
  - Non-LLM decision glue.
- does_article_replace_old_llm.py → does_article_replace_old_llm/does_article_replace_old_llm.py
  - LLM decides if a new article replaces an older one.
- does_article_replace_old.py → does_article_replace_old/does_article_replace_old.py
  - Non-LLM enforcement of replacement decision.

### graph_utils/
- graph_stats.py → graph_statistics/graph_statistics.py
  - Snapshot counters/reporting over the graph.
- graph_tools.py → split later into explicit actions (e.g., list_nodes/list_nodes.py, list_edges/list_edges.py) or keep if truly generic.
- remove_article_from_graph.py → article_remove_from_graph/article_remove_from_graph.py (or move under `remove_article/` later)
  - Removes article nodes (older utility; see also new remove flow under articles).
- set_article_hidden.py → set_article_hidden/set_article_hidden.py
  - Toggle article visibility flag.
- update_article_priority.py → update_article_priority/update_article_priority.py
  - Update priority scoring on articles.
- check_if_node_exists.py, create_topic_node.py, get_all_nodes.py, get_node_by_id.py, get_topic_id_by_name.py, get_topic_analysis_field.py, get_article_temporal_horizon.py (keep)
  - Generic graph helpers with explicit names.

### graph_db/
- Keep as-is (clear and minimal). Optionally rename directory to `graph/` later.

### perigon/
- Keep `perigon/` name.
- Consider adding `run_news_ingestion/run_news_ingestion.py` as a thin entry that sequences existing functions.
- `news_ingestion_orchestrator.py` may remain since descriptive; keep thin.

### backfill_scripts/
- Keep `link_orphan_articles.py`.
- Mark `backfill_topic_importance.py`, `count_topics_by_importance.py` as candidates for removal later.

### utils/
- Keep as-is; names are already minimal and clear.

---

## 9. System Overview (Single-Step Friendly)

1) Ingest → 2) Categorize/Score → 3) Map to Topics → 4) Link → 5) Rewrite → 6) Aggregate & Report.

- Single-step entry points (examples):
  - `backfill_scripts/link_orphan_articles.py`
  - `perigon/run.py` (or future `run_news_ingestion/run_news_ingestion.py`)
  - Any action directory’s core function (e.g., `add_article/add_article.py`)

---

## 10. Enforcement & Tests (Policy-Level)

- Fail-Fast
  - Direct indexing in code examples; no `.get(...)` on required fields.

- LLM Helpers
  - No `try:` blocks inside `_llm` helpers.
  - JSON-first; tests should validate JSON parse (where applicable) and tuple returns.

- Minimalism
  - No features unless strictly necessary. Prompts enforce citation requirements; no extra code added for citation processing.

---

## 11. Citations Policy

- Require inline `(ARTICLE_ID)` citations in LLM prompts whenever articles are referenced.
- No additional code to enforce; prompts must elicit the behavior.

---

## 12. Appendix

- ISO 8601 Timestamp
  - Example: `2025-08-29T16:25:57+02:00`

- Master Log Examples
  - `2025-08-09T04:50:09+00:00 | Saved analysis | eurusd | Saved fundamental_analysis length=3498`

- Tracker Event Schema (minimal)
  - `{timestamp, event_type, component, action, ids:{topic_id?, article_id?}, details, processed:false}`

- Master Stats `problems[]` Schema (minimal)
  - `{timestamp, component, action, error_code, message, topic_id?, article_id?}`

- Chain Skeleton (JSON-first)
  - See § 4 example.

---

## 13. Project Goals

- LLM-powered, real-time world macro graph for investment research and swing trading.
- Automatically ingest news, map to topics, update graph structure, and rewrite analyses.
- Modular MVP: solo-developer speed, minimal moving parts, easy iteration.
- Future-proof: scale to hundreds of topics and thousands of articles/day.

---

## 14. Idempotency & Article Processing Policy

- Vector-store flag: every ingested article carries `processed_in_graph: False` initially.
- Graph pipeline processes only when `processed_in_graph == False`.
- On completion (even if judged “irrelevant”), set `processed_in_graph=True` and optionally `graph_processed_at` timestamp.
- If any step fails, do not set the flag—enables safe retry without side effects.

---

## 15. Data Objects, Links & Constraints (Neo4j)

- Topic Node
  - Properties: `id`, `name`, `type` (e.g., `asset`, `policy`), `level` (`main`|`driver`), `parent_id` (optional)
  - Analysis fields: `fundamental_analysis`, `medium_analysis`, `current_analysis`, `implications`
  - Operational: `status` (`active`|`hidden`), `last_updated`

- Article Node
  - Properties: `id`, `title`, `summary`, `source`, `published_at`, `vector_id`, `type`
  - Classification: `temporal_horizon`, `priority` (`3`|`2`|`1`|`hidden`), `relevance_score`, `status`

- Relationships
  - `(:Topic)-[:INFLUENCES]->(:Topic)`
  - `(:Topic)-[:CORRELATES_WITH]->(:Topic)` (bidirectional pairs)
  - `(:Topic)-[:PEERS]->(:Topic)` (bidirectional pairs)
  - `(:Article)-[:ABOUT]->(:Topic)`

- Constraint: Articles link only to Topics (or their subtopics) via `ABOUT`.
  - All inter-topic structure is captured by `INFLUENCES`, `CORRELATES_WITH`, `PEERS`.

- How Relationships Are Used
  - `INFLUENCES`: find drivers of a topic.
  - `CORRELATES_WITH`: find related topics.
  - `PEERS`: find peer topics.

### 15a. Server & Connectivity (Neo4j)

- **Requirement**: A running Neo4j 5.x server.
- **Environment variables**
  - `NEO4J_URI` (e.g., `neo4j://127.0.0.1:7687`)
  - `NEO4J_USER` (e.g., `neo4j`)
  - `NEO4J_PASSWORD`
  - `NEO4J_DATABASE` (e.g., `argosgraph`)
- **Client**: Connections are created in `graph_db/db_driver.py`. Verify connectivity before long runs.

### 15b. Minimal Schema Bootstrapping (Run Once)

```cypher
// Unique IDs for core labels
CREATE CONSTRAINT topic_id_unique IF NOT EXISTS
FOR (t:Topic) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT article_id_unique IF NOT EXISTS
FOR (a:Article) REQUIRE a.id IS UNIQUE;

// Frequently filtered fields (status/time)
CREATE INDEX topic_status_idx IF NOT EXISTS
FOR (t:Topic) ON (t.status);

CREATE INDEX article_status_idx IF NOT EXISTS
FOR (a:Article) ON (a.status);

CREATE INDEX article_published_at_idx IF NOT EXISTS
FOR (a:Article) ON (a.published_at);

// Optional: relationship property indexes (if used)
CREATE INDEX influences_strength_idx IF NOT EXISTS
FOR ()-[r:INFLUENCES]-() ON (r.strength);

CREATE INDEX correlates_evidence_idx IF NOT EXISTS
FOR ()-[r:CORRELATES_WITH]-() ON (r.evidence);
```

### 15c. Database Backup & Restore

**Location**: `neo4j_backup/dump_or_load_neo_to_or_from_json.py`

Complete database backup/restore functionality for development and disaster recovery:

- **Dump**: `dump_neo_db()` exports entire graph (nodes + relationships) to timestamped JSON
- **Load**: `load_neo_db(path, wipe=True)` restores from JSON dump with optional DB clearing
- **Requirements**: APOC plugin for dynamic label/relationship creation
- **Batch Processing**: Handles large datasets via configurable batch sizes (default: 1000)
- **Safety**: Validates temporary property conflicts before import

```python
# Quick backup
from neo4j_backup.dump_or_load_neo_to_or_from_json import dump_neo_db
path = dump_neo_db()  # Creates timestamped dump in neo4j_backup/dumps/

# Restore (destructive - clears DB first)
from neo4j_backup.dump_or_load_neo_to_or_from_json import load_neo_db
load_neo_db(path, wipe=True)
```

**Use Cases**: Environment migration, development snapshots, disaster recovery, testing with clean state.

### 15d. Relationship Semantics

- `ABOUT` edges are created via `MERGE` to stay idempotent.
- `CORRELATES_WITH` and `PEERS` are modeled as bidirectional pairs; when creating/removing, affect both directions.
- To avoid duplicates, choose a canonical direction rule (e.g., order by ID in upsert helpers).

---

## 16. Example Cypher Snippets

```cypher
// Create a main topic
CREATE (eurusd:Topic {id:"eurusd", name:"EUR/USD", type:"asset", level:"main", status:"active", last_updated:datetime()});

// Link an article
MATCH (a:Article {id:"art123"}),(t:Topic {id:"eurusd"})
MERGE (a)-[:ABOUT]->(t);

// Find drivers of EURUSD
MATCH (d:Topic)-[:INFLUENCES]->(eurusd:Topic {id:"eurusd"})
RETURN d;
```

---

## 17. Logging Structure & Strict Policy (No Defaults)

```
project_root/
└── logs/
    ├── ingestion/
    ├── mapping/
    ├── analysis/
    ├── relationships/
    ├── scheduler/
    └── ...
```

- One directory per stage; one timestamped file per run.
- Log entries: timestamp, function, inputs, outputs, errors.
- Strict: No silent defaults. Fail fast and loud.

Bad (do not do this):
```python
topic_dict["query"] = query.get("query", "")
```

Good (raise immediately on invalid LLM output):
```python
topic_dict["query"] = query["query"]
```

---

## 18. Modular Event Tracking (MVP) — Deep Dive

- One JSON per event under `tracker/<event_type>/<graph_id>.json`.
- IDs anchor to graph `elementId` when available; otherwise node/property `id`.
- Single-file truth: include all LLM outputs and reasoning inline under `details` (no extra artifacts).
- Inputs are IDs-only (`source_article_id`, `topic_id`, `status`, etc.) to avoid duplication.
- `processed:false` by default for later review (LLM critic/manual).
- Events are written only with valid IDs; otherwise fail fast.

---

## 19. Self-Governing Feedback Loop (Tracker + QA)

The Tracker and the Quality Assurance (QA) critic together make Saga a self-governing and self-improving system. The design goal is full decision provenance, asynchronous oversight, and a continuous learning loop without coupling to orchestrators.

- Purpose (why it exists)
  - Auditability: every decision is captured in a single JSON file with stable IDs and full LLM outputs.
  - Correctness: an independent critic evaluates decisions with project-wide context and per-action guidance.
  - Improvement: failed decisions yield human-readable reports that drive prompt/policy refinements.

- Components (what it is)
  - Tracker (`tracker/tracker.py`)
    - One file per event under `tracker/<event_type>/<id>.json`.
    - IDs-only under `inputs` (e.g., `topic_id`, `article_id`, `start_id`, `end_id`).
    - Rich LLM content under `details` (classification, motivations, selections, candidates, etc.).
    - `processed: false` by default to enable later QA review.
    - Strict minimal schema and fail-fast validation for discoverability and consistency.
  - QA Critic (`Quality_Assurance_Team/qa_runner.py` + `Quality_Assurance_Team/qa_prompts.py`)
    - Picks a random unprocessed event; builds full context (loads nodes, articles, prior links).
    - Invokes `run_critic(...)` with a project summary and an action-specific guide.
    - Marks the event as `processed: true` to avoid re-audit by default.
    - On `fail`, writes a Markdown report to `Quality_Assurance_Team/Quality_Reports/` and increments the daily QA counters in `master_stats`.

- Lifecycle (how it works)
  1) A core action runs (e.g., add article, add node, add/remove relationship) and writes its tracker event.
  2) QA runner selects an unprocessed event and applies the critic with full project context.
  3) If `pass`: no report, event remains archived as processed.
  4) If `fail`: a clear report is generated with a motivation and a recommendation; daily QA counters are updated.
  5) Follow-up: humans or scheduled guards adjust prompts, thresholds, or policies; subsequent runs naturally produce improved events.

- Policy and guarantees
  - Idempotency: the `processed` flag prevents repeated audits of the same decision; re-running QA is as simple as creating a new event or resetting the flag intentionally.
  - Separation of concerns: operational failures are logged under `master_stats/.../problems[]`, while QA tracks semantic decision quality.
  - Non-blocking: QA is asynchronous and does not halt the pipeline; it supplies oversight and learning signals.

- Extensibility
  - New event types can be added by emitting tracker files with minimal schema compliance.
  - Per-action checks are guided by `ACTION_TYPE_GUIDE` in `qa_prompts.py`; versioning is supported via `QA_VERSION`.

---

## 20. Final Notes

- Discoverability: every function is discoverable by filename. No god modules.
- Absolute imports guaranteed with § 3 canonical pattern.
- LLMs do the “thinking”; Python is clean, explicit glue.

---

## PRIORITY FIXES:

### 1. Tracker System Enhancement (HIGH PRIORITY)
- **Goal**: Make tracker self-improving and higher quality
- **Focus**: Minimal footprint when used in other files
- **Requirements**: 
  - Reduce tracker calls to absolute minimum lines in operational code
  - Improve tracker data quality and usefulness for system learning
  - Enable better decision provenance and feedback loops

### 2. Analysis Coverage Expansion (HIGH PRIORITY) 
- **Problem**: Only 4/43 topics have complete analysis coverage
- **Root Cause**: Non-timeframe sections (drivers, movers_scenarios, swing_trade_or_outlook, executive_summary) require different triggers than timeframe sections
- **Solution**: Lower thresholds and improve analysis pipeline to write analysis for wider range of topics
- **Status**: Thresholds reduced from 5→3 articles, individual sections from 2→1 articles

## TODO: 
- **Extend LLM Router**: Evolve current simple model selection to multi-backend SQLite-based router supporting OpenAI API, vLLM HTTP servers, and local Ollama with automatic failover, load balancing, and cost-aware routing
- Add module that adds all fundamental data to each node that has data, like EURUSD, like a stock, inflation and so on
- Add a function that pulls out fundamental data points from texts, cross references with other data points.
- Fix self-improving QA Team.
