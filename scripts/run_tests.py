#!/usr/bin/env python3
"""
Test runner for pipeline filter tests.
Runs all unit tests and integration tests with coverage reporting.
"""
import sys
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_all_tests():
    """Run all tests with pytest."""
    print("\n" + "=" * 70)
    print("PIPELINE FILTER TEST SUITE")
    print("=" * 70 + "\n")

    # Run pytest with verbose output
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--color=yes"
    ]

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)

    return result.returncode


def run_specific_test(test_path: str):
    """Run a specific test file."""
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        "--tb=short",
        "--color=yes"
    ]

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def run_with_coverage():
    """Run tests with coverage reporting."""
    print("\n" + "=" * 70)
    print("RUNNING TESTS WITH COVERAGE")
    print("=" * 70 + "\n")

    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--cov=src/filters",
        "--cov=src/enrichment/warning_generator",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov"
    ]

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)

    if result.returncode == 0:
        print("\n" + "=" * 70)
        print("✅ Coverage report generated: htmlcov/index.html")
        print("=" * 70 + "\n")

    return result.returncode


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "--coverage" or arg == "-c":
            return run_with_coverage()
        elif arg == "--help" or arg == "-h":
            print("""
Pipeline Filter Test Runner

Usage:
    python scripts/run_tests.py                 Run all tests
    python scripts/run_tests.py --coverage      Run with coverage report
    python scripts/run_tests.py <test_file>     Run specific test file

Examples:
    python scripts/run_tests.py
    python scripts/run_tests.py --coverage
    python scripts/run_tests.py tests/filters/test_size_filters.py
            """)
            return 0
        else:
            # Assume it's a test file path
            return run_specific_test(arg)
    else:
        # Run all tests
        return run_all_tests()


if __name__ == "__main__":
    sys.exit(main())
