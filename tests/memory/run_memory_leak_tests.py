#!/usr/bin/env python3
"""
Master test runner for memory leak detection across all YTArchive services.

This script runs comprehensive memory leak tests for all services and generates
a detailed report with recommendations for production deployment.
"""

import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class MemoryLeakTestSuite:
    """Master test suite for memory leak detection."""

    def __init__(self):
        self.results: Dict[str, Any] = {
            "test_run_id": datetime.now().isoformat(),
            "services": {},
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "leaks_detected": 0,
                "critical_leaks": 0,
                "high_leaks": 0,
                "medium_leaks": 0,
                "low_leaks": 0,
            },
            "recommendations": [],
        }

    def run_service_tests(self, service_name: str, test_file: str) -> Dict[str, Any]:
        """Run memory leak tests for a specific service."""
        print(f"\n{'='*60}")
        print(f"Running memory leak tests for {service_name}")
        print(f"{'='*60}")

        # Run pytest with detailed output
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            test_file,
            "-v",
            "--tb=short",
            "--capture=no",
            "--maxfail=5",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            service_result: Dict[str, Any] = {
                "service_name": service_name,
                "test_file": test_file,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tests_passed": result.returncode == 0,
                "memory_issues": [],
            }
            memory_issues = service_result["memory_issues"]  # type: ignore

            # Parse output for memory leak indicators
            if "Memory leak detected" in result.stdout:
                memory_issues.append("Memory leaks detected in test output")

            if "CRITICAL" in result.stdout:
                memory_issues.append("Critical memory leaks detected")
                self.results["summary"]["critical_leaks"] += 1

            if "HIGH" in result.stdout:
                memory_issues.append("High-severity memory leaks detected")
                self.results["summary"]["high_leaks"] += 1

            if "MEDIUM" in result.stdout:
                memory_issues.append("Medium-severity memory leaks detected")
                self.results["summary"]["medium_leaks"] += 1

            if "LOW" in result.stdout:
                memory_issues.append("Low-severity memory leaks detected")
                self.results["summary"]["low_leaks"] += 1

            # Update summary
            if service_result["memory_issues"]:
                self.results["summary"]["leaks_detected"] += 1

            if result.returncode == 0:
                self.results["summary"]["passed_tests"] += 1
                print(f"✅ {service_name} memory leak tests PASSED")
            else:
                self.results["summary"]["failed_tests"] += 1
                print(f"❌ {service_name} memory leak tests FAILED")
                print(f"Error output: {result.stderr}")

            return service_result

        except Exception as e:
            service_result = {
                "service_name": service_name,
                "test_file": test_file,
                "exit_code": -1,
                "error": str(e),
                "tests_passed": False,
                "memory_issues": [f"Failed to run tests: {str(e)}"],
            }

            self.results["summary"]["failed_tests"] += 1
            print(f"❌ {service_name} memory leak tests FAILED with exception: {e}")

            return service_result

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all memory leak tests."""
        print("🔍 Starting comprehensive memory leak detection for YTArchive services")
        print(f"Test run ID: {self.results['test_run_id']}")

        # Define test suite
        test_services = [
            ("DownloadService", "tests/memory/test_download_memory_leaks.py"),
            ("MetadataService", "tests/memory/test_metadata_memory_leaks.py"),
            ("StorageService", "tests/memory/test_storage_memory_leaks.py"),
        ]

        # Install required dependencies
        print("\n📦 Installing required dependencies...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "psutil", "tracemalloc"],
                check=True,
                capture_output=True,
            )
            print("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Warning: Could not install dependencies: {e}")

        # Run tests for each service
        for service_name, test_file in test_services:
            service_result = self.run_service_tests(service_name, test_file)
            self.results["services"][service_name] = service_result
            self.results["summary"]["total_tests"] += 1

        # Generate recommendations
        self._generate_recommendations()

        return self.results

    def _generate_recommendations(self):
        """Generate recommendations based on test results."""
        recommendations = []

        # Critical issues
        if self.results["summary"]["critical_leaks"] > 0:
            recommendations.append(
                {
                    "severity": "CRITICAL",
                    "issue": f"{self.results['summary']['critical_leaks']} critical memory leaks detected",
                    "action": "Do not deploy to production until all critical memory leaks are fixed",
                    "details": "Critical memory leaks can cause service crashes and system instability",
                }
            )

        # High severity issues
        if self.results["summary"]["high_leaks"] > 0:
            recommendations.append(
                {
                    "severity": "HIGH",
                    "issue": f"{self.results['summary']['high_leaks']} high-severity memory leaks detected",
                    "action": "Fix before production deployment",
                    "details": "High-severity leaks can cause performance degradation and eventual service failure",
                }
            )

        # Medium severity issues
        if self.results["summary"]["medium_leaks"] > 0:
            recommendations.append(
                {
                    "severity": "MEDIUM",
                    "issue": f"{self.results['summary']['medium_leaks']} medium-severity memory leaks detected",
                    "action": "Monitor closely in production and fix in next release",
                    "details": "Medium-severity leaks may cause gradual performance degradation",
                }
            )

        # Low severity issues
        if self.results["summary"]["low_leaks"] > 0:
            recommendations.append(
                {
                    "severity": "LOW",
                    "issue": f"{self.results['summary']['low_leaks']} low-severity memory leaks detected",
                    "action": "Monitor and fix when convenient",
                    "details": "Low-severity leaks have minimal impact but should be addressed",
                }
            )

        # Test failures
        if self.results["summary"]["failed_tests"] > 0:
            recommendations.append(
                {
                    "severity": "ERROR",
                    "issue": f"{self.results['summary']['failed_tests']} test suites failed to run",
                    "action": "Fix test environment and re-run memory leak detection",
                    "details": "Test failures prevent proper memory leak assessment",
                }
            )

        # Success case
        if (
            self.results["summary"]["leaks_detected"] == 0
            and self.results["summary"]["failed_tests"] == 0
        ):
            recommendations.append(
                {
                    "severity": "SUCCESS",
                    "issue": "No memory leaks detected",
                    "action": "Services are ready for production deployment",
                    "details": "All memory leak tests passed successfully",
                }
            )

        # General recommendations
        recommendations.extend(
            [
                {
                    "severity": "INFO",
                    "issue": "Production monitoring recommendations",
                    "action": "Implement continuous memory monitoring in production",
                    "details": "Use tools like Prometheus + Grafana to monitor memory usage patterns",
                },
                {
                    "severity": "INFO",
                    "issue": "Resource limits recommendations",
                    "action": "Set appropriate memory limits for each service",
                    "details": "Configure container memory limits based on test results",
                },
                {
                    "severity": "INFO",
                    "issue": "Regular testing recommendations",
                    "action": "Run memory leak tests regularly as part of CI/CD",
                    "details": "Include memory leak detection in automated testing pipeline",
                },
            ]
        )

        self.results["recommendations"] = recommendations

    def generate_report(self) -> str:
        """Generate a comprehensive memory leak report."""
        report_lines = [
            "=" * 80,
            "YTARCHIVE MEMORY LEAK DETECTION REPORT",
            "=" * 80,
            f"Test Run ID: {self.results['test_run_id']}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Services Tested: {self.results['summary']['total_tests']}",
            f"Tests Passed: {self.results['summary']['passed_tests']}",
            f"Tests Failed: {self.results['summary']['failed_tests']}",
            f"Services with Memory Leaks: {self.results['summary']['leaks_detected']}",
            "",
            "MEMORY LEAK SEVERITY BREAKDOWN",
            "-" * 40,
            f"Critical: {self.results['summary']['critical_leaks']}",
            f"High: {self.results['summary']['high_leaks']}",
            f"Medium: {self.results['summary']['medium_leaks']}",
            f"Low: {self.results['summary']['low_leaks']}",
            "",
        ]

        # Service-specific results
        report_lines.append("SERVICE-SPECIFIC RESULTS")
        report_lines.append("-" * 40)

        for service_name, service_result in self.results["services"].items():
            status = "✅ PASSED" if service_result["tests_passed"] else "❌ FAILED"
            report_lines.append(f"{service_name}: {status}")

            if service_result["memory_issues"]:
                report_lines.append("  Memory Issues:")
                for issue in service_result["memory_issues"]:
                    report_lines.append(f"    - {issue}")

            if not service_result["tests_passed"] and "error" in service_result:
                report_lines.append(f"  Error: {service_result['error']}")

        report_lines.append("")

        # Recommendations
        report_lines.append("RECOMMENDATIONS")
        report_lines.append("-" * 40)

        for rec in self.results["recommendations"]:
            report_lines.append(f"[{rec['severity']}] {rec['issue']}")
            report_lines.append(f"  Action: {rec['action']}")
            report_lines.append(f"  Details: {rec['details']}")
            report_lines.append("")

        # Production readiness assessment
        report_lines.extend(
            [
                "PRODUCTION READINESS ASSESSMENT",
                "-" * 40,
            ]
        )

        if self.results["summary"]["critical_leaks"] > 0:
            report_lines.append("🚨 NOT READY FOR PRODUCTION")
            report_lines.append("Critical memory leaks must be fixed before deployment")
        elif self.results["summary"]["high_leaks"] > 0:
            report_lines.append("⚠️ PROCEED WITH CAUTION")
            report_lines.append(
                "High-severity memory leaks should be fixed before deployment"
            )
        elif self.results["summary"]["medium_leaks"] > 0:
            report_lines.append("⚠️ READY WITH MONITORING")
            report_lines.append(
                "Deploy with close monitoring and fix medium-severity leaks soon"
            )
        else:
            report_lines.append("✅ READY FOR PRODUCTION")
            report_lines.append("No significant memory leaks detected")

        return "\n".join(report_lines)

    def save_report(self, json_file: Path, text_file: Path):
        """Save detailed results and human-readable report."""
        # Save JSON results
        with open(json_file, "w") as f:
            json.dump(self.results, f, indent=2)

        # Save text report
        with open(text_file, "w") as f:
            f.write(self.generate_report())

        print(f"\n📊 Detailed results saved to: {json_file}")
        print(f"📄 Human-readable report saved to: {text_file}")


def main():
    """Main entry point."""
    print("🔍 YTArchive Memory Leak Detection Suite")
    print("=" * 60)

    # Create test suite
    test_suite = MemoryLeakTestSuite()

    # Run all tests
    results = test_suite.run_all_tests()

    # Generate and display report
    report = test_suite.generate_report()
    print("\n" + report)

    # Save reports
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = reports_dir / f"memory_leak_results_{timestamp}.json"
    text_file = reports_dir / f"memory_leak_report_{timestamp}.txt"

    test_suite.save_report(json_file, text_file)

    # Exit with appropriate code
    if (
        results["summary"]["critical_leaks"] > 0
        or results["summary"]["failed_tests"] > 0
    ):
        print("\n🚨 CRITICAL ISSUES DETECTED - Exiting with error code")
        sys.exit(1)
    elif results["summary"]["high_leaks"] > 0:
        print("\n⚠️ HIGH-SEVERITY ISSUES DETECTED - Review before deployment")
        sys.exit(2)
    else:
        print("\n✅ MEMORY LEAK DETECTION COMPLETE")
        sys.exit(0)


if __name__ == "__main__":
    main()
