"""Memory leak detection utilities for YTArchive services."""

import gc
import tracemalloc
import asyncio
import psutil
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import asynccontextmanager
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Snapshot of memory usage at a specific point in time."""

    timestamp: float
    rss_mb: float = 0.0  # Resident Set Size in MB
    vms_mb: float = 0.0  # Virtual Memory Size in MB
    cpu_percent: float = 0.0
    open_files: int = 0
    tracemalloc_top: List[str] = field(default_factory=list)
    python_objects: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Post-init to capture current memory state."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            self.rss_mb = memory_info.rss / 1024 / 1024
            self.vms_mb = memory_info.vms / 1024 / 1024
            self.cpu_percent = process.cpu_percent()
            try:
                self.open_files = len(process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                self.open_files = 0

            # Capture tracemalloc data if available
            if tracemalloc.is_tracing():
                try:
                    snapshot = tracemalloc.take_snapshot()
                    top_stats = snapshot.statistics("lineno")[:10]
                    self.tracemalloc_top = [str(stat) for stat in top_stats]
                except Exception:
                    self.tracemalloc_top = []

            # Count Python objects by type
            self.python_objects = self._count_objects()
        except Exception as e:
            logger.warning(f"Failed to capture memory snapshot: {e}")
            # Set defaults if capture fails
            self.rss_mb = 0.0
            self.vms_mb = 0.0
            self.cpu_percent = 0.0
            self.open_files = 0

    def _count_objects(self) -> Dict[str, int]:
        """Count Python objects by type."""
        object_counts: Dict[str, int] = {}
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            object_counts[obj_type] = object_counts.get(obj_type, 0) + 1
        return object_counts


@dataclass
class MemoryLeakReport:
    """Report of potential memory leaks."""

    service_name: str
    test_name: str
    start_snapshot: MemorySnapshot
    end_snapshot: MemorySnapshot
    peak_snapshot: Optional[MemorySnapshot] = None
    leak_detected: bool = False
    leak_severity: str = "none"  # none, low, medium, high, critical
    recommendations: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Analyze snapshots for memory leaks."""
        self._analyze_memory_growth()

    def _analyze_memory_growth(self):
        """Analyze memory growth patterns."""
        rss_growth = self.end_snapshot.rss_mb - self.start_snapshot.rss_mb
        # VMS growth calculation available if needed
        # vms_growth = self.end_snapshot.vms_mb - self.start_snapshot.vms_mb
        file_growth = self.end_snapshot.open_files - self.start_snapshot.open_files

        # Memory growth thresholds (in MB)
        CRITICAL_THRESHOLD = 100
        HIGH_THRESHOLD = 50
        MEDIUM_THRESHOLD = 20
        LOW_THRESHOLD = 10

        # Analyze RSS growth
        if rss_growth > CRITICAL_THRESHOLD:
            self.leak_detected = True
            self.leak_severity = "critical"
            self.recommendations.append(
                f"CRITICAL: RSS memory grew by {rss_growth:.1f}MB"
            )
        elif rss_growth > HIGH_THRESHOLD:
            self.leak_detected = True
            self.leak_severity = "high"
            self.recommendations.append(f"HIGH: RSS memory grew by {rss_growth:.1f}MB")
        elif rss_growth > MEDIUM_THRESHOLD:
            self.leak_detected = True
            self.leak_severity = "medium"
            self.recommendations.append(
                f"MEDIUM: RSS memory grew by {rss_growth:.1f}MB"
            )
        elif rss_growth > LOW_THRESHOLD:
            self.leak_detected = True
            self.leak_severity = "low"
            self.recommendations.append(f"LOW: RSS memory grew by {rss_growth:.1f}MB")

        # Analyze file handle growth
        if file_growth > 10:
            self.leak_detected = True
            self.recommendations.append(
                f"File handle leak: {file_growth} files not closed"
            )

        # Analyze object growth
        self._analyze_object_growth()

    def _analyze_object_growth(self):
        """Analyze Python object growth."""
        for obj_type in self.end_snapshot.python_objects:
            start_count = self.start_snapshot.python_objects.get(obj_type, 0)
            end_count = self.end_snapshot.python_objects[obj_type]
            growth = end_count - start_count

            # Flag significant object growth
            if growth > 1000:  # More than 1000 new objects of same type
                self.leak_detected = True
                self.recommendations.append(
                    f"Object leak: {growth} new {obj_type} objects"
                )


