"""
Writer - Graph Strategy

MISSION: Get ALL material needed to write world-class analysis.

COMPREHENSIVE GRAPH EXPLORATION:
1. Get BEST articles for this section (tier 3, smart selection)
2. Get ALL existing analysis sections (for context & consistency)
3. Get related topic analyses (for synthesis)
4. Get cross-topic drivers (for depth)
5. Format for maximum insight density

SMART ARTICLE SELECTION:
- Timeframe sections (fundamental/medium/current): ALL tier 3+2 articles (importance >= 2) for that timeframe, max 15
- Synthesis sections (drivers/executive_summary): 5 articles each from fundamental/medium/current (15 total)
- Perspective sections (risk/opportunity/trend/catalyst): ALL tier 3+2 articles (perspective score >= 2), max 15
"""

from typing import Dict, List
from src.graph.neo4j_client import run_cypher


def explore_graph(topic_id: str, section: str) -> Dict:
    """
    Get COMPREHENSIVE material for writing analysis.
    
    Returns:
        {
            "topic_name": str,
            "topic_id": str,
            "articles": List[dict],  # Smart-selected tier 3 articles
            "existing_analysis": dict,  # ALL sections for context
            "related_topics": List[dict],  # Related topic analyses
            "cross_topic_drivers": List[dict]  # Driver articles from other topics
        }
    """
    
    # Section type detection
    TIMEFRAME_SECTIONS = ["fundamental", "medium", "current"]
    SYNTHESIS_SECTIONS = ["drivers", "movers_scenarios", "swing_trade_or_outlook", "executive_summary"]
    PERSPECTIVE_SECTIONS = ["risk_analysis", "opportunity_analysis", "trend_analysis", "catalyst_analysis"]
    
    # STEP 1: Get articles with SMART SELECTION based on section type
    if section in TIMEFRAME_SECTIONS:
        # Timeframe sections: ALL tier 3 + tier 2 articles (max 4+3 per perspective = 28 total)
        # Use timeframe AND perspective filters, limit to 15 for safety
        articles_query = """
        MATCH (t:Topic {id: $topic_id})
        OPTIONAL MATCH (art:Article)-[r:ABOUT]->(t)
        WHERE r.timeframe = $section
          AND (
            coalesce(r.importance_risk, 0) >= 2 OR 
            coalesce(r.importance_opportunity, 0) >= 2 OR 
            coalesce(r.importance_trend, 0) >= 2 OR 
            coalesce(r.importance_catalyst, 0) >= 2
          )
        WITH t, art, r,
             CASE 
               WHEN coalesce(r.importance_risk, 0) >= coalesce(r.importance_opportunity, 0) 
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_risk, 0)
               WHEN coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_opportunity, 0)
               WHEN coalesce(r.importance_trend, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_trend, 0)
               ELSE coalesce(r.importance_catalyst, 0)
             END as overall_importance
        ORDER BY overall_importance DESC, art.published_at DESC
        LIMIT 15
        WITH t, collect({
            id: art.id,
            summary: art.summary,
            full_summary: art.argos_summary,
            source: art.source,
            published_at: art.published_at,
            motivation: r.motivation,
            implications: r.implications,
            risk: r.importance_risk,
            opportunity: r.importance_opportunity,
            trend: r.importance_trend,
            catalyst: r.importance_catalyst
        }) as articles
        
        // Get related topics for synthesis
        OPTIONAL MATCH (t)-[rel:RELATED_TO|DRIVES|DRIVEN_BY]-(related:Topic)
        WITH t, articles, collect(DISTINCT {
            id: related.id,
            name: related.name,
            relationship: type(rel),
            fundamental: related.fundamental_analysis,
            medium: related.medium_analysis,
            current: related.current_analysis
        }) as related_topics
        
        RETURN 
            t.name as topic_name,
            t.id as topic_id,
            articles,
            related_topics,
            {
                fundamental: t.fundamental_analysis,
                medium: t.medium_analysis,
                current: t.current_analysis,
                drivers: t.drivers,
                executive_summary: t.executive_summary,
                risk_analysis: t.risk_analysis,
                opportunity_analysis: t.opportunity_analysis,
                trend_analysis: t.trend_analysis,
                catalyst_analysis: t.catalyst_analysis
            } as existing_analysis
        """
        params = {"topic_id": topic_id, "section": section}
        
    elif section in PERSPECTIVE_SECTIONS:
        # Perspective sections: 10 articles with perspective score >= 2
        perspective_map = {
            "risk_analysis": "importance_risk",
            "opportunity_analysis": "importance_opportunity",
            "trend_analysis": "importance_trend",
            "catalyst_analysis": "importance_catalyst"
        }
        perspective_field = perspective_map.get(section, "importance_risk")
        
        articles_query = f"""
        MATCH (t:Topic {{id: $topic_id}})
        OPTIONAL MATCH (art:Article)-[r:ABOUT]->(t)
        WHERE coalesce(r.{perspective_field}, 0) >= 2
        WITH t, art, r,
             coalesce(r.{perspective_field}, 0) as perspective_score,
             CASE 
               WHEN coalesce(r.importance_risk, 0) >= coalesce(r.importance_opportunity, 0) 
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_risk, 0)
               WHEN coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_opportunity, 0)
               WHEN coalesce(r.importance_trend, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_trend, 0)
               ELSE coalesce(r.importance_catalyst, 0)
             END as overall_importance
        ORDER BY perspective_score DESC, overall_importance DESC, art.published_at DESC
        LIMIT 10
        WITH t, collect({
            id: art.id,
            summary: art.summary,
            full_summary: art.argos_summary,
            source: art.source,
            published_at: art.published_at,
            motivation: r.motivation,
            implications: r.implications,
            risk: r.importance_risk,
            opportunity: r.importance_opportunity,
            trend: r.importance_trend,
            catalyst: r.importance_catalyst,
            perspective_score: perspective_score
        }) as articles
        
        // Get related topics
        OPTIONAL MATCH (t)-[rel:RELATED_TO|DRIVES|DRIVEN_BY]-(related:Topic)
        WITH t, articles, collect(DISTINCT {{
            id: related.id,
            name: related.name,
            relationship: type(rel),
            {section}: related.{section}
        }}) as related_topics
        
        RETURN 
            t.name as topic_name,
            t.id as topic_id,
            articles,
            related_topics,
            {{
                fundamental: t.fundamental_analysis,
                medium: t.medium_analysis,
                current: t.current_analysis,
                drivers: t.drivers,
                executive_summary: t.executive_summary,
                risk_analysis: t.risk_analysis,
                opportunity_analysis: t.opportunity_analysis,
                trend_analysis: t.trend_analysis,
                catalyst_analysis: t.catalyst_analysis
            }} as existing_analysis
        """
        params = {"topic_id": topic_id}
        
    else:
        # Synthesis sections: 5 articles each from fundamental/medium/current (15 total)
        articles_query = """
        MATCH (t:Topic {id: $topic_id})
        
        // Get 5 best from each timeframe
        OPTIONAL MATCH (art:Article)-[r:ABOUT]->(t)
        WHERE r.timeframe IN ['fundamental', 'medium', 'current']
        WITH t, art, r,
             CASE 
               WHEN coalesce(r.importance_risk, 0) >= coalesce(r.importance_opportunity, 0) 
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_risk, 0)
               WHEN coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_trend, 0)
                    AND coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_opportunity, 0)
               WHEN coalesce(r.importance_trend, 0) >= coalesce(r.importance_catalyst, 0)
               THEN coalesce(r.importance_trend, 0)
               ELSE coalesce(r.importance_catalyst, 0)
             END as overall_importance
        ORDER BY r.timeframe, overall_importance DESC, art.published_at DESC
        WITH t, r.timeframe as timeframe, collect(art)[0..5] as timeframe_articles
        WITH t, collect({timeframe: timeframe, articles: timeframe_articles}) as grouped
        
        // Flatten articles from all timeframes
        UNWIND grouped as group
        UNWIND group.articles as art
        MATCH (art)-[r:ABOUT]->(t)
        WITH t, collect({
            id: art.id,
            summary: art.summary,
            full_summary: art.argos_summary,
            source: art.source,
            published_at: art.published_at,
            motivation: r.motivation,
            implications: r.implications,
            risk: r.importance_risk,
            opportunity: r.importance_opportunity,
            trend: r.importance_trend,
            catalyst: r.importance_catalyst,
            timeframe: r.timeframe
        }) as articles
        
        // Get related topics for synthesis
        OPTIONAL MATCH (t)-[rel:RELATED_TO|DRIVES|DRIVEN_BY]-(related:Topic)
        WITH t, articles, collect(DISTINCT {
            id: related.id,
            name: related.name,
            relationship: type(rel),
            fundamental: related.fundamental_analysis,
            medium: related.medium_analysis,
            current: related.current_analysis,
            drivers: related.drivers
        }) as related_topics
        
        RETURN 
            t.name as topic_name,
            t.id as topic_id,
            articles,
            related_topics,
            {
                fundamental: t.fundamental_analysis,
                medium: t.medium_analysis,
                current: t.current_analysis,
                drivers: t.drivers,
                executive_summary: t.executive_summary,
                risk_analysis: t.risk_analysis,
                opportunity_analysis: t.opportunity_analysis,
                trend_analysis: t.trend_analysis,
                catalyst_analysis: t.catalyst_analysis
            } as existing_analysis
        """
        params = {"topic_id": topic_id}
    
    # Execute query
    result = run_cypher(articles_query, params)
    
    if not result:
        return {
            "topic_name": topic_id,
            "topic_id": topic_id,
            "articles": [],
            "existing_analysis": {},
            "related_topics": []
        }
    
    data = result[0]
    
    # Filter out None articles
    articles = [a for a in data.get("articles", []) if a and a.get("id")]
    related_topics = [r for r in data.get("related_topics", []) if r and r.get("id")]
    
    return {
        "topic_name": data.get("topic_name", topic_id),
        "topic_id": data.get("topic_id", topic_id),
        "articles": articles,
        "existing_analysis": data.get("existing_analysis", {}),
        "related_topics": related_topics
    }
