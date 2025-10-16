import sys
import os

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
from utils import app_logging
from src.graph.ops.topic import get_all_topics
from src.graph.ops.link import remove_link, get_existing_links
from src.graph.policies.link import llm_select_link_to_remove
from src.graph.core.user_anchors import USER_ANCHOR_TOPICS

logger = app_logging.get_logger(__name__)


def interactive_propose_and_remove() -> None:
    """
    Stateless, minimal flow:
    1) Find a non-anchor source with >=2 non-ABOUT links (targets not anchors).
    2) Ask you to approve the source (single y/N).
    3) Build candidates and call LLM to pick weakest link; show motivation.
    4) Auto-remove and persist full context (no second y/N).
    """

    app_logging.get_logger("graph_relationships.get_existing_links").setLevel(
        logging.INFO
    )
    app_logging.get_logger("graph_relationships.add_link").setLevel(logging.INFO)

    anchor_ids = {n.get("id") for n in USER_ANCHOR_TOPICS}
    topics = get_all_topics()
    if not topics:
        print("No candidate relationship found.")
        return

    id_to_topic = {n.get("id"): n for n in topics}
    id_to_name = {n.get("id"): n.get("name", n.get("id")) for n in topics}

    # 1) Iterate sources; prompt once per source
    for n in topics:
        src = n.get("id")
        if not src or src in anchor_ids:
            continue
        try:
            links = get_existing_links(src)
        except Exception:
            continue
        # Only non-ABOUT links that do not touch anchors
        candidate_links = [
            l
            for l in links
            if l.get("type") != "ABOUT" and l.get("target") not in anchor_ids
        ]
        if len(candidate_links) < 2:
            continue

        # Show a compact summary for approval
        sample = candidate_links[:3]
        sample_str = "; ".join(
            f"{id_to_name.get(l.get('target'), l.get('target'))} ({l.get('type')})"
            for l in sample
        )
        print(
            f"Source candidate: {id_to_name.get(src, src)} ({src}), "
            f"non-ABOUT links: {len(candidate_links)}. Sample: {sample_str}"
        )
        resp = input("Use this source? [y/N]: ").strip().lower()
        if resp not in ("y", "yes"):
            continue  # try next source

        # 2) Approved source → build LLM inputs
        source_topic = {
            "id": src,
            "name": id_to_name.get(src, src),
            "type": id_to_topic.get(src, {}).get("type", "Topic"),
        }
        candidate_ids = [l.get("target") for l in candidate_links if l.get("target")]
        candidate_motivation = (
            "Non-ABOUT outgoing links from selected source (anchors excluded)."
        )
        existing_links_count = len(candidate_links)

        # Fake prioritized link for testing
        prioritized_link = {
            "type": "INFLUENCES",
            "source": "trump_dc_public_safety",
            "target": "federal_grant_compliance_dc_policing",
            "motivation": (
                "OMB guidance ties Byrne JAG/DHS funds to transparent reporting, training benchmarks, and "
                "union arbitration reforms, making fiscal/oversight levers the proximate driver of MPD policy. "
                "Compliance audits and quarterly thresholds directly influence deployment and management incentives, "
                "reducing the explanatory power of broad violent-crime trendlines. Therefore, replace trend-based links "
                "with a mechanism-specific link to federal grant compliance conditions."
            ),
            "title": "OMB Tightens Federal Grant Conditions for D.C. Policing",
            "summary": (
                "Access to federal policing grants will hinge on verifiable transparency and training metrics, "
                "with quarterly audits shaping D.C. policing priorities more than generalized crime-rate narratives."
            ),
        }

        # 3) Call LLM selector (no prioritized_link in standalone QA)
        result = llm_select_link_to_remove(
            source_topic, candidate_links, prioritized_link=prioritized_link
        )
        if not isinstance(result, dict) or not result.get("remove_link"):
            print("LLM returned no decision. Aborting.")
            return

        target_to_remove = result["remove_link"]
        selection_motivation = result.get("motivation", "")

        # Verify target is in our candidate set
        link = next(
            (l for l in candidate_links if l.get("target") == target_to_remove), None
        )
        if not link:
            print("LLM chose a target not in candidate set. Aborting.")
            return

        # Minimal visibility
        src_name = id_to_name.get(src, src)
        tgt = link.get("target")
        tgt_name = id_to_name.get(tgt, tgt)
        rtype = link.get("type")
        print(f"Suggestion: {src_name} ({src}) --[{rtype}]--> {tgt_name} ({tgt})")
        if selection_motivation:
            print(f"Motivation: {selection_motivation}")

        # 4) Execute removal with full provenance; no second prompt
        ctx = {
            "remove_cause": "qa_cleanup",
            "trigger_stage": "tests.test_remove_relationship.interactive_propose_and_remove",
            "entry_point": "tests/test_remove_relationship.py::interactive_propose_and_remove",
            "user_confirmation": True,  # you approved the source
            "source_topic": source_topic,
            "candidate_motivation": candidate_motivation,
            "candidate_ids": candidate_ids,
            "existing_links_count": existing_links_count,
            "selection_motivation": selection_motivation,
            "prioritized_link": None,  # pipeline mode sets this to the new link
            "llm_raw_response": result,  # full JSON response for audit
        }
        try:
            remove_link(link, context=ctx)
            after = get_existing_links(src)
            still = [
                l
                for l in after
                if l.get("type") == link.get("type")
                and l.get("source") == link.get("source")
                and l.get("target") == link.get("target")
            ]
            if not still:
                logger.info("Removed.")
        except Exception:
            logger.error("Error: could not remove.")
        return  # done after first approved source

    print("No candidate relationship found.")


# main to run test
if __name__ == "__main__":
    # Run interactive propose→approve→apply to avoid accidental removal of important links
    interactive_propose_and_remove()
