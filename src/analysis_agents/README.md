# Analysis Agents - Graph-Powered Intelligence

## Vision

**World-class analysis through specialized, graph-aware agents.**

Each agent has ONE job. Each agent explores the graph differently. Combined, they create insights impossible from any single perspective.

---

## Architecture

```
analysis_agents/
├── base_agent.py                    # Abstract interface
├── orchestrator.py                  # Composes agents for each section
├── test_agents.py                   # Test pre-writing agents
├── test_full_pipeline.py            # Test complete pipeline
│
├── improvement_analyzer/            # PRE-WRITING
│   ├── agent.py                     # Compares old vs. new
│   ├── prompt.py                    # LLM instructions
│   └── graph_strategy.py            # What to extract from graph
│
├── synthesis_scout/                 # PRE-WRITING
│   ├── agent.py                     # Finds cross-topic insights
│   ├── prompt.py
│   └── graph_strategy.py            # Explores related topics
│
├── contrarian_finder/               # PRE-WRITING
│   ├── agent.py                     # Challenges consensus
│   ├── prompt.py
│   └── graph_strategy.py            # Checks contrarian assets
│
├── depth_finder/                    # PRE-WRITING
│   ├── agent.py                     # Builds causal chains
│   ├── prompt.py
│   └── graph_strategy.py            # Deep dives articles
│
├── writer/                          # WRITING
│   ├── agent.py                     # Writes initial draft
│   ├── prompt.py
│   └── graph_strategy.py            # Gets material
│
├── critic/                          # POST-WRITING
│   ├── agent.py                     # Quality feedback
│   └── prompt.py
│
└── source_checker/                  # POST-WRITING
    ├── agent.py                     # Fact checking
    └── prompt.py
```

---

## How It Works

### 1. Graph Strategy (Data)
Each agent has a **graph_strategy.py** that queries Neo4j:
- What topics to explore
- What articles to include
- What analysis sections to read

### 2. Agent (Logic)
Each agent has an **agent.py** that:
- Calls graph strategy to get data
- Formats data for LLM
- Calls LLM with specialized prompt
- Returns structured output

### 3. Prompt (Instructions)
Each agent has a **prompt.py** with:
- Clear mission statement
- Specific output format
- Examples of good output

### 4. Orchestrator (Composition)
**orchestrator.py** composes agents based on section needs:
- Fundamental: All 4 agents
- Medium: Synthesis + Contrarian + Improvement
- Current: Synthesis + Contrarian
- Drivers: Synthesis only

---

## Philosophy

**SIMPLEST POSSIBLE:**
- No unnecessary abstraction
- No complex inheritance
- No over-engineering

**GRAPH-POWERED:**
- Each agent explores graph differently
- Leverage existing analysis on related topics
- Cross-topic synthesis is the killer feature

**COMPOSABLE:**
- Each agent works independently
- Orchestrator combines them
- Easy to add/remove agents

---

## Example Output

**Synthesis Scout:**
```
"Article (ARTICLE_ID) ([RATE_OUTLOOK]) + (Topic:fed_policy.executive_summary) 
([FED_STANCE]) + (Topic:ecb_policy.executive_summary) 
([ECB_STANCE]) = Central bank divergence creates [DIRECTIONAL_IMPACT]"
```

**Contrarian Finder:**
```
"Consensus: [ASSET] strength on [CATALYST]
Our view: (Topic:dxy.executive_summary) shows [CONTRADICTING_FACTOR] - 
[OVERLOOKED_DRIVER] underestimated by consensus"
```

**Depth Finder:**
```
"Article (ARTICLE_ID_1) mentions '[VAGUE_CLAIM]' - quantify as 
[SPECIFIC_NUMBER] from Article (ARTICLE_ID_2)"
```

---

## Test

**ONE test file. That's it.**

```bash
# Full pipeline (random topic)
python -m src.analysis_agents.test

# Specific topic
python -m src.analysis_agents.test --topic eurusd

# Pre-writing agents only
python -m src.analysis_agents.test --pre-only

# Different section
python -m src.analysis_agents.test --topic gold --section medium
```

**What you'll see:**
- ✅ Each agent's sources found and selected
- ✅ Article IDs tracked through entire pipeline
- ✅ Related topics discovered
- ✅ Synthesis opportunities with citations
- ✅ Draft with full source tracking
- ✅ Critic and source checker feedback
- ✅ Complete source registry

**Note:** Agents connect to Neo4j using `.env` file in `/graph-functions/`. Already configured!
