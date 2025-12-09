# Strategy & Topic Analysis – Position‑Aware Plan

Location: `graph-functions/docs/strategy_analysis_position_plan.md`

Last updated: _2025‑12‑07 – strategy pipeline implemented; topic `analysis_agents` refactor pending_

---

## 1. Strategy analysis pipeline – current behavior (implemented)

- **Canonical `has_position` flag** is computed once in the orchestrator from `position_text` and passed into `material_builder` and all strategy agents.
- Pipeline uses the **Backend API** end‑to‑end: load strategies, run analysis, save topics + analysis + dashboard question with API key auth.
- Strategy analysis is now **8‑section, section‑centric** and mode‑aware (active position vs thesis monitoring).

### 1.1 Modes

- `has_position=True`  → **ACTIVE POSITION ANALYSIS**
  - User has provided position details.
  - Agents may talk about entries, stops, sizing, P&L, and concrete trade structures, grounded only in user input + market context.

- `has_position=False` → **THESIS MONITORING (NO ACTIVE POSITION)**
  - No live position; this is **scenario and strategic analysis**, not a trade plan.
  - All prompts forbid inventing a current trade, entry, stop, size, leverage, or realized P&L.

### 1.2 Agents & flow

1. **TopicMapperAgent**
   - Maps strategy to primary / driver / correlated topics in the graph.
   - Result is saved to the Backend API (when `save_to_backend=True`).

2. **Material builder**
   - Builds a `material_package` with:
     - `user_strategy`, `position_text`, `has_position`.
     - Topic analyses + market data for all mapped topics.
     - Combined topic‑analysis and market‑context strings used by downstream agents and logging.

3. **RiskAssessorAgent**
   - Uses the shared material package.
   - Prompt is **mode‑aware** and avoids fabricating trade‑level risks when `has_position=False` (losses/stops/P&L must be conditional/future‑oriented).

4. **OpportunityFinderAgent**
   - Uses the same material package.
   - Prompt is **mode‑aware** and avoids inventing live positions; in thesis mode it frames opportunities as conditional future setups.

5. **StrategyWriterAgent**
   - Consumes strategy text, position text, topic material, and the structured risk/opportunity outputs.
   - Writes a `StrategyAnalysis` with 8 sections:
     - `executive_summary`
     - `position_analysis`
     - `risk_analysis`
     - `opportunity_analysis`
     - `recommendation`
     - `scenarios_and_catalysts`
     - `structuring_and_risk_management`
     - `context_and_alignment`
   - Logs input and output sizes per run.

6. **Backend save + dashboard question**
   - Orchestrator saves topics and full `analysis_dict` (risk, opportunity, final analysis) via Backend API.
   - Generates a single dashboard question from the latest analysis and saves it to the backend.

### 1.3 Thesis‑monitoring mode (no position)

When `has_position=False`:

- **Executive Summary**
  - Must begin with an explicit line: there is **no active position**, and any trades are **potential future setups only**.
  - Focuses on thesis, market context, key movers/drivers, and scenario quality.

- **Overall emphasis**
  - Primary job is **scenario and strategic analysis**:
    - What is happening in the relevant markets/sector.
    - Who the key drivers are.
    - How bull/base/bear paths and catalysts could unfold.
    - What risks, indicators, and structural bottlenecks to watch.

- **Trade / exposure language**
  - Almost all content is non‑trade: markets, drivers, scenarios, risks.
  - It is allowed to briefly mention that a situation **could reward exposure** to certain assets, sectors, or styles.
  - It must **not** design a full trade plan (no detailed entries/stops/sizing or execution playbook).
  - Any mention of losses, stop‑loss hits, exposure, or P&L must be explicitly conditional and forward‑looking.

- **Position Analysis section**
  - `StrategyWriterAgent` explicitly sets `position_analysis = ""` in thesis mode so the frontend can hide this section.

### 1.4 Active‑position mode

When `has_position=True`:

- StrategyWriter and upstream agents may speak in full **trade‑plan terms**:
  - Entry vs current market, stops, sizing, time‑in‑trade, realized/expected P&L.
  - Position optimization and structuring inside risk/opportunity/structuring sections.
- All trade details must still be grounded in the user’s position text and the loaded market/topic material; prompts forbid inventing trades or arbitrary levels.

---

## 2. Topic `analysis_agents` – concise refactor plan

Topic/article analysis (in `src/analysis_agents`) already has a Writer, Critic, and SourceChecker. The goal is to align it with the same simple pattern the strategy pipeline now follows, while hardening it against hallucinations.

- **Goals**
  - Keep topic analysis **section‑centric** (e.g. `chain_reaction_map`, `structural_threats`, etc.).
  - Use pre‑writing agents once per topic/section to produce **structured signals**, not prose.
  - Have a single Writer per section, then a **Critic + SourceChecker loop** to enforce factual grounding and citation rules.

- **Key ideas**
  - Treat existing pre‑writing agents (`SynthesisScout`, `ContrarianFinder`, `DepthFinder`, etc.) as signal producers.
  - For each topic section:
    1. Build a `section_material` bundle (sources, signals, prior sections).
    2. Call the section Writer once to draft the text.
    3. Run a short **quality loop** (Critic + SourceChecker + rewrite) to fix hallucinations, missing citations, and weak reasoning.
  - Make all prompts explicit about:
    - No invented facts or article IDs.
    - Market levels and macro claims must come from source material or topic market data.

