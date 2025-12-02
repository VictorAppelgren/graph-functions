"""
Analysis Agents - Test

ONE test file for everything.

Usage:
    python -m src.analysis_agents.test                    # Random topic, full pipeline
    python -m src.analysis_agents.test --topic eurusd     # Specific topic
    python -m src.analysis_agents.test --pre-only         # Pre-writing agents only
"""

# Load .env file FIRST
from utils.env_loader import load_env
load_env()

import argparse
from src.analysis_agents.orchestrator import AnalysisAgentOrchestrator
from src.analysis_agents.writer.agent import WriterAgent
from src.analysis_agents.critic.agent import CriticAgent
from src.analysis_agents.source_checker.agent import SourceCheckerAgent
from src.graph.neo4j_client import run_cypher
from src.analysis.orchestration.analysis_rewriter import SECTION_FOCUS


def get_random_topic():
    """Get random topic from Neo4j"""
    query = """
    MATCH (t:Topic)
    WHERE t.fundamental_analysis IS NOT NULL
       OR t.medium_analysis IS NOT NULL
       OR t.current_analysis IS NOT NULL
    RETURN t.id as id, t.name as name
    ORDER BY rand()
    LIMIT 1
    """
    result = run_cypher(query, {})
    if not result:
        raise ValueError("No topics found in Neo4j")
    return result[0]["id"], result[0]["name"]


def test(topic_id=None, section="fundamental", pre_only=False):
    """
    Test analysis agents.
    
    Args:
        topic_id: Topic to test (random if None)
        section: Section to test
        pre_only: Only run pre-writing agents
    """
    print("\n" + "="*80)
    print("🚀 ANALYSIS AGENTS - FULL PIPELINE TEST")
    print("="*80)
    
    # Get topic
    if not topic_id:
        print("\n🎲 Selecting random topic...")
        topic_id, topic_name = get_random_topic()
    else:
        query = "MATCH (t:Topic {id: $id}) RETURN t.name as name"
        result = run_cypher(query, {"id": topic_id})
        topic_name = result[0]["name"] if result else topic_id
    
    print(f"\n📌 Topic: {topic_name} ({topic_id})")
    print(f"📌 Section: {section}")
    print(f"📌 Mode: {'Pre-writing only' if pre_only else 'Full pipeline'}")
    
    # PRE-WRITING AGENTS
    print("\n" + "="*80)
    print("PHASE 1: PRE-WRITING AGENTS")
    print("="*80)
    
    orchestrator = AnalysisAgentOrchestrator()
    pre_results, source_registry = orchestrator.run_agents_for_section(topic_id, section)
    
    print("\n" + "="*80)
    print("📚 SOURCE REGISTRY SUMMARY")
    print("="*80)
    print(source_registry.get_summary())
    
    if pre_only:
        print("\n✅ Pre-writing agents complete!")
        return pre_results
    
    # WRITER
    print("\n" + "="*80)
    print("PHASE 2: WRITER (Initial Draft)")
    print("="*80)
    
    # Get section focus
    section_focus_text = SECTION_FOCUS.get(section, "")
    
    print(f"\n📝 Writing Section: {section.upper()}")
    if section_focus_text:
        # Show first 150 chars of section focus
        focus_preview = section_focus_text[:150].replace('\n', ' ')
        print(f"📝 Focus: {focus_preview}...")
    
    # Get material for writer
    from src.analysis_agents.writer.graph_strategy import explore_graph
    graph_data = explore_graph(topic_id, section)
    articles = graph_data.get('articles', [])
    
    print(f"\n📚 Material gathered:")
    print(f"   • Articles: {len(articles)}")
    if articles:
        print(f"   • Sample articles: {[a.get('id', 'unknown')[:30] for a in articles[:3]]}")
    print(f"   • Pre-writing guidance: {len([r for r in pre_results.values() if r])} agents")
    
    writer = WriterAgent()
    writer_output = writer.run(
        topic_id=topic_id,
        section=section,
        section_focus=section_focus_text,
        pre_writing_results=pre_results
    )
    draft = writer_output.analysis_text
    
    print(f"\n✅ Initial draft written!")
    print(f"   • Length: {len(draft)} characters")
    print(f"   • Words: ~{len(draft.split())} words")
    print(f"\n--- DRAFT PREVIEW (first 300 chars) ---")
    print(draft[:300] + "...")
    
    # CRITIC
    print("\n" + "="*80)
    print("PHASE 3: CRITIC (Quality Review)")
    print("="*80)
    
    material = f"Articles: {len(articles)} for {topic_name}"
    
    critic = CriticAgent()
    critic_output = critic.run(
        draft=draft,
        material=material,
        section_focus=section_focus_text,
        asset_name=topic_name,
        asset_id=topic_id
    )
    critic_feedback = critic_output.feedback
    
    print(f"\n✅ Critic review complete!")
    print(f"   • Feedback length: {len(critic_feedback)} characters")
    print(f"\n--- CRITIC FEEDBACK (first 400 chars) ---")
    print(critic_feedback[:400] + ("..." if len(critic_feedback) > 400 else ""))
    
    # SOURCE CHECKER
    print("\n" + "="*80)
    print("PHASE 4: SOURCE CHECKER (Fact Verification)")
    print("="*80)
    
    source_checker = SourceCheckerAgent()
    source_output = source_checker.run(
        draft=draft,
        material=material,
        section_focus=SECTION_FOCUS[section],
        critic_feedback=critic_feedback,
        asset_name=topic_name,
        asset_id=topic_id
    )
    source_feedback = source_output.feedback
    
    print(f"\n✅ Source check complete!")
    print(f"   • Feedback length: {len(source_feedback)} characters")
    print(f"\n--- SOURCE CHECK FEEDBACK (first 400 chars) ---")
    print(source_feedback[:400] + ("..." if len(source_feedback) > 400 else ""))
    
    # FINAL SUMMARY
    print("\n" + "="*80)
    print("📊 PIPELINE COMPLETE - SUMMARY")
    print("="*80)
    
    print(f"\n✅ All phases executed successfully!")
    print(f"\n📈 Statistics:")
    print(f"   • Pre-writing agents: {len([r for r in pre_results.values() if r])}")
    print(f"   • Articles analyzed: {len(articles)}")
    print(f"   • Draft length: {len(draft)} chars (~{len(draft.split())} words)")
    print(f"   • Critic feedback: {len(critic_feedback)} chars")
    print(f"   • Source feedback: {len(source_feedback)} chars")
    
    print(f"\n📝 FINAL ANALYSIS:")
    print("="*80)
    print(draft)
    print("="*80)
    
    print(f"\n💡 Next steps:")
    print(f"   • Review critic feedback for improvements")
    print(f"   • Address source checker concerns")
    print(f"   • Optionally: Run final rewrite incorporating feedback")
    print(f"\n📌 Analysis NOT saved to Neo4j (test mode)\n")
    
    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "section": section,
        "pre_writing_results": pre_results,
        "draft": draft,
        "critic_feedback": critic_feedback,
        "source_feedback": source_feedback,
        "articles_count": len(articles)
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Analysis Agents")
    parser.add_argument("--topic", type=str, help="Topic ID (random if not specified)")
    parser.add_argument("--section", type=str, default="fundamental", 
                       choices=["fundamental", "medium", "current"])
    parser.add_argument("--pre-only", action="store_true", 
                       help="Only run pre-writing agents")
    
    args = parser.parse_args()
    
    try:
        test(args.topic, args.section, args.pre_only)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
