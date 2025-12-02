"""
Analysis Agents - Graph-Powered Intelligence

Specialized agents that explore the graph to create world-class analysis.

Complete pipeline:
1. Pre-writing: Improvement, Synthesis, Contrarian, Depth
2. Writing: Writer
3. Post-writing: Critic, Source Checker

NOTE: Imports are lazy to allow .env loading before Neo4j client initialization.
"""

# Lazy imports - only import when actually used
# This allows test.py to load .env BEFORE neo4j_client is imported

__all__ = [
    "AnalysisAgentOrchestrator",
    "run_analysis_agents",
    "ImprovementAnalyzerAgent",
    "SynthesisScoutAgent",
    "ContrarianFinderAgent",
    "DepthFinderAgent",
    "WriterAgent",
    "CriticAgent",
    "SourceCheckerAgent",
]


def __getattr__(name):
    """Lazy import to avoid loading neo4j_client before .env is loaded"""
    if name == "AnalysisAgentOrchestrator":
        from src.analysis_agents.orchestrator import AnalysisAgentOrchestrator
        return AnalysisAgentOrchestrator
    elif name == "run_analysis_agents":
        from src.analysis_agents.orchestrator import run_analysis_agents
        return run_analysis_agents
    elif name == "ImprovementAnalyzerAgent":
        from src.analysis_agents.improvement_analyzer import ImprovementAnalyzerAgent
        return ImprovementAnalyzerAgent
    elif name == "SynthesisScoutAgent":
        from src.analysis_agents.synthesis_scout import SynthesisScoutAgent
        return SynthesisScoutAgent
    elif name == "ContrarianFinderAgent":
        from src.analysis_agents.contrarian_finder import ContrarianFinderAgent
        return ContrarianFinderAgent
    elif name == "DepthFinderAgent":
        from src.analysis_agents.depth_finder import DepthFinderAgent
        return DepthFinderAgent
    elif name == "WriterAgent":
        from src.analysis_agents.writer import WriterAgent
        return WriterAgent
    elif name == "CriticAgent":
        from src.analysis_agents.critic import CriticAgent
        return CriticAgent
    elif name == "SourceCheckerAgent":
        from src.analysis_agents.source_checker import SourceCheckerAgent
        return SourceCheckerAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
