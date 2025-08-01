#!/usr/bin/env python3
"""
YTArchive Test Suite Audit Script

Comprehensive test suite validation and reporting tool for maintaining
enterprise-grade test organization and quality standards.

Features:
- Validates all tests have proper pytest markers
- Generates detailed test statistics and reports
- Detects uncategorized or miscategorized tests
- Provides CI/CD integration capabilities
- Supports multiple output formats (console, JSON, markdown)

Usage:
    python scripts/test_audit.py                    # Standard audit report
    python scripts/test_audit.py --json            # JSON output for CI/CD
    python scripts/test_audit.py --markdown        # Markdown report
    python scripts/test_audit.py --strict          # Fail on any issues
    python scripts/test_audit.py --fix-missing     # Auto-fix missing markers
"""

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Test categories and their expected characteristics
TEST_CATEGORIES = {
    "unit": {
        "description": "Unit tests for individual components",
        "expected_patterns": ["test_utils", "test_base", "test_placeholder"],
        "color": "🎯",
    },
    "service": {
        "description": "Service-level tests (single service, mocked dependencies)",
        "expected_patterns": ["test_*_service", "test_cli", "test_workplan_cli"],
        "color": "🔧",
    },
    "integration": {
        "description": "Integration tests (multiple services, real coordination)",
        "expected_patterns": ["test_service_coordination", "test_playlist_integration"],
        "color": "🔗",
    },
    "e2e": {
        "description": "End-to-end workflow tests",
        "expected_patterns": ["test_e2e_workflows"],
        "color": "🚀",
    },
    "memory": {
        "description": "Memory leak detection tests",
        "expected_patterns": ["test_*_memory_leaks"],
        "color": "🧠",
    },
    "performance": {
        "description": "Performance benchmark tests measuring response times and throughput",
        "expected_patterns": ["test_large_playlist_optimizations", "test_performance"],
        "color": "⚡",
    },
}


@dataclass
class AuditTestFunction:
    """Represents a test function with its metadata."""

    name: str
    file_path: str
    line_number: int
    markers: List[str]
    is_async: bool
    docstring: Optional[str] = None
    parametrize_count: int = (
        1  # Number of parameterized combinations (1 for non-parameterized)
    )


@dataclass
class AuditTestFile:
    """Represents a test file with its test functions."""

    path: str
    functions: List[AuditTestFunction]
    total_tests: int


@dataclass
class AuditResult:
    """Results of the test suite audit."""

    total_tests: int
    total_files: int
    categorized_tests: int
    uncategorized_tests: List[AuditTestFunction]
    category_counts: Dict[str, int]
    issues: List[str]
    warnings: List[str]
    test_files: List[AuditTestFile]


