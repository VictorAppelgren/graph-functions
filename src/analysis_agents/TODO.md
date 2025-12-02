# Analysis Agents - TODO

## Post Market Data Integration

### 1. Add Market Context to All Agents
- [ ] Add `market_context` parameter to Writer agent
- [ ] Include current date + current price in Writer prompt
- [ ] Format: "TODAY: Nov 21, 2025 | EURUSD: 1.1500"

### 2. Add Article Timestamps
- [ ] Include publication date in article formatting
- [ ] Format: "Published: Jan 15, 2025" under each article
- [ ] Helps LLM distinguish old forecasts from current analysis

### 3. Time-Aware Prompts
- [ ] Add to Writer: "Reconcile all analysis with current market reality"
- [ ] Prevent treating H1 2025 events as future predictions when we're in late 2025
- [ ] Force reality check: past forecasts vs current price

### 4. Market Data in Pre-Writing Agents (Optional)
- [ ] Consider adding current price context to Synthesis/Depth/Contrarian
- [ ] May help agents understand current vs historical context
- [ ] Low priority - Writer is most critical

## Notes
- Market data already exists in `analysis_rewriter.py` - reuse that pattern
- Use `load_market_data_from_neo4j()` + `format_market_data_display()`
- Keep it simple - just date + price is enough for context
