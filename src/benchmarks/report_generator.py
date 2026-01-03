"""
Report Generator - Creates markdown comparison reports

Takes benchmark results and produces a clean, readable markdown file.
"""

from datetime import datetime
from pathlib import Path

from .test_runner import TestResult
from .test_cases import TEST_CASES


def calculate_summary_stats(results: list[TestResult]) -> dict:
    """Calculate summary statistics for a model's results."""
    if not results:
        return {"total": 0, "passed": 0, "avg_score": 0.0, "avg_time": 0.0}

    passed = sum(1 for r in results if r.passed)
    avg_score = sum(r.score for r in results) / len(results)
    avg_time = sum(r.time_seconds for r in results) / len(results)

    return {
        "total": len(results),
        "passed": passed,
        "pass_rate": passed / len(results) * 100,
        "avg_score": avg_score,
        "avg_time": avg_time,
    }


def score_to_stars(score: float) -> str:
    """Convert 0-1 score to star rating."""
    stars = int(score * 4)
    return "★" * stars + "☆" * (4 - stars)


def generate_report(
    results: dict[str, list[TestResult]],
    suite: str,
    output_dir: Path,
) -> Path:
    """Generate markdown report from benchmark results.

    Args:
        results: {model_name: [TestResult, ...]}
        suite: Name of test suite used
        output_dir: Directory to write report

    Returns:
        Path to generated report
    """
    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M")

    # Calculate stats for each model
    stats = {model: calculate_summary_stats(res) for model, res in results.items()}

    # Find winner (highest avg score)
    if stats:
        winner = max(stats.keys(), key=lambda m: stats[m]["avg_score"])
    else:
        winner = None

    # Build report
    lines = []

    # Header
    lines.append("# Model Benchmark Results")
    lines.append("")
    lines.append(f"**Date**: {date_str} {time_str}")
    lines.append(f"**Suite**: {suite}")
    lines.append(f"**Models**: {', '.join(results.keys())}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary Scoreboard
    lines.append("## Summary Scoreboard")
    lines.append("")
    lines.append("| Model | Score | Pass Rate | Avg Time | Recommend? |")
    lines.append("|-------|-------|-----------|----------|------------|")

    for model, s in sorted(stats.items(), key=lambda x: -x[1]["avg_score"]):
        score_display = f"{s['avg_score']:.2f}"
        pass_rate = f"{s['pass_rate']:.0f}%"
        time_display = f"{s['avg_time']:.1f}s"

        if model == winner:
            recommend = "**BEST**"
            model_display = f"**{model}**"
        else:
            recommend = "-"
            model_display = model

        lines.append(f"| {model_display} | {score_display} | {pass_rate} | {time_display} | {recommend} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Test-by-Test Results
    lines.append("## Test-by-Test Results")
    lines.append("")

    # Get all test names from results
    all_tests = set()
    for model_results in results.values():
        for r in model_results:
            all_tests.add(r.test_name)

    for test_name in sorted(all_tests):
        test_case = TEST_CASES.get(test_name, {})
        test_display_name = test_case.get("name", test_name)
        test_description = test_case.get("description", "")

        lines.append(f"### {test_display_name}")
        lines.append(f"*{test_description}*")
        lines.append("")

        # Table header
        lines.append("| Model | Score | Passed | Time | Notes |")
        lines.append("|-------|-------|--------|------|-------|")

        # Find results for this test across models
        test_results = []
        for model, model_results in results.items():
            for r in model_results:
                if r.test_name == test_name:
                    test_results.append((model, r))

        # Sort by score descending
        test_results.sort(key=lambda x: -x[1].score)

        for model, r in test_results:
            score = f"{r.score:.2f}"
            passed = "✓" if r.passed else "✗"
            time = f"{r.time_seconds:.1f}s"
            notes = "; ".join(r.notes[:2]) if r.notes else "-"  # First 2 notes

            lines.append(f"| {model} | {score} | {passed} | {time} | {notes} |")

        # Winner for this test
        if test_results:
            test_winner = test_results[0][0]
            lines.append("")
            lines.append(f"**Test Winner**: {test_winner}")

        lines.append("")
        lines.append("---")
        lines.append("")

    # Raw Outputs Section (collapsible)
    lines.append("## Raw Outputs")
    lines.append("")
    lines.append("*Expand to see actual model outputs for manual comparison*")
    lines.append("")

    for model, model_results in results.items():
        lines.append(f"### {model}")
        lines.append("")

        for r in model_results:
            lines.append(f"<details>")
            lines.append(f"<summary>{r.test_name} (score: {r.score:.2f})</summary>")
            lines.append("")
            lines.append("```json")
            # Truncate very long outputs
            output = r.raw_output[:2000] if len(r.raw_output) > 2000 else r.raw_output
            lines.append(output)
            lines.append("```")
            lines.append("")
            if r.notes:
                lines.append("**Notes:**")
                for note in r.notes:
                    lines.append(f"- {note}")
                lines.append("")
            lines.append("</details>")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Verdict Section
    lines.append("## Verdict")
    lines.append("")

    if winner and len(results) > 1:
        winner_stats = stats[winner]

        # Compare to others
        other_models = [m for m in results.keys() if m != winner]
        comparisons = []
        for other in other_models:
            other_stats = stats[other]
            score_diff = winner_stats["avg_score"] - other_stats["avg_score"]
            if score_diff > 0:
                comparisons.append(f"+{score_diff:.2f} vs {other}")

        lines.append(f"**RECOMMENDED**: {winner}")
        lines.append("")
        lines.append(f"**Why**:")
        lines.append(f"- Highest average score: {winner_stats['avg_score']:.2f}")
        lines.append(f"- Pass rate: {winner_stats['pass_rate']:.0f}%")
        lines.append(f"- Average response time: {winner_stats['avg_time']:.1f}s")
        if comparisons:
            lines.append(f"- Score advantage: {', '.join(comparisons)}")
        lines.append("")
        lines.append("**Should you switch?**")
        lines.append("")

        # Decision guidance
        score_diff = winner_stats["avg_score"] - min(stats[m]["avg_score"] for m in other_models)
        if score_diff >= 0.15:
            lines.append("**YES** - Clear improvement in reasoning quality")
        elif score_diff >= 0.05:
            lines.append("**MAYBE** - Marginal improvement, test on production before switching")
        else:
            lines.append("**NO STRONG SIGNAL** - Models are similar, consider cost/speed tradeoffs")

    elif len(results) == 1:
        model = list(results.keys())[0]
        lines.append(f"Single model tested: {model}")
        lines.append("")
        lines.append("Run with multiple models to get comparison.")

    else:
        lines.append("No results to compare.")

    lines.append("")

    # Write to file
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date_str}_{suite}_comparison.md"
    output_path = output_dir / filename

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    return output_path
