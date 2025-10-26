"""
Strategy Analyzer - Main Orchestrator for Custom User Analysis

Generates personalized analysis for user trading strategies.
"""

import os
import sys
from datetime import datetime
from typing import Dict

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from src.custom_user_analysis.topic_discovery import discover_relevant_topics
from src.custom_user_analysis.material_collector import (
    collect_analysis_material,
    format_material_for_prompt
)
from src.custom_user_analysis.evidence_classifier import classify_evidence
from src.custom_user_analysis.prompts.fundamental_prompt import build_fundamental_prompt
from src.custom_user_analysis.prompts.current_prompt import build_current_prompt
from src.custom_user_analysis.prompts.risks_prompt import build_risks_prompt
from src.custom_user_analysis.prompts.drivers_prompt import build_drivers_prompt
from src.custom_user_analysis.prompts.executive_summary_prompt import build_executive_summary_prompt
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.observability.pipeline_logging import master_log

# Import Backend API client
from src.api.backend_client import get_strategy, update_strategy


def log_and_print(message: str):
    """Log to master log AND print to stdout for visibility."""
    master_log(message)
    print(message)


def generate_custom_user_analysis(
    username: str,
    strategy_id: str,
    test: bool = False
) -> None:
    """
    Generate custom analysis for user strategy.
    
    Flow:
    1. Load strategy from file
    2. Discover relevant topics from graph
    3. Collect analysis material
    4. Generate 4 custom sections via LLM
    5. Classify evidence
    6. Save analysis back to strategy JSON
    
    Args:
        username: User's username
        strategy_id: Strategy ID (e.g., "strategy_001")
        test: If True, use faster/cheaper models
    """
    master_log(f"Custom analysis started | {username}/{strategy_id}")
    
    try:
        # 1. Load strategy from Backend API
        strategy = get_strategy(username, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {username}/{strategy_id}")
        master_log(f"Strategy loaded | {username}/{strategy_id} | asset={strategy['asset']['primary']}")
        
        # Extract user inputs
        asset_name = strategy["asset"]["primary"]
        strategy_text = strategy["user_input"]["strategy_text"]
        position_text = strategy["user_input"]["position_text"]
        target = strategy["user_input"]["target"]
        
        # 2. Discover relevant topics
        topics = discover_relevant_topics(asset_name, strategy_text, position_text)
        master_log(f"Topics discovered | {username}/{strategy_id} | primary={len(topics['primary'])} drivers={len(topics['drivers'])} correlated={len(topics['correlated'])}")
        
        # 3. Collect analysis material
        material = collect_analysis_material(
            primary_topics=topics["primary"],
            driver_topics=topics["drivers"],
            correlated_topics=topics["correlated"]
        )
        
        # Log what material was collected
        log_and_print("="*100)
        log_and_print("="*100)
        log_and_print(f"MATERIAL COLLECTED FOR ANALYSIS")
        log_and_print(f"Strategy           : {username}/{strategy_id}")
        log_and_print(f"Asset              : {asset_name}")
        log_and_print(f"Primary topics     : {', '.join(topics['primary'])}")
        log_and_print(f"Driver topics      : {', '.join(topics['drivers'])}")
        log_and_print(f"Correlated topics  : {', '.join(topics['correlated'])}")
        log_and_print(f"Total topics       : {len(topics['primary']) + len(topics['drivers']) + len(topics['correlated'])}")
        log_and_print("="*100)
        
        # 4. Generate analysis sections
        llm = get_llm(ModelTier.COMPLEX if not test else ModelTier.FAST)
        
        # Section 1: Fundamental Analysis
        primary_material_fund = format_material_for_prompt(
            material, "primary_analysis",
            section_filter=["fundamental_analysis", "medium_analysis", "drivers", "executive_summary"]
        )
        driver_material_fund = format_material_for_prompt(
            material, "driver_analysis"
        )
        
        log_and_print("")
        log_and_print("─"*100)
        log_and_print(f"GENERATING SECTION: FUNDAMENTAL ANALYSIS")
        log_and_print(f"Asset              : {asset_name}")
        log_and_print(f"Topics used        : {len(topics['primary'])} primary + {len(topics['drivers'])} drivers")
        log_and_print(f"Sections included  : fundamental_analysis, medium_analysis, drivers, executive_summary")
        log_and_print(f"Input material     : {len(primary_material_fund):,} chars (primary) + {len(driver_material_fund):,} chars (drivers)")
        log_and_print(f"Total input        : {len(primary_material_fund) + len(driver_material_fund):,} chars")
        log_and_print("─"*100)
        
        fundamental_prompt = build_fundamental_prompt(
            asset_name=asset_name,
            strategy_text=strategy_text,
            position_text=position_text,
            target=target,
            primary_material=primary_material_fund,
            driver_material=driver_material_fund
        )
        fundamental_response = llm.invoke(fundamental_prompt)
        fundamental_analysis = fundamental_response.content if hasattr(fundamental_response, 'content') else str(fundamental_response)
        log_and_print(f"✅ Generated {len(fundamental_analysis):,} chars")
        
        # Section 2: Current Analysis
        primary_material_curr = format_material_for_prompt(
            material, "primary_analysis",
            section_filter=["current_analysis"]
        )
        driver_material_curr = format_material_for_prompt(
            material, "driver_analysis",
            section_filter=["current_analysis"]
        )
        correlated_material_curr = format_material_for_prompt(
            material, "correlated_analysis",
            section_filter=["current_analysis"]
        )
        
        log_and_print("")
        log_and_print("─"*100)
        log_and_print(f"GENERATING SECTION: CURRENT ANALYSIS (0-3 weeks)")
        log_and_print(f"Asset              : {asset_name}")
        log_and_print(f"Topics used        : {len(topics['primary'])} primary + {len(topics['drivers'])} drivers + {len(topics['correlated'])} correlated")
        log_and_print(f"Sections included  : current_analysis")
        log_and_print(f"Input material     : {len(primary_material_curr):,} chars (primary) + {len(driver_material_curr):,} chars (drivers) + {len(correlated_material_curr):,} chars (correlated)")
        log_and_print(f"Total input        : {len(primary_material_curr) + len(driver_material_curr) + len(correlated_material_curr):,} chars")
        log_and_print("─"*100)
        
        current_prompt = build_current_prompt(
            asset_name=asset_name,
            strategy_text=strategy_text,
            position_text=position_text,
            target=target,
            primary_material=primary_material_curr,
            driver_material=driver_material_curr,
            correlated_material=correlated_material_curr
        )
        
        current_response = llm.invoke(current_prompt)
        current_analysis = current_response.content if hasattr(current_response, 'content') else str(current_response)
        log_and_print(f"✅ Generated {len(current_analysis):,} chars")
        
        # Section 3: Risks Analysis
        # Use ALL sections for risks - LLM will extract contradicting evidence and risks
        primary_material_risks = format_material_for_prompt(material, "primary_analysis")
        driver_material_risks = format_material_for_prompt(material, "driver_analysis")
        correlated_material_risks = format_material_for_prompt(material, "correlated_analysis")
        
        # Limit each to avoid token overflow
        primary_material_risks_limited = primary_material_risks[:5000]
        driver_material_risks_limited = driver_material_risks[:5000]
        correlated_material_risks_limited = correlated_material_risks[:5000]
        
        total_risks_input = len(primary_material_risks_limited) + len(driver_material_risks_limited) + len(correlated_material_risks_limited)
        
        log_and_print("")
        log_and_print("─"*100)
        log_and_print(f"GENERATING SECTION: RISKS ANALYSIS")
        log_and_print(f"Asset              : {asset_name}")
        log_and_print(f"Topics used        : {len(topics['primary'])} primary + {len(topics['drivers'])} drivers + {len(topics['correlated'])} correlated")
        log_and_print(f"Sections included  : all sections (LLM extracts risks and contradicting evidence)")
        log_and_print(f"Input material     : {len(primary_material_risks_limited):,} chars (primary) + {len(driver_material_risks_limited):,} chars (drivers) + {len(correlated_material_risks_limited):,} chars (correlated)")
        log_and_print(f"Total input        : {total_risks_input:,} chars")
        log_and_print("─"*100)
        
        risks_prompt = build_risks_prompt(
            asset_name=asset_name,
            strategy_text=strategy_text,
            position_text=position_text,
            target=target,
            primary_material=primary_material_risks_limited,
            driver_material=driver_material_risks_limited,
            correlated_material=correlated_material_risks_limited
        )
        
        risks_response = llm.invoke(risks_prompt)
        risks_analysis = risks_response.content if hasattr(risks_response, 'content') else str(risks_response)
        log_and_print(f"✅ Generated {len(risks_analysis):,} chars")
        
        # Section 4: Drivers Analysis
        driver_material_drv = format_material_for_prompt(material, "driver_analysis")
        primary_material_drv = format_material_for_prompt(material, "primary_analysis", section_filter=["drivers"])
        
        log_and_print("")
        log_and_print("─"*100)
        log_and_print(f"GENERATING SECTION: DRIVERS ANALYSIS (Cross-Asset Synthesis)")
        log_and_print(f"Asset              : {asset_name}")
        log_and_print(f"Topics used        : {len(topics['primary'])} primary + {len(topics['drivers'])} drivers")
        log_and_print(f"Sections included  : drivers")
        log_and_print(f"Input material     : {len(driver_material_drv):,} chars (drivers) + {len(primary_material_drv):,} chars (primary)")
        log_and_print(f"Total input        : {len(driver_material_drv) + len(primary_material_drv):,} chars")
        log_and_print("─"*100)
        
        drivers_prompt = build_drivers_prompt(
            asset_name=asset_name,
            strategy_text=strategy_text,
            position_text=position_text,
            target=target,
            primary_material=primary_material_drv
        )
        
        drivers_response = llm.invoke(drivers_prompt)
        drivers_analysis = drivers_response.content if hasattr(drivers_response, 'content') else str(drivers_response)
        log_and_print(f"✅ Generated {len(drivers_analysis):,} chars")
        
        # Section 5: Executive Summary (synthesizes all 4 sections)
        log_and_print("")
        log_and_print("─"*100)
        log_and_print(f"GENERATING SECTION: EXECUTIVE SUMMARY (Final Synthesis)")
        log_and_print(f"Asset              : {asset_name}")
        log_and_print(f"Synthesizing       : All 4 analysis sections")
        log_and_print(f"Input material     : {len(fundamental_analysis):,} + {len(current_analysis):,} + {len(risks_analysis):,} + {len(drivers_analysis):,} chars")
        log_and_print(f"Total input        : {len(fundamental_analysis) + len(current_analysis) + len(risks_analysis) + len(drivers_analysis):,} chars")
        log_and_print(f"Target output      : 3-4 sentences (ultra-concise, actionable)")
        log_and_print("─"*100)
        
        executive_summary_prompt = build_executive_summary_prompt(
            asset_name=asset_name,
            strategy_text=strategy_text,
            position_text=position_text,
            target=target,
            fundamental_analysis=fundamental_analysis,
            current_analysis=current_analysis,
            risks_analysis=risks_analysis,
            drivers_analysis=drivers_analysis
        )
        
        executive_summary_response = llm.invoke(executive_summary_prompt)
        executive_summary = executive_summary_response.content if hasattr(executive_summary_response, 'content') else str(executive_summary_response)
        log_and_print(f"✅ Generated {len(executive_summary):,} chars")
        
        log_and_print("")
        log_and_print("="*100)
        log_and_print("="*100)
        log_and_print(f"ANALYSIS GENERATION COMPLETE")
        log_and_print(f"Strategy           : {username}/{strategy_id}")
        log_and_print(f"Asset              : {asset_name}")
        log_and_print(f"Executive Summary  : {len(executive_summary):,} chars")
        log_and_print(f"Fundamental        : {len(fundamental_analysis):,} chars")
        log_and_print(f"Current            : {len(current_analysis):,} chars")
        log_and_print(f"Risks              : {len(risks_analysis):,} chars")
        log_and_print(f"Drivers            : {len(drivers_analysis):,} chars")
        log_and_print(f"Total output       : {len(executive_summary) + len(fundamental_analysis) + len(current_analysis) + len(risks_analysis) + len(drivers_analysis):,} chars")
        log_and_print("="*100)
        
        # 5. Classify evidence (simplified - extract topic names as plain strings)
        supporting_evidence = []
        contradicting_evidence = []
        
        # Simple extraction: list all topics analyzed as plain strings
        # Format: "Topic analysis supports/contradicts thesis - brief insight"
        for topic_id in topics["primary"]:
            topic_name = material["primary_analysis"].get(topic_id, {}).get("name", topic_id)
            supporting_evidence.append(
                f"{topic_name} analysis provides core intelligence for {asset_name} performance"
            )
        
        for topic_id in topics["drivers"][:3]:  # Top 3 drivers
            topic_name = material["driver_analysis"].get(topic_id, {}).get("name", topic_id)
            supporting_evidence.append(
                f"{topic_name} identified as key macro driver affecting {asset_name}"
            )
        
        # 6. Save analysis to strategy
        all_related_topics = list(set(topics["primary"] + topics["drivers"] + topics["correlated"]))
        
        _save_analysis_to_strategy(
            username=username,
            strategy_id=strategy_id,
            analysis_results={
                "executive_summary": executive_summary.strip(),
                "fundamental": fundamental_analysis.strip(),
                "current": current_analysis.strip(),
                "risks": risks_analysis.strip(),
                "drivers": drivers_analysis.strip()
            },
            supporting_evidence=supporting_evidence,
            contradicting_evidence=contradicting_evidence,
            related_topics=all_related_topics
        )
        
        master_log(f"Custom analysis complete | {username}/{strategy_id}")
        
    except Exception as e:
        master_log(f"Custom analysis failed | {username}/{strategy_id} | error={str(e)}")
        raise


def _save_analysis_to_strategy(
    username: str,
    strategy_id: str,
    analysis_results: Dict[str, str],
    supporting_evidence: list,
    contradicting_evidence: list,
    related_topics: list
) -> None:
    """
    Update strategy JSON with generated analysis via Backend API.
    """
    # Load current strategy from Backend API
    strategy = get_strategy(username, strategy_id)
    if not strategy:
        raise ValueError(f"Strategy not found: {username}/{strategy_id}")
    
    # Update related topics
    strategy["asset"]["related"] = related_topics
    
    # Update analysis section
    strategy["analysis"] = {
        "generated_at": datetime.now().isoformat(),
        "executive_summary": analysis_results.get("executive_summary", ""),
        "fundamental": analysis_results["fundamental"],
        "current": analysis_results["current"],
        "risks": analysis_results["risks"],
        "drivers": analysis_results["drivers"],
        "supporting_evidence": supporting_evidence,
        "contradicting_evidence": contradicting_evidence
    }
    
    # Save via Backend API
    success = update_strategy(username, strategy_id, strategy)
    if success:
        master_log(f"Analysis saved to strategy | {username}/{strategy_id}")
    else:
        raise Exception(f"Failed to save strategy to Backend API: {username}/{strategy_id}")


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 3:
        print("Usage: python strategy_analyzer.py <username> <strategy_id>")
        sys.exit(1)
    
    username = sys.argv[1]
    strategy_id = sys.argv[2]
    
    generate_custom_user_analysis(username, strategy_id)
    print(f"\n✅ Custom analysis generated for {username}/{strategy_id}")
