"""
Metrics collection and monitoring for lead generation pipeline.
PRIORITY: P2 - Observability for production monitoring.

Task 11: Observability Dashboard
Tracks gate performance, API health, and pipeline metrics.
"""

import sqlite3
import json
import structlog
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from threading import Lock


logger = structlog.get_logger(__name__)


@dataclass
class MetricEvent:
    """Single metric event."""
    timestamp: str
    name: str
    value: float
    tags: Dict[str, str]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "name": self.name,
            "value": self.value,
            "tags": json.dumps(self.tags)
        }


class MetricsCollector:
    """
    Singleton metrics collector for pipeline observability.

    Tracks:
    - Gate pass/fail rates
    - API call latency and errors
    - LLM extraction quality
    - Overall pipeline metrics
    """

    _instance: Optional['MetricsCollector'] = None
    _lock = Lock()

    def __init__(self, db_path: str = "data/metrics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    @classmethod
    def get_instance(cls, db_path: str = "data/metrics.db") -> 'MetricsCollector':
        """Get singleton instance of metrics collector."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    def _init_database(self):
        """Initialize SQLite database for metrics storage."""
        with sqlite3.connect(self.db_path) as conn:
            # Metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for fast queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_name_timestamp
                ON metrics (name, timestamp DESC)
            """)

            logger.info("metrics_database_initialized", path=str(self.db_path))

    def increment(self, metric_name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.

        Args:
            metric_name: Name of the metric (e.g., "gate.category.pass")
            value: Value to add (default: 1.0)
            tags: Optional tags for grouping (e.g., {"gate": "category", "result": "pass"})

        Example:
            >>> metrics.increment("gate.category.pass", tags={"industry": "manufacturing"})
        """
        self._record_metric(metric_name, value, tags or {})

    def gauge(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric to a specific value.

        Args:
            metric_name: Name of the metric (e.g., "pipeline.total_leads")
            value: Current value
            tags: Optional tags for grouping

        Example:
            >>> metrics.gauge("pipeline.qualified_leads", 42)
        """
        self._record_metric(metric_name, value, tags or {})

    def histogram(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Record a histogram metric (for latency, timing, etc.).

        Args:
            metric_name: Name of the metric (e.g., "api.places.latency_ms")
            value: Measured value
            tags: Optional tags for grouping

        Example:
            >>> metrics.histogram("api.places.latency_ms", 245.3, tags={"status": "success"})
        """
        self._record_metric(metric_name, value, tags or {})

    def _record_metric(self, name: str, value: float, tags: Dict[str, str]):
        """Internal method to record metric to database."""
        try:
            event = MetricEvent(
                timestamp=datetime.utcnow().isoformat(),
                name=name,
                value=value,
                tags=tags
            )

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO metrics (timestamp, name, value, tags) VALUES (?, ?, ?, ?)",
                    (event.timestamp, event.name, event.value, json.dumps(event.tags))
                )

            logger.debug("metric_recorded", name=name, value=value, tags=tags)

        except Exception as e:
            logger.error("metric_recording_failed", name=name, error=str(e))

    def get_metric_stats(
        self,
        metric_name: str,
        hours: int = 24,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Get statistics for a metric over time period.

        Args:
            metric_name: Name of metric to query
            hours: Hours of history to include
            tags: Optional tag filters

        Returns:
            Dict with count, sum, mean, min, max, latest
        """
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT COUNT(*) as count, SUM(value) as sum,
                           AVG(value) as mean, MIN(value) as min,
                           MAX(value) as max
                    FROM metrics
                    WHERE name = ? AND timestamp >= ?
                """
                params = [metric_name, cutoff]

                # Add tag filters if provided
                if tags:
                    for key, val in tags.items():
                        query += " AND json_extract(tags, ?) = ?"
                        params.extend([f"$.{key}", val])

                cursor = conn.execute(query, params)
                row = cursor.fetchone()

                # Get latest value
                cursor = conn.execute(
                    """SELECT value FROM metrics
                       WHERE name = ? AND timestamp >= ?
                       ORDER BY timestamp DESC LIMIT 1""",
                    [metric_name, cutoff]
                )
                latest_row = cursor.fetchone()

                return {
                    "metric": metric_name,
                    "period_hours": hours,
                    "count": row[0] or 0,
                    "sum": row[1] or 0.0,
                    "mean": row[2] or 0.0,
                    "min": row[3] or 0.0,
                    "max": row[4] or 0.0,
                    "latest": latest_row[0] if latest_row else None,
                    "tags": tags
                }

        except Exception as e:
            logger.error("get_metric_stats_failed", metric=metric_name, error=str(e))
            return {"metric": metric_name, "error": str(e)}

    def get_gate_performance(self, hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """
        Get pass/fail rates for all gates.

        Args:
            hours: Hours of history to include

        Returns:
            Dict mapping gate names to performance stats
        """
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT name, tags, SUM(value) as total
                    FROM metrics
                    WHERE name LIKE 'gate.%.%' AND timestamp >= ?
                    GROUP BY name, tags
                """, [cutoff])

                # Organize by gate
                gates: Dict[str, Dict[str, float]] = {}
                for row in cursor.fetchall():
                    metric_name, tags_json, total = row
                    parts = metric_name.split('.')
                    if len(parts) >= 3:
                        gate_name = parts[1]  # gate.GATENAME.result
                        result = parts[2]  # pass or fail

                        if gate_name not in gates:
                            gates[gate_name] = {"pass": 0, "fail": 0}

                        gates[gate_name][result] = gates[gate_name].get(result, 0) + total

                # Calculate rates
                performance = {}
                for gate_name, counts in gates.items():
                    total = counts.get("pass", 0) + counts.get("fail", 0)
                    pass_rate = counts.get("pass", 0) / total if total > 0 else 0.0

                    performance[gate_name] = {
                        "total": int(total),
                        "passed": int(counts.get("pass", 0)),
                        "failed": int(counts.get("fail", 0)),
                        "pass_rate": pass_rate
                    }

                return performance

        except Exception as e:
            logger.error("get_gate_performance_failed", error=str(e))
            return {}

    def get_api_health(self, hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """
        Get API health metrics (latency, errors, success rate).

        Args:
            hours: Hours of history to include

        Returns:
            Dict mapping API names to health stats
        """
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                # Get API call metrics
                cursor = conn.execute("""
                    SELECT name, AVG(value) as avg_latency, COUNT(*) as count
                    FROM metrics
                    WHERE name LIKE 'api.%.latency_ms' AND timestamp >= ?
                    GROUP BY name
                """, [cutoff])

                apis: Dict[str, Dict[str, Any]] = {}
                for row in cursor.fetchall():
                    metric_name, avg_latency, count = row
                    api_name = metric_name.split('.')[1]  # api.APINAME.latency_ms

                    apis[api_name] = {
                        "avg_latency_ms": round(avg_latency, 2),
                        "total_calls": count,
                        "errors": 0,  # Default to 0
                        "success_rate": 1.0  # Default to 100% success
                    }

                # Get error counts
                cursor = conn.execute("""
                    SELECT name, SUM(value) as errors
                    FROM metrics
                    WHERE name LIKE 'api.%.error' AND timestamp >= ?
                    GROUP BY name
                """, [cutoff])

                for row in cursor.fetchall():
                    metric_name, errors = row
                    api_name = metric_name.split('.')[1]

                    if api_name in apis:
                        apis[api_name]["errors"] = int(errors)
                        total = apis[api_name]["total_calls"]
                        success_rate = (total - errors) / total if total > 0 else 0.0
                        apis[api_name]["success_rate"] = success_rate

                return apis

        except Exception as e:
            logger.error("get_api_health_failed", error=str(e))
            return {}

    def cleanup_old_metrics(self, days: int = 90):
        """
        Remove metrics older than specified days.

        Args:
            days: Number of days to retain
        """
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM metrics WHERE timestamp < ?",
                    [cutoff]
                )
                deleted = cursor.rowcount

            logger.info("metrics_cleaned_up", deleted=deleted, retention_days=days)

        except Exception as e:
            logger.error("cleanup_failed", error=str(e))


# Global metrics instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector.get_instance()
    return _metrics_collector


# Convenience functions
def track_gate_result(gate_name: str, passed: bool, tags: Optional[Dict[str, str]] = None):
    """
    Track gate pass/fail result.

    Args:
        gate_name: Name of the gate (e.g., "category", "revenue", "geo")
        passed: Whether the business passed the gate
        tags: Optional additional tags

    Example:
        >>> track_gate_result("category", True, {"industry": "manufacturing"})
    """
    metrics = get_metrics()
    result = "pass" if passed else "fail"
    metrics.increment(f"gate.{gate_name}.{result}", tags=tags)


def track_api_call(api_name: str, latency_ms: float, success: bool, tags: Optional[Dict[str, str]] = None):
    """
    Track API call latency and success.

    Args:
        api_name: Name of the API (e.g., "places", "openai", "yelp")
        latency_ms: Latency in milliseconds
        success: Whether the call succeeded
        tags: Optional additional tags

    Example:
        >>> track_api_call("places", 245.3, True, {"endpoint": "details"})
    """
    metrics = get_metrics()
    metrics.histogram(f"api.{api_name}.latency_ms", latency_ms, tags=tags)

    if not success:
        metrics.increment(f"api.{api_name}.error", tags=tags)


def track_pipeline_metric(metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """
    Track general pipeline metric.

    Args:
        metric_name: Name of the metric (e.g., "leads_processed", "qualified_count")
        value: Metric value
        tags: Optional additional tags

    Example:
        >>> track_pipeline_metric("leads_processed", 50, {"source": "yellowpages"})
    """
    metrics = get_metrics()
    metrics.gauge(f"pipeline.{metric_name}", value, tags=tags)
