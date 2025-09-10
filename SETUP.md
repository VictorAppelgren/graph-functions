# Saga Graph — Setup Guide

This guide gets you from zero to a working Saga Graph environment on macOS.

## Quick Start (Automated Setup)

**🚀 For the fastest setup, use our automated setup script:**

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/saga-graph.git
   cd saga-graph
   ```

2. **Configure environment variables** (add to ~/.zshrc or ~/.bash_profile):
   ```bash
   # Neo4j (required)
   export NEO4J_URI=neo4j://127.0.0.1:7687
   export NEO4J_USER=neo4j
   export NEO4J_PASSWORD=your_password
   export NEO4J_DATABASE=argosgraph

   # LLM Provider (at least one required)
   export OPENAI_API_KEY=sk-...
   # OR
   export ANTHROPIC_API_KEY=...

   # News API (optional, for news ingestion)
   export NEWS_API_KEY=your_perigon_api_key
   ```

3. **Run the automated setup:**
   ```bash
   ./setup.sh
   ```

The script will:
- ✅ Check Python 3.11+ is installed
- ✅ Create `.venv` virtual environment 
- ✅ Install all dependencies from `pyproject.toml`
- ✅ Validate all required environment variables
- ✅ Test Neo4j connectivity
- ✅ Test LLM provider connection
- ✅ Test News API (if configured)  
- ✅ Seed initial anchor nodes in the graph
- ✅ Provide next steps for running the system

**That's it!** If the setup script completes successfully, you're ready to run Saga Graph.

---

## Manual Setup (Step-by-Step)

If you prefer manual setup or need to troubleshoot, follow these detailed steps:

### 1) Prerequisites
- Python 3.11+ (we lock to 3.11.9 in `.python-version`)
- Neo4j 5.x (Desktop or Docker)
- macOS/Linux with bash/zsh terminal

Optional:
- Playwright (only if you want browser fallback scraping)

### 2) Clone and enter the project
```bash
git clone https://github.com/your-org/saga-graph.git
cd saga-graph
```

### 3) Configure environment variables
Export these in your shell profile (e.g., ~/.zshrc) or before running commands:

**Neo4j (required):**
```bash
export NEO4J_URI=neo4j://127.0.0.1:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
export NEO4J_DATABASE=argosgraph
```

**LLM Providers (at least one required):**
```bash
export OPENAI_API_KEY=sk-...
# OR/AND
export ANTHROPIC_API_KEY=...
```

**Optional configurations:**
```bash
# News API for ingestion
export NEWS_API_KEY=your_perigon_api_key

# LLM tier overrides (optional)
export ARGOS_SIMPLE_PROVIDER=openai
export ARGOS_SIMPLE_MODEL=gpt-4o-mini
# etc. - see model_config.py for full options
```

### 4) Python environment and dependencies
Create an isolated environment and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel setuptools
pip install -e .
```

For development dependencies (type checking, pre-commit):
```bash
pip install -e ".[dev]"
```

For optional browser scraping:
```bash
pip install -e ".[browser]"
```

### 5) Neo4j database setup
Ensure Neo4j is running locally and accessible via NEO4J_URI.

**Quick connectivity check:**
```bash
python -c "
from graph_db.db_driver import run_cypher
print('Neo4j connection:', run_cypher('RETURN 1 AS ok'))
"
```
Expected: `[{'ok': 1}]`

### 6) LLM and News API verification
**LLM check:**
```bash
python -c "
from model_config import get_simple_llm
llm = get_simple_llm()
print('LLM response:', llm.invoke('ping'))
"
```

**News API check:**
```bash
python -m perigon.news_api_client
```

### 7) Seed anchor nodes (one-time)
```bash
python user_anchor_nodes.py
```

---

## Testing Your Installation

After setup (automated or manual), test your installation:

### 1) Test with a sample report
```bash
source .venv/bin/activate
python Reports/export_asset_analysis_pdf.py
```
This should create a PDF report under `Reports/PDFs/`

### 2) Test news ingestion (if NEWS_API_KEY is set)
```bash
python perigon/run.py
```

### 3) Run the main system loop
```bash
python main.py
```
**Note:** This runs continuously - use Ctrl+C to stop.

---

## Package Management

### Modern Python Packaging
All dependencies are now managed through `pyproject.toml` for clean, modern Python packaging:

**Core dependencies:**
- Neo4j and LangChain dependencies
- HTTP clients (requests, httpx)  
- Content extraction (trafilatura)
- PDF generation (fpdf2)

**Installation options:**
```bash
pip install -e .              # Core dependencies only
pip install -e ".[dev]"       # + development tools (mypy, pre-commit)
pip install -e ".[browser]"   # + Playwright for browser scraping
```

### Python Version
- Locked to Python 3.11.9 (see `python-version`)
- Defined in `pyproject.toml` as `>=3.11,<3.12`

### Browser Scraping (Optional)
Browser-based scraping fallback via Playwright:
```bash
pip install -e ".[browser]"
playwright install chromium
```

The system defaults to static scraping (httpx + trafilatura).

---

## Troubleshooting

### Common Issues

**Neo4j Connection Errors:**
- Verify Neo4j server is running (`systemctl status neo4j` or Neo4j Desktop)
- Check credentials: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- Ensure database `NEO4J_DATABASE` exists or user has admin rights to create it
- Test: `neo4j-admin ping` or manual connection via Neo4j Browser

**LLM Provider Errors:**
- Verify API keys are valid and have sufficient quota
- Check network connectivity to provider endpoints
- For custom `base_url` configurations, ensure endpoint compatibility
- Test with a simple API call outside the application

**News API Issues:**
- `401/403 errors`: Check `NEWS_API_KEY` is valid and active
- Rate limiting: Perigon has usage limits per plan
- Test: `curl -H "Authorization: $NEWS_API_KEY" https://api.goperigon.com/v1/all`

**Package Installation Problems:**
- Update pip: `python -m pip install --upgrade pip`
- Clear cache: `pip cache purge`
- Check Python version: `python --version` (must be 3.11+)
- Reinstall dependencies: `pip install -e . --force-reinstall`

**Content Extraction Issues:**
- Trafilatura returns empty: Page may be JS-heavy or blocked
- Solution: Install Playwright fallback (see Package Management section)
- Alternative: Check if target sites require specific user-agents or headers

### Log Files
- Master logs: `master_logs/`
- Component logs: `logs/`
- Daily stats: `master_stats/statistics_YYYY_MM_DD.json`
- Problems tracked under `master_stats/.../problems[]`

### Getting Help
- Check logs for detailed error messages with ISO 8601 timestamps
- Review `config.py` for configuration options
- See SAGA_V3 principles in `README.md` for architecture guidance
