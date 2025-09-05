# Saga Graph — Minimal Setup Guide

This guide gets you from zero to a working Saga Graph environment on macOS.

## 1) Prerequisites
- Python 3.11–3.13 (recommended: 3.13)
- Neo4j 5.x (Desktop or Docker)
- macOS zsh terminal

Optional:
- Playwright (only if you want browser fallback scraping)

## 2) Clone and enter the project
```
git clone https://github.com/your-org/saga-graph.git
cd saga-graph/V1
```

## 3) Configure environment variables
Export these in your shell profile (e.g., ~/.zshrc) or before running commands:

- Neo4j
  - NEO4J_URI=neo4j://127.0.0.1:7687
  - NEO4J_USER=neo4j
  - NEO4J_PASSWORD=your_password
  - NEO4J_DATABASE=argosgraph

- LLM Providers (set the ones you use)
  - OPENAI_API_KEY=sk-...
  - ANTHROPIC_API_KEY=... (if using Anthropic)
  - OLLAMA: configure base URL per your local setup if used
  - Tier overrides (optional): ARGOS_SIMPLE_*, ARGOS_MEDIUM_*, ARGOS_COMPLEX_* (keys: provider, model, temperature, base_url) per `model_config.py`

- News API
  - NEWS_API_KEY=your_perigon_api_key

## 4) Python environment and dependencies
Create an isolated environment and install requirements:
```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel setuptools
pip install -r requirements.txt
```

If you do not yet have a pinned requirements.txt, see section 7 to generate one.

## 5) Neo4j database setup
Ensure Neo4j is running locally and accessible via NEO4J_URI.
- The helper in `graph_db/db_driver.py` will:
  - Connect to Neo4j
  - Create `NEO4J_DATABASE` if missing (requires admin)
  - Poll until the database is online

Quick connectivity check:
```
python - <<'PY'
from graph_db.db_driver import run_cypher
print(run_cypher('RETURN 1 AS ok'))
PY
```
Expected: a list with a dict containing ok: 1

## 6) Quick LLM and News client checks
- LLM check (OpenAI-compatible endpoint):
```
python - <<'PY'
from model_config import get_simple_llm
llm = get_simple_llm()
print(llm.invoke('ping'))
PY
```

- Perigon News API check:
```
python -m perigon.news_api_client
```
This runs a small demo search (see `perigon/news_api_client.py`).

## 7) Generate a pinned requirements.txt (recommended)
Use this to capture exact, reproducible versions (works with Python 3.13):
```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel setuptools
# Install curated top-level dependencies
pip install \
  neo4j \
  langchain langchain-core langchain-openai langchain-anthropic langchain-ollama \
  requests httpx trafilatura fpdf2
# Freeze full lock
pip freeze > requirements.txt
```
Note: Playwright is optional. If you want browser scraping fallback, also:
```
pip install playwright
playwright install chromium
```
The code defaults to static (httpx + trafilatura) scraping.

## Quickstart (10 min)

Follow these minimal steps to get a working graph with anchor nodes.

1) Activate env and install deps
   - See §4 for the exact commands.

2) Export environment variables
   - See §3 for the list. At minimum set Neo4j and one LLM provider.

3) Verify Neo4j connectivity
   - See §5 quick connectivity check.

4) Seed anchor nodes (one-time)
   - Run from project root `V1/`:
   ```
   python user_anchor_nodes.py
   ```
   - This MERGEs the permanent anchors and creates explicit typed relationships.
   - Note: `main.py` will also seed anchors automatically if none exist.

5) (Optional) Export a sample report PDF
   ```
   python Reports/export_asset_analysis_pdf.py
   ```
   - Outputs under `Reports/PDFs/`.

## 8) Run a minimal ingestion
A safe test is to export a report PDF (does not require a long-running loop):
```
python Reports/export_asset_analysis_pdf.py
```
Output should be created under `Reports/PDFs/`.

For a fuller ingestion, refer to `perigon/news_ingestion_orchestrator.py` and the main loop in `main.py`. Be aware `main.py` is a continuous loop and assumes operational scheduling.

## 9) Logs and stats
- Minimal logger used throughout (`utils/minimal_logging.py`) with ISO 8601 timestamps
- Master logs in `master_logs/` and per-module in `logs/`
- Problems must be tracked only under `master_stats/<day>.json` → `problems` (per SAGA_V3 conventions)

## 10) Optional: Playwright browser scraping
The static path is default and recommended. To enable fallback browser scraping:
```
pip install playwright
playwright install chromium
```
Integrate import in your scraper if needed (see `perigon/source_scraper.py`).

## 11) Troubleshooting
- Neo4j connection errors: confirm credentials and NEO4J_URI; ensure DB is online
- LLM errors: verify API keys; if using a custom base_url, confirm endpoint compatibility
- Perigon 401/403: check NEWS_API_KEY
- Trafilatura extraction empty: page may be heavy/JS-rendered; consider Playwright fallback

That’s it. You should now be able to connect to Neo4j, call the LLM, query news, and generate PDFs.
