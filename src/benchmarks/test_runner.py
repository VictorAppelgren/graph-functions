"""
Test Runner - Executes benchmark tests against models

Simple: Give it a model config, run tests, return results.
"""

import json
import time
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

from .test_cases import TEST_CASES, TEST_SUITES


# =============================================================================
# MODEL REGISTRY - Add new models here
# =============================================================================

MODEL_REGISTRY = {
    # Current baseline
    "gpt-oss-20b": {
        "base_url": "http://gate04.cfa.handels.gu.se:8686/v1",
        "model": "openai/gpt-oss-20b",
        "api_key": "sk-noop",
    },
    "gpt-oss-20b-b": {
        "base_url": "http://gate04.cfa.handels.gu.se:8787/v1",
        "model": "openai/gpt-oss-20b",
        "api_key": "sk-noop",
    },
    # 120B model
    "gpt-oss-120b": {
        "base_url": "http://gate04.cfa.handels.gu.se:3331/v1",
        "model": "openai/gpt-oss-120b",
        "api_key": "sk-noop",
    },
    # Add new models here:
    # "qwen-32b": {
    #     "base_url": "http://...",
    #     "model": "qwen/qwen-32b",
    #     "api_key": "sk-noop",
    # },
    # "nemotron-22b": {
    #     "base_url": "http://...",
    #     "model": "nvidia/nemotron-22b",
    #     "api_key": "sk-noop",
    # },
}


@dataclass
class TestResult:
    """Result from running a single test."""
    test_name: str
    model_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    raw_output: str
    parsed_output: dict | None
    error: str | None
    time_seconds: float
    notes: list[str]


def build_llm(model_name: str) -> ChatOpenAI:
    """Build LLM client for a model."""
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_name}. Add it to MODEL_REGISTRY.")

    config = MODEL_REGISTRY[model_name]
    return ChatOpenAI(
        base_url=config["base_url"],
        model=config["model"],
        api_key=config["api_key"],
        temperature=0.2,
        max_tokens=2048,
        timeout=120.0,
    )


def format_prompt(test_case: dict) -> str:
    """Format a test case prompt with its data."""
    prompt_template = test_case["prompt"]

    # Single article case
    if "article" in test_case:
        article = test_case["article"]
        return prompt_template.format(
            title=article["title"],
            content=article["content"],
            topic=test_case.get("topic", ""),
        )

    # Multiple articles case
    if "articles" in test_case:
        articles_formatted = "\n\n".join([
            f"Article ID: {a['id']}\nTitle: {a['title']}\nContent: {a['content']}"
            for a in test_case["articles"]
        ])
        return prompt_template.format(
            articles_formatted=articles_formatted,
            topic=test_case.get("topic", ""),
        )

    # No article (like json_compliance)
    return prompt_template


def parse_json_output(raw: str) -> tuple[dict | None, str | None]:
    """Try to parse JSON from model output."""
    # Clean up common issues
    text = raw.strip()

    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"