class MemoryLeakDetector:
    """Main memory leak detection system."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.snapshots: List[MemorySnapshot] = []
        self.is_tracing = False
        self.reports: List[MemoryLeakReport] = []

    def start_tracing(self):
        """Start memory tracing."""
        if not self.is_tracing:
            tracemalloc.start()
            self.is_tracing = True
            logger.info(f"Started memory tracing for {self.service_name}")

    def stop_tracing(self):
        """Stop memory tracing."""
        if self.is_tracing:
            tracemalloc.stop()
            self.is_tracing = False
            logger.info(f"Stopped memory tracing for {self.service_name}")

    def take_snapshot(self, label: str = "") -> MemorySnapshot:
        """Take a memory snapshot."""
        snapshot = MemorySnapshot(timestamp=time.time())
        self.snapshots.append(snapshot)

        logger.info(
            f"Memory snapshot [{label}]: "
            f"RSS={snapshot.rss_mb:.1f}MB, "
            f"VMS={snapshot.vms_mb:.1f}MB, "
            f"Files={snapshot.open_files}"
        )

        return snapshot

    def analyze_test(
        self,
        test_name: str,
        start_snapshot: MemorySnapshot,
        end_snapshot: MemorySnapshot,
    ) -> MemoryLeakReport:
        """Analyze a test for memory leaks."""
        peak_snapshot = self._find_peak_snapshot(start_snapshot, end_snapshot)

        report = MemoryLeakReport(
            service_name=self.service_name,
            test_name=test_name,
            start_snapshot=start_snapshot,
            end_snapshot=end_snapshot,
            peak_snapshot=peak_snapshot,
        )

        self.reports.append(report)
        return report

    def _find_peak_snapshot(
        self, start: MemorySnapshot, end: MemorySnapshot
    ) -> Optional[MemorySnapshot]:
        """Find the peak memory usage between start and end snapshots."""
        relevant_snapshots = [
            s for s in self.snapshots if start.timestamp <= s.timestamp <= end.timestamp
        ]

        if not relevant_snapshots:
            return None

        return max(relevant_snapshots, key=lambda s: s.rss_mb)

    def generate_report(self) -> str:
        """Generate a comprehensive memory leak report."""
        report_lines = [
            "=== MEMORY LEAK DETECTION REPORT ===",
            f"Service: {self.service_name}",
            f"Total Tests: {len(self.reports)}",
            f"Leaks Detected: {sum(1 for r in self.reports if r.leak_detected)}",
            "",
        ]

        # Summary by severity
        severity_counts: Dict[str, int] = {}
        for report in self.reports:
            if report.leak_detected:
                severity_counts[report.leak_severity] = (
                    severity_counts.get(report.leak_severity, 0) + 1
                )

        if severity_counts:
            report_lines.append("LEAK SEVERITY SUMMARY:")
            for severity in ["critical", "high", "medium", "low"]:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    report_lines.append(f"  {severity.upper()}: {count} tests")
            report_lines.append("")

        # Detailed reports
        for report in self.reports:
            if report.leak_detected:
                report_lines.extend(
                    [
                        f"TEST: {report.test_name}",
                        f"  Severity: {report.leak_severity.upper()}",
                        f"  Memory Growth: {report.end_snapshot.rss_mb - report.start_snapshot.rss_mb:.1f}MB",
                        f"  File Handle Growth: {report.end_snapshot.open_files - report.start_snapshot.open_files}",
                        "  Recommendations:",
                    ]
                )
                for rec in report.recommendations:
                    report_lines.append(f"    - {rec}")
                report_lines.append("")

        return "\n".join(report_lines)

    def save_report(self, filepath: Path):
        """Save report to file."""
        with open(filepath, "w") as f:
            f.write(self.generate_report())
        logger.info(f"Memory leak report saved to {filepath}")


@asynccontextmanager
async def memory_leak_test(detector: MemoryLeakDetector, test_name: str):
    """Context manager for memory leak testing."""
    # Force garbage collection before test
    gc.collect()

    start_snapshot = detector.take_snapshot(f"{test_name}_start")

    try:
        yield detector
    finally:
        # Force garbage collection after test
        gc.collect()

        end_snapshot = detector.take_snapshot(f"{test_name}_end")
        report = detector.analyze_test(test_name, start_snapshot, end_snapshot)

        if report.leak_detected:
            logger.warning(
                f"Memory leak detected in {test_name}: {report.leak_severity}"
            )
        else:
            logger.info(f"No memory leaks detected in {test_name}")


def memory_profile(func: Callable) -> Callable:
    """Decorator to profile memory usage of a function."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        detector = MemoryLeakDetector(f"{func.__module__}.{func.__name__}")
        detector.start_tracing()

        try:
            async with memory_leak_test(detector, func.__name__):
                result = await func(*args, **kwargs)
                return result
        finally:
            detector.stop_tracing()

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        detector = MemoryLeakDetector(f"{func.__module__}.{func.__name__}")
        detector.start_tracing()

        try:
            gc.collect()
            start_snapshot = detector.take_snapshot(f"{func.__name__}_start")

            result = func(*args, **kwargs)

            gc.collect()
            end_snapshot = detector.take_snapshot(f"{func.__name__}_end")

            report = detector.analyze_test(func.__name__, start_snapshot, end_snapshot)
            if report.leak_detected:
                logger.warning(
                    f"Memory leak detected in {func.__name__}: {report.leak_severity}"
                )

            return result
        finally:
            detector.stop_tracing()

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class ResourceMonitor:
    """Monitor resource usage patterns."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.monitoring = False
        self.samples: List[MemorySnapshot] = []
        self.monitor_task: Optional[asyncio.Task] = None

    async def start_monitoring(self, interval: float = 5.0):
        """Start continuous monitoring."""
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info(f"Started continuous monitoring for {self.service_name}")

    async def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped monitoring for {self.service_name}")

    async def _monitor_loop(self, interval: float):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                snapshot = MemorySnapshot(timestamp=time.time())
                self.samples.append(snapshot)

                # Keep only last 1000 samples to prevent memory growth
                if len(self.samples) > 1000:
                    self.samples = self.samples[-1000:]

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        if not self.samples:
            return {}

        rss_values = [s.rss_mb for s in self.samples]
        file_counts = [s.open_files for s in self.samples]

        return {
            "service_name": self.service_name,
            "sample_count": len(self.samples),
            "duration_minutes": (self.samples[-1].timestamp - self.samples[0].timestamp)
            / 60,
            "memory_stats": {
                "rss_min_mb": min(rss_values),
                "rss_max_mb": max(rss_values),
                "rss_avg_mb": sum(rss_values) / len(rss_values),
                "rss_growth_mb": rss_values[-1] - rss_values[0],
            },
            "file_stats": {
                "files_min": min(file_counts),
                "files_max": max(file_counts),
                "files_avg": sum(file_counts) / len(file_counts),
                "files_growth": file_counts[-1] - file_counts[0],
            },
        }