class SuiteAuditor:
    """Main auditor class for analyzing the test suite."""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.expected_markers = list(TEST_CATEGORIES.keys())
        self.test_dirs = [
            self.root_path / "tests",
        ]

    def find_test_files(self) -> List[Path]:
        """Find all test files in the project."""
        test_files: List[Path] = []
        for test_dir in self.test_dirs:
            if test_dir.exists():
                test_files.extend(test_dir.rglob("test_*.py"))
        return sorted(test_files)

    def _count_parametrize_combinations(self, decorator_list: List[ast.expr]) -> int:
        """Count the number of test combinations from parametrize decorators."""
        total_combinations = 1

        for decorator in decorator_list:
            # Look for @pytest.mark.parametrize
            if isinstance(decorator, ast.Call) and isinstance(
                decorator.func, ast.Attribute
            ):
                # Check if it's pytest.mark.parametrize
                if (
                    isinstance(decorator.func.value, ast.Attribute)
                    and decorator.func.value.attr == "mark"
                    and isinstance(decorator.func.value.value, ast.Name)
                    and decorator.func.value.value.id == "pytest"
                    and decorator.func.attr == "parametrize"
                ):
                    # Get the parameter values (second argument)
                    if len(decorator.args) >= 2:
                        values_arg = decorator.args[
                            1
                        ]  # Second argument contains the parameter values

                        # Count combinations based on the structure
                        if isinstance(values_arg, ast.List):
                            # Direct list of parameter combinations
                            param_count = len(values_arg.elts)
                            total_combinations *= param_count
                        elif isinstance(values_arg, ast.Tuple):
                            # Tuple of parameter combinations
                            param_count = len(values_arg.elts)
                            total_combinations *= param_count

        return total_combinations

    def _extract_test_info_from_file(self, filepath: Path) -> Dict[str, List[str]]:
        """Extract test function names and their markers from a file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            tests = {}

            # Walk through all nodes to find test functions
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and node.name.startswith("test_"):
                    markers = []

                    # Check decorators
                    for decorator in node.decorator_list:
                        marker_name = None

                        if isinstance(decorator, ast.Attribute):
                            # Handle @pytest.mark.marker
                            if (
                                isinstance(decorator.value, ast.Attribute)
                                and decorator.value.attr == "mark"
                                and isinstance(decorator.value.value, ast.Name)
                                and decorator.value.value.id == "pytest"
                            ):
                                marker_name = decorator.attr
                        elif isinstance(decorator, ast.Call):
                            # Handle @pytest.mark.marker() with parentheses
                            if isinstance(decorator.func, ast.Attribute):
                                if (
                                    isinstance(decorator.func.value, ast.Attribute)
                                    and decorator.func.value.attr == "mark"
                                    and isinstance(decorator.func.value.value, ast.Name)
                                    and decorator.func.value.value.id == "pytest"
                                ):
                                    marker_name = decorator.func.attr
                        elif isinstance(decorator, ast.Name):
                            # Handle simple decorator names that might be pytest markers
                            if decorator.id in self.expected_markers:
                                marker_name = decorator.id

                        if marker_name and marker_name in self.expected_markers:
                            markers.append(marker_name)

                    # Also check for class methods inside test classes
                    tests[node.name] = markers

            # Also check for methods inside test classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and (
                    "Test" in node.name or node.name.startswith("test_")
                ):
                    # First, check for class-level markers
                    class_markers = []
                    for decorator in node.decorator_list:
                        marker_name = None
                        if isinstance(decorator, ast.Attribute):
                            # Handle @pytest.mark.marker
                            if (
                                isinstance(decorator.value, ast.Attribute)
                                and decorator.value.attr == "mark"
                                and isinstance(decorator.value.value, ast.Name)
                                and decorator.value.value.id == "pytest"
                            ):
                                marker_name = decorator.attr
                        elif isinstance(decorator, ast.Call):
                            # Handle @pytest.mark.marker() with parentheses
                            if (
                                isinstance(decorator.func, ast.Attribute)
                                and isinstance(decorator.func.value, ast.Attribute)
                                and decorator.func.value.attr == "mark"
                                and isinstance(decorator.func.value.value, ast.Name)
                                and decorator.func.value.value.id == "pytest"
                            ):
                                marker_name = decorator.func.attr
                        elif isinstance(decorator, ast.Name):
                            # Handle simple decorator names
                            if decorator.id in self.expected_markers:
                                marker_name = decorator.id

                        if marker_name and marker_name in self.expected_markers:
                            class_markers.append(marker_name)

                    # Now process methods in the class
                    for method in node.body:
                        if isinstance(
                            method, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ) and method.name.startswith("test_"):
                            if method.name not in tests:  # Avoid duplicates
                                markers = (
                                    class_markers.copy()
                                )  # Inherit class-level markers

                                # Check decorators on methods
                                for decorator in method.decorator_list:
                                    marker_name = None
                                    if isinstance(decorator, ast.Attribute):
                                        # Handle @pytest.mark.marker
                                        if (
                                            isinstance(decorator.value, ast.Attribute)
                                            and decorator.value.attr == "mark"
                                            and isinstance(
                                                decorator.value.value, ast.Name
                                            )
                                            and decorator.value.value.id == "pytest"
                                        ):
                                            marker_name = decorator.attr
                                    elif isinstance(decorator, ast.Call):
                                        # Handle @pytest.mark.marker() with parentheses
                                        if (
                                            isinstance(decorator.func, ast.Attribute)
                                            and isinstance(
                                                decorator.func.value, ast.Attribute
                                            )
                                            and decorator.func.value.attr == "mark"
                                            and isinstance(
                                                decorator.func.value.value, ast.Name
                                            )
                                            and decorator.func.value.value.id
                                            == "pytest"
                                        ):
                                            marker_name = decorator.func.attr
                                    elif isinstance(decorator, ast.Name):
                                        # Handle simple decorator names
                                        if decorator.id in self.expected_markers:
                                            marker_name = decorator.id

                                    if (
                                        marker_name
                                        and marker_name in self.expected_markers
                                    ):
                                        markers.append(marker_name)

                                tests[method.name] = markers

            return tests
        except Exception as e:
            print(f"Warning: Could not parse {filepath}: {e}")
            return {}

    def extract_test_functions(self, file_path: Path) -> List[AuditTestFunction]:
        """Extract test functions and their metadata from a Python file."""
        test_info = self._extract_test_info_from_file(file_path)
        functions = []

        for test_name, markers in test_info.items():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if (
                        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name == test_name
                    ):
                        is_async = isinstance(node, ast.AsyncFunctionDef)
                        docstring = ast.get_docstring(node)
                        parametrize_count = self._count_parametrize_combinations(
                            node.decorator_list
                        )

                        functions.append(
                            AuditTestFunction(
                                name=node.name,
                                file_path=str(file_path),
                                line_number=node.lineno,
                                markers=markers,
                                is_async=is_async,
                                docstring=docstring,
                                parametrize_count=parametrize_count,
                            )
                        )
            except Exception as e:
                print(f"Warning: Could not parse {file_path}: {e}")

        return functions

    def get_pytest_markers(self) -> Dict[str, int]:
        """Get test counts by marker using pytest --collect-only."""
        marker_counts = {}

        for category in TEST_CATEGORIES.keys():
            try:
                result = subprocess.run(
                    ["uv", "run", "pytest", "-m", category, "--collect-only", "-q"],
                    capture_output=True,
                    text=True,
                    cwd=self.root_path,
                )

                if result.returncode == 0:
                    # Count test lines in output
                    test_lines = [
                        line for line in result.stdout.split("\n") if "::test_" in line
                    ]
                    marker_counts[category] = len(test_lines)
                else:
                    marker_counts[category] = 0

            except Exception as e:
                print(f"Warning: Could not run pytest for {category}: {e}")
                marker_counts[category] = 0

        return marker_counts

    def get_pytest_total_count(self) -> int:
        """Get accurate total test count from pytest --collect-only."""
        try:
            result = subprocess.run(
                ["uv", "run", "pytest", "--collect-only", "-q"],
                capture_output=True,
                text=True,
                cwd=self.root_path,
            )

            if result.returncode == 0:
                # Count test lines in output
                test_lines = [
                    line for line in result.stdout.split("\n") if "::test_" in line
                ]
                return len(test_lines)
            else:
                return 0

        except Exception as e:
            print(f"Warning: Could not run pytest for total count: {e}")
            return 0

    def audit_test_suite(self) -> AuditResult:
        """Perform comprehensive audit of the test suite."""
        test_files = self.find_test_files()
        all_test_functions = []
        processed_files = []
        issues = []
        warnings = []

        # Analyze each test file
        for file_path in test_files:
            functions = self.extract_test_functions(file_path)
            all_test_functions.extend(functions)

            # Calculate total test instances (accounting for parameterized tests)
            total_test_instances = sum(func.parametrize_count for func in functions)

            test_file = AuditTestFile(
                path=str(file_path.relative_to(self.root_path)),
                functions=functions,
                total_tests=total_test_instances,
            )
            processed_files.append(test_file)

        # Find uncategorized tests
        uncategorized_tests = [
            func
            for func in all_test_functions
            if not any(marker in TEST_CATEGORIES for marker in func.markers)
        ]

        # Calculate uncategorized test instances (accounting for parameterized tests)
        uncategorized_test_instances = sum(
            func.parametrize_count for func in uncategorized_tests
        )

        # Run pytest to get marker-based test counts
        pytest_marker_counts = self.get_pytest_markers()
        total_pytest_tests = self.get_pytest_total_count()
        # Calculate total test instances (accounting for parameterized tests)
        total_tests = sum(func.parametrize_count for func in all_test_functions)

        if len(uncategorized_tests) > 0:
            issues.append(
                f"Found {len(uncategorized_tests)} uncategorized test functions ({uncategorized_test_instances} test instances)"
            )

        # Check for discrepancies
        if total_pytest_tests != total_tests:
            warnings.append(
                f"Test count mismatch: pytest reports {total_pytest_tests}, "
                f"AST analysis finds {total_tests} tests"
            )

        return AuditResult(
            total_tests=total_tests,
            total_files=len(processed_files),
            categorized_tests=total_tests - uncategorized_test_instances,
            uncategorized_tests=uncategorized_tests,
            category_counts=pytest_marker_counts,
            issues=issues,
            warnings=warnings,
            test_files=processed_files,
        )


class AuditReporter:
    """Handles different output formats for audit results."""

    def __init__(self, result: AuditResult):
        self.result = result

    def generate_console_report(self) -> str:
        """Generate a comprehensive console report."""
        report = []
        report.append("🔍 YTArchive Test Suite Audit Report")
        report.append("=" * 50)
        report.append("")

        # Overall statistics
        report.append("📊 Overall Statistics:")
        report.append(f"   Total Tests: {self.result.total_tests}")
        report.append(f"   Total Files: {self.result.total_files}")
        if self.result.total_tests > 0:
            report.append(
                f"   Categorized: {self.result.categorized_tests} ({self.result.categorized_tests/self.result.total_tests*100:.1f}%)"
            )
        else:
            report.append(f"   Categorized: {self.result.categorized_tests} (0.0%)")
        report.append(f"   Uncategorized: {len(self.result.uncategorized_tests)}")
        report.append("")

        # Category breakdown
        report.append("📋 Test Categories:")
        for category, count in self.result.category_counts.items():
            if count > 0:
                emoji = TEST_CATEGORIES[category]["color"]
                desc = TEST_CATEGORIES[category]["description"]
                percentage = (count / self.result.total_tests) * 100
                report.append(
                    f"   {emoji} {category}: {count} tests ({percentage:.1f}%) - {desc}"
                )
        report.append("")

        # File breakdown
        report.append("📁 File Breakdown:")
        for test_file in sorted(
            self.result.test_files, key=lambda x: x.total_tests, reverse=True
        ):
            if test_file.total_tests > 0:
                report.append(f"   {test_file.path}: {test_file.total_tests} tests")
        report.append("")

        # Issues and warnings
        if self.result.issues:
            report.append("❌ Issues Found:")
            for issue in self.result.issues:
                report.append(f"   • {issue}")
            report.append("")

        if self.result.warnings:
            report.append("⚠️  Warnings:")
            for warning in self.result.warnings:
                report.append(f"   • {warning}")
            report.append("")

        # Uncategorized tests
        if self.result.uncategorized_tests:
            report.append("🏷️  Uncategorized Tests:")
            for test in self.result.uncategorized_tests:
                report.append(
                    f"   • {test.name} in {test.file_path}:{test.line_number}"
                )
            report.append("")

        # Quality assessment
        if not self.result.issues and not self.result.uncategorized_tests:
            report.append("✅ Test Suite Quality: EXCELLENT")
            report.append("   All tests are properly categorized and organized!")
        elif len(self.result.uncategorized_tests) <= 5:
            report.append("⚠️  Test Suite Quality: GOOD")
            report.append("   Minor categorization issues found.")
        else:
            report.append("❌ Test Suite Quality: NEEDS IMPROVEMENT")
            report.append("   Significant categorization issues found.")

        return "\n".join(report)

    def generate_json_report(self) -> str:
        """Generate JSON report for CI/CD integration."""
        data = {
            "summary": {
                "total_tests": self.result.total_tests,
                "total_files": self.result.total_files,
                "categorized_tests": self.result.categorized_tests,
                "uncategorized_count": len(self.result.uncategorized_tests),
                "categorization_percentage": (
                    self.result.categorized_tests / self.result.total_tests
                )
                * 100,
            },
            "categories": self.result.category_counts,
            "files": [
                {
                    "path": f.path,
                    "test_count": f.total_tests,
                    "functions": [
                        {
                            "name": func.name,
                            "markers": func.markers,
                            "line": func.line_number,
                            "is_async": func.is_async,
                        }
                        for func in f.functions
                    ],
                }
                for f in self.result.test_files
            ],
            "issues": self.result.issues,
            "warnings": self.result.warnings,
            "uncategorized_tests": [
                {"name": test.name, "file": test.file_path, "line": test.line_number}
                for test in self.result.uncategorized_tests
            ],
        }
        return json.dumps(data, indent=2)

    def generate_markdown_report(self) -> str:
        """Generate markdown report for documentation."""
        report = []
        report.append("# YTArchive Test Suite Audit Report")
        report.append("")
        report.append("## 📊 Overall Statistics")
        report.append("")
        report.append(f"- **Total Tests:** {self.result.total_tests}")
        report.append(f"- **Total Files:** {self.result.total_files}")
        report.append(
            f"- **Categorized:** {self.result.categorized_tests} ({self.result.categorized_tests/self.result.total_tests*100:.1f}%)"
        )
        report.append(f"- **Uncategorized:** {len(self.result.uncategorized_tests)}")
        report.append("")

        report.append("## 📋 Test Categories")
        report.append("")
        for category, count in self.result.category_counts.items():
            if count > 0:
                emoji = TEST_CATEGORIES[category]["color"]
                desc = TEST_CATEGORIES[category]["description"]
                percentage = (count / self.result.total_tests) * 100
                report.append(f"### {emoji} {category.title()}")
                report.append(f"- **Count:** {count} tests ({percentage:.1f}%)")
                report.append(f"- **Description:** {desc}")
                report.append("")

        if self.result.uncategorized_tests:
            report.append("## 🏷️ Uncategorized Tests")
            report.append("")
            for test in self.result.uncategorized_tests:
                report.append(
                    f"- `{test.name}` in `{test.file_path}:{test.line_number}`"
                )
            report.append("")

        return "\n".join(report)


def main():
    """Main entry point for the audit script."""
    parser = argparse.ArgumentParser(description="YTArchive Test Suite Auditor")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument(
        "--markdown", action="store_true", help="Output Markdown format"
    )
    parser.add_argument("--strict", action="store_true", help="Fail on any issues")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--root", default=".", help="Root directory path")

    args = parser.parse_args()

    # Run the audit
    auditor = SuiteAuditor(args.root)
    result = auditor.audit_test_suite()
    reporter = AuditReporter(result)

    # Generate report
    if args.json:
        report = reporter.generate_json_report()
    elif args.markdown:
        report = reporter.generate_markdown_report()
    else:
        report = reporter.generate_console_report()

    # Output report
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)

    # Exit with error code if issues found and strict mode enabled
    if args.strict and (result.issues or result.uncategorized_tests):
        print("\n❌ Strict mode: Exiting with error code due to issues found.")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