def evaluate_result(test_name: str, test_case: dict, parsed: dict | None, raw: str) -> tuple[bool, float, list[str]]:
    """Evaluate if test passed and calculate score."""
    notes = []
    expected = test_case.get("expected", {})

    # If JSON didn't parse, fail
    if parsed is None:
        return False, 0.0, ["Failed to parse JSON output"]

    score = 0.5  # Start at middle, adjust up/down
    passed = True

    # --- Test-specific evaluation ---

    if test_name == "classify_relevance":
        relevance = parsed.get("relevance", "").upper()
        expected_relevance = expected.get("relevance", "HIGH")

        if relevance == expected_relevance:
            score += 0.3
            notes.append(f"✓ Correct relevance: {relevance}")
        else:
            score -= 0.3
            passed = False
            notes.append(f"✗ Expected {expected_relevance}, got {relevance}")

        # Check reasoning quality
        reasoning = parsed.get("reasoning", "").lower()
        good_terms = expected.get("good_reasoning_contains", [])
        terms_found = sum(1 for term in good_terms if term.lower() in reasoning)
        if terms_found >= 2:
            score += 0.2
            notes.append(f"✓ Good reasoning ({terms_found}/{len(good_terms)} key terms)")
        else:
            notes.append(f"○ Weak reasoning ({terms_found}/{len(good_terms)} key terms)")

    elif test_name == "conviction_test":
        direction = parsed.get("direction", "")
        reasoning = parsed.get("reasoning", "").lower()

        # Check for hedging language
        fail_phrases = expected.get("fail_phrases", [])
        hedges_found = [p for p in fail_phrases if p.lower() in reasoning]

        if hedges_found:
            score -= 0.4
            passed = False
            notes.append(f"✗ Hedging detected: {hedges_found}")
        else:
            score += 0.3
            notes.append("✓ Clear stance, no hedging")

        # Check conviction level
        conviction = parsed.get("conviction", "").upper()
        if conviction in ["HIGH", "MEDIUM"]:
            score += 0.1
            notes.append(f"✓ Conviction: {conviction}")
        elif conviction == "LOW":
            notes.append("○ Low conviction")

    elif test_name == "simple_causal_chain":
        chain = parsed.get("chain", [])
        min_steps = expected.get("min_steps", 3)

        if len(chain) >= min_steps:
            score += 0.3
            notes.append(f"✓ Chain has {len(chain)} steps (min: {min_steps})")
        else:
            score -= 0.2
            passed = False
            notes.append(f"✗ Chain too short: {len(chain)} steps (min: {min_steps})")

        # Check for direction
        chain_text = " ".join(chain).lower()
        if any(word in chain_text for word in ["up", "down", "rise", "fall", "bullish", "bearish", "strengthen", "weaken"]):
            score += 0.1
            notes.append("✓ Has directional conclusion")
        else:
            notes.append("○ Missing clear direction")

    elif test_name == "source_citation":
        cited = parsed.get("articles_cited", [])
        valid_ids = expected.get("valid_ids", [])
        min_citations = expected.get("must_cite_at_least", 2)

        # Check for hallucinated IDs
        invalid = [c for c in cited if c not in valid_ids]
        if invalid:
            score -= 0.4
            passed = False
            notes.append(f"✗ Hallucinated IDs: {invalid}")

        # Check citation count
        valid_citations = [c for c in cited if c in valid_ids]
        if len(valid_citations) >= min_citations:
            score += 0.3
            notes.append(f"✓ Cited {len(valid_citations)} valid sources")
        else:
            score -= 0.2
            notes.append(f"○ Only {len(valid_citations)} citations (need {min_citations})")

        # Check if IDs appear in summary text
        summary = parsed.get("summary", "")
        ids_in_text = sum(1 for id in valid_ids if id in summary)
        if ids_in_text >= min_citations:
            score += 0.1
            notes.append("✓ Citations embedded in text")

    elif test_name == "json_compliance":
        required = expected.get("required_fields", [])
        missing = [f for f in required if f not in parsed]

        if not missing:
            score += 0.3
            notes.append("✓ All required fields present")
        else:
            score -= 0.3
            passed = False
            notes.append(f"✗ Missing fields: {missing}")

        # Check enum values
        if "trend" in parsed:
            valid_trends = expected.get("trend_values", [])
            if parsed["trend"] in valid_trends:
                score += 0.1
                notes.append("✓ Valid trend value")
            else:
                score -= 0.1
                notes.append(f"✗ Invalid trend: {parsed['trend']}")

        # Check confidence is numeric
        if "confidence" in parsed:
            try:
                conf = float(parsed["confidence"])
                if 0 <= conf <= 1:
                    score += 0.1
                    notes.append("✓ Valid confidence range")
            except (TypeError, ValueError):
                score -= 0.1
                notes.append("✗ Invalid confidence format")

    elif test_name == "quantification":
        terms = parsed.get("vague_terms_found", [])
        min_terms = expected.get("min_terms_found", 3)

        if len(terms) >= min_terms:
            score += 0.3
            notes.append(f"✓ Found {len(terms)} vague terms")
        else:
            score -= 0.2
            notes.append(f"○ Only found {len(terms)} terms (want {min_terms})")

        # Check if replacements have numbers
        has_numbers = sum(1 for t in terms if any(c.isdigit() for c in str(t.get("suggested_replacement", ""))))
        if has_numbers >= 2:
            score += 0.2
            notes.append(f"✓ {has_numbers} replacements have specific numbers")
        else:
            notes.append("○ Replacements lack specific numbers")

    elif test_name == "multi_step_chain":
        chain = parsed.get("chain", [])
        min_steps = expected.get("min_steps", 4)

        if len(chain) >= min_steps:
            score += 0.3
            notes.append(f"✓ Deep chain: {len(chain)} steps")
        else:
            score -= 0.2
            passed = False
            notes.append(f"✗ Chain too shallow: {len(chain)} steps (need {min_steps})")

        # Check for non-obvious insight
        insight = parsed.get("non_obvious_insight", "")
        if len(insight) > 50:
            score += 0.2
            notes.append("✓ Has non-obvious insight")
        else:
            notes.append("○ Weak or missing insight")

    elif test_name == "cross_domain_synthesis":
        synthesis = parsed.get("synthesis", "")

        # Check if multiple article IDs are referenced
        article_refs = synthesis.count("BENCH008")
        if article_refs >= 2:
            score += 0.3
            notes.append(f"✓ References {article_refs} articles")
        else:
            score -= 0.2
            notes.append("○ Doesn't combine multiple sources")

        # Check for actionable implication
        actionable = parsed.get("actionable_implication", "")
        if len(actionable) > 30:
            score += 0.2
            notes.append("✓ Has actionable implication")
        else:
            notes.append("○ Missing actionable takeaway")

    # Clamp score
    score = max(0.0, min(1.0, score))

    return passed, score, notes