- **High‑level implementation steps (pending)**
  1. Define a small `SECTION_CONFIG` for topic sections (order, focus, which signals feed each section).
  2. Add a `run_topic_quality_loop` helper mirroring the strategy quality loop, reusing existing critic/source_checker logic.
  3. Update pre‑writing agent prompts to accept a `section_focus` so they are task‑aware but reusable.
  4. Tighten Critic + SourceChecker prompts around:
     - citation validity,
     - numerical/market‑data consistency,
     - explicit rejection of unsupported claims.

This keeps the **strategy** side implemented, stable, and mode‑aware, while leaving a clear, compact roadmap for bringing the **topic analysis agents** up to the same anti‑hallucination standard.

### 2.2 Exact change list for topic `analysis_agents`

- **`src/analysis_agents/orchestrator.py`**
  - Keep `AGENT_SECTIONS`, `SECTION_AGENT_CONFIG`, `SECTION_FOCUS`, `SECTION_DEPENDENCIES`, and the 8‑section execution order as the single source of truth.
  - Refactor `analysis_rewriter_with_agents` so that:
    - It builds a `section_material` bundle per section (topic id, section name, `section_focus`, article material, prior sections, structured `agent_results`).
    - It calls a dedicated **Writer agent** for the first draft instead of invoking the LLM inline.
    - It calls a shared **topic quality loop** (Critic + SourceChecker + rewrite) to refine the draft before saving to Neo4j.
  - Add simple logging per section: material size, agent‑context size, final analysis size, and which sections were written.

- **`src/analysis_agents/writer/agent.py`**
  - Expose a method like `run_section(topic_id, section_name, section_focus, material, agent_results) -> str`.
  - Ensure the writer prompt:
    - Clearly separates **AGENT INSIGHTS** vs **MATERIAL & CONTEXT** vs **TASK**.
    - Enforces strict 9‑character article IDs and forbids made‑up IDs.
    - States that any numeric claims (levels, flows, macro numbers) must be grounded in the provided material.
  - Log input/output sizes per section.

- **`src/analysis_agents/critic/agent.py` & `critic/prompt.py`**
  - Make `CriticAgent.run(...)` accept `section_name` / `section_focus` so feedback is section‑aware.
  - Strengthen the critic prompt to:
    - Flag hand‑wavy causal claims not supported by material.
    - Flag overconfident trade/positioning language in sections that should be structural/scenario‑oriented.
    - Require that suggested fixes reference which sources support them.
  - Optionally log a short summary per section: counts of issues (missing citations, weak causal chains, numerical inconsistencies).

- **`src/analysis_agents/source_checker/agent.py` & `source_checker/prompt.py`**
  - Ensure `SourceCheckerAgent.run(...)` also accepts `section_name` / `section_focus`.
  - Tighten the prompt so that it:
    - Rejects any article IDs not present in the input material.
    - Flags numeric market data / levels that cannot be traced to articles or topic market data.
    - Distinguishes between qualitative structural narrative (allowed) and hard numbers (must be explicitly sourced).
  - Have SourceChecker output structured feedback categories that the rewrite step can consume (e.g. `missing_citation`, `wrong_number`, `unsupported_claim`).

- **Topic quality loop helper (new)**
  - Add a helper (e.g. `run_topic_quality_loop(section_name, draft_text, section_material, topic_id) -> str`) that:
    - Calls `CriticAgent` and `SourceCheckerAgent` once per round.
    - Rewrites the draft using a small rewrite prompt (can reuse `llm/prompts/rewrite_analysis_llm.py` patterns).
    - Runs for a small fixed number of rounds (e.g. 2–3) or until critic/source feedback is “good enough”.
  - Use this helper from `analysis_rewriter_with_agents` before saving each section.

- **Pre‑writing agents** – `synthesis_scout/agent.py`, `contrarian_finder/agent.py`, `depth_finder/agent.py`
  - Ensure each pre‑writer:
    - Accepts `section` or `section_focus` (the orchestrator already passes this) and uses it to slightly tune behavior by section.
    - Returns structured outputs (Pydantic models or dicts) that the writer can consume, rather than long narrative strings.
  - Keep them as **signal producers only**; they must not attempt to write final section prose.

- **Logging & observability**
  - For each topic/section run, log:
    - Topic id and section name.
    - Number of articles and total material characters.
    - Counts of items per pre‑writing agent (e.g. number of chains, contrarian angles).
    - Counts of issues found by Critic/SourceChecker.
    - Final section length and confirmation that it was saved to Neo4j.

- **Tests** – `src/analysis_agents/test_full_pipeline.py` (or new equivalent)
  - Update the full‑pipeline test so it:
    - Runs the new section‑centric writer + quality loop on a few real topics (e.g. `eurusd`, `gold`, `fed_policy`).
    - Asserts that each section is non‑empty and within a reasonable length range.
    - Asserts that all article IDs in the generated text belong to the material set used for that run.

This extended list is the concrete, per‑file change set for bringing topic `analysis_agents` up to the same structured, anti‑hallucination standard as the strategy pipeline.
