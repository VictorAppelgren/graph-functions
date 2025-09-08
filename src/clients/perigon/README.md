# News Ingestion Pipeline

A minimal, focused pipeline for news article ingestion, scraping, and summarization. This module follows Argos Graph development principles of simplicity, explicitness, and fail-fast behavior.

## Overview

The news ingestion pipeline performs these core functions:

1. **Query Execution**: Execute search queries against news API sources
2. **Article Retrieval**: Fetch article metadata from news APIs
3. **Source Scraping**: Scrape full text from article URLs and linked sources
4. **Summarization**: Generate text summaries from article content
5. **Storage**: Store raw article data with metadata and summaries

## Directory Structure

```
news_ingestion/
├── __init__.py           - Module definition
├── config.py             - Configuration and environment setup
├── ingestion_orchestrator.py - Core pipeline orchestration
├── news_api_client.py    - News API client with error handling
├── query1.py             - EURUSD test query
├── query2.py             - AI data centers test query  
├── raw_storage_manager.py - Storage of article data
├── run.py                - Command-line pipeline runner
├── source_scraper.py     - Article and source scraper
└── text_summarizer.py    - Article content summarization
```

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set required environment variables:

```bash
export NEWS_API_KEY="your_api_key_here"
```

## Usage

### Running the Complete Pipeline

Execute the complete pipeline with default settings:

```bash
python run.py
```


### Command-line Options

- `--max-articles N`: Maximum number of articles to retrieve per query (default: 5)
- `--debug`: Enable debug mode with verbose logging

### Using the API

You can also use the pipeline programmatically:

```python
from news_ingestion.ingestion_orchestrator import NewsIngestionOrchestrator

# Initialize the orchestrator
orchestrator = NewsIngestionOrchestrator()

# Run with custom queries
results = orchestrator.run_query("EURUSD OR forex OR currency", max_results=5)

# Run the test pipeline
test_results = orchestrator.run_complete_test()
print(f"Articles processed: {test_results['statistics']['articles_stored']}")
```

## Development

### Adding New Queries

Create new query files following the pattern in `query1.py` and `query2.py`:

```python
def get_query():
    """Return the query string."""
    return "YOUR QUERY STRING HERE"
```

Then import and use them in your code:

```python
from news_ingestion import your_query_module
query = your_query_module.get_query()
```

### Environment Variables

- `NEWS_API_KEY`: API key for accessing news sources
- `LOG_LEVEL`: Optional, set to DEBUG, INFO, WARNING, etc. (default: INFO)

## Testing

Run the built-in tests:

```bash
# Run full test with sample queries
python -m news_ingestion.ingestion_orchestrator
```

## Design Principles

This module follows these key principles:

1. **Simplicity**: Focused solely on ingestion tasks
2. **Modularity**: Clean separation of concerns
3. **Explicitness**: No silent failures or hidden behavior
4. **Fail-fast**: Errors are raised, not suppressed
5. **Minimal Dependencies**: Only essential packages required
