"""
Model Benchmark Runner

THE MAIN ENTRY POINT.

Configure models and suite below, then run:
    python -m src.benchmarks.run_benchmark

Results saved to: src/benchmarks/results/YYYY-MM-DD_suite_comparison.md
"""

from pathlib import Path

from .test_runner import run_benchmark
from .report_generator import generate_report


# =============================================================================
# CONFIGURE HERE
# =============================================================================

# Models to test - add/remove as needed
# Must match keys in test_runner.MODEL_REGISTRY
MODELS_TO_TEST = [
    "gpt-oss-20b",      # Current baseline (port 8686)
    # "gpt-oss-20b-b",  # Same model, different server (port 8787)
    # "gpt-oss-120b",   # Larger model (port 3331)
    # "qwen-32b",       # Add to MODEL_REGISTRY first
    # "nemotron-22b",   # Add to MODEL_REGISTRY first
]

# Test suite: "quick" (3 tests) | "standard" (6 tests) | "deep" (8 tests)
TEST_SUITE = "standard"

# =============================================================================
# END CONFIG
# =============================================================================


def main():
    """Run the benchmark."""
    print("=" * 60)
    print("MODEL BENCHMARK")
    print("=" * 60)
    print(f"Models: {MODELS_TO_TEST}")
    print(f"Suite:  {TEST_SUITE}")
    print("=" * 60)

    # Run benchmark
    results = run_benchmark(MODELS_TO_TEST, TEST_SUITE)

    # Generate report
    output_dir = Path(__file__).parent / "results"
    report_path = generate_report(results, TEST_SUITE, output_dir)

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    print(f"Report saved to: {report_path}")
    print("\nOpen the report to see detailed comparison.")


if __name__ == "__main__":
    main()