def run_single_test(model_name: str, test_name: str, llm: ChatOpenAI) -> TestResult:
    """Run a single test against a model."""
    test_case = TEST_CASES[test_name]
    prompt = format_prompt(test_case)

    start_time = time.time()
    error = None
    raw_output = ""
    parsed_output = None

    try:
        response = llm.invoke(prompt)
        raw_output = response.content
        parsed_output, parse_error = parse_json_output(raw_output)
        if parse_error:
            error = parse_error
    except Exception as e:
        error = str(e)

    elapsed = time.time() - start_time

    # Evaluate
    if error and not parsed_output:
        passed, score, notes = False, 0.0, [f"Error: {error}"]
    else:
        passed, score, notes = evaluate_result(test_name, test_case, parsed_output, raw_output)

    return TestResult(
        test_name=test_name,
        model_name=model_name,
        passed=passed,
        score=score,
        raw_output=raw_output,
        parsed_output=parsed_output,
        error=error,
        time_seconds=elapsed,
        notes=notes,
    )


def run_benchmark(models: list[str], suite: str = "standard") -> dict[str, list[TestResult]]:
    """Run full benchmark suite against multiple models.

    Returns: {model_name: [TestResult, ...]}
    """
    if suite not in TEST_SUITES:
        raise ValueError(f"Unknown suite: {suite}. Options: {list(TEST_SUITES.keys())}")

    test_names = TEST_SUITES[suite]
    results = {}

    for model_name in models:
        print(f"\n{'='*60}")
        print(f"Testing: {model_name}")
        print(f"{'='*60}")

        try:
            llm = build_llm(model_name)
        except Exception as e:
            print(f"  ✗ Failed to build LLM: {e}")
            results[model_name] = []
            continue

        model_results = []
        for test_name in test_names:
            print(f"  Running: {test_name}...", end=" ", flush=True)
            result = run_single_test(model_name, test_name, llm)
            model_results.append(result)

            status = "✓" if result.passed else "✗"
            print(f"{status} (score: {result.score:.2f}, time: {result.time_seconds:.1f}s)")

        results[model_name] = model_results

    return results
