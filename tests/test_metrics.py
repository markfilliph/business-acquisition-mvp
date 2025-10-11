"""
Tests for metrics collection and dashboard.
Validates observability system for production monitoring.
"""

import pytest
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta

from src.utils.metrics import (
    MetricsCollector,
    MetricEvent,
    get_metrics,
    track_gate_result,
    track_api_call,
    track_pipeline_metric
)


class TestMetricsCollector:
    """Test metrics collector functionality."""

    @pytest.fixture
    def temp_metrics(self):
        """Create temporary metrics collector."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        collector = MetricsCollector(db_path)
        yield collector

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    def test_metrics_database_initialized(self, temp_metrics):
        """Test that database is created and initialized."""
        assert temp_metrics.db_path.exists()

    def test_increment_counter(self, temp_metrics):
        """Test incrementing a counter metric."""
        temp_metrics.increment("test.counter", value=1.0)
        temp_metrics.increment("test.counter", value=2.0)

        stats = temp_metrics.get_metric_stats("test.counter", hours=1)
        assert stats['count'] == 2
        assert stats['sum'] == 3.0

    def test_gauge_metric(self, temp_metrics):
        """Test setting a gauge metric."""
        temp_metrics.gauge("test.gauge", 42.0)
        temp_metrics.gauge("test.gauge", 43.0)

        stats = temp_metrics.get_metric_stats("test.gauge", hours=1)
        assert stats['count'] == 2
        assert stats['latest'] == 43.0

    def test_histogram_metric(self, temp_metrics):
        """Test recording histogram values."""
        temp_metrics.histogram("test.latency", 100.0)
        temp_metrics.histogram("test.latency", 200.0)
        temp_metrics.histogram("test.latency", 150.0)

        stats = temp_metrics.get_metric_stats("test.latency", hours=1)
        assert stats['count'] == 3
        assert stats['mean'] == 150.0
        assert stats['min'] == 100.0
        assert stats['max'] == 200.0

    def test_metrics_with_tags(self, temp_metrics):
        """Test metrics with tag filtering."""
        temp_metrics.increment("test.tagged", tags={"env": "prod"})
        temp_metrics.increment("test.tagged", tags={"env": "dev"})

        # Filter by tag
        stats = temp_metrics.get_metric_stats("test.tagged", hours=1, tags={"env": "prod"})
        assert stats['count'] == 1

    def test_gate_performance_tracking(self, temp_metrics):
        """Test tracking gate pass/fail rates."""
        # Record some gate results
        temp_metrics.increment("gate.category.pass")
        temp_metrics.increment("gate.category.pass")
        temp_metrics.increment("gate.category.fail")

        temp_metrics.increment("gate.revenue.pass")
        temp_metrics.increment("gate.revenue.fail")
        temp_metrics.increment("gate.revenue.fail")

        performance = temp_metrics.get_gate_performance(hours=1)

        assert "category" in performance
        assert performance["category"]["passed"] == 2
        assert performance["category"]["failed"] == 1
        assert performance["category"]["pass_rate"] == pytest.approx(0.666, abs=0.01)

        assert "revenue" in performance
        assert performance["revenue"]["passed"] == 1
        assert performance["revenue"]["failed"] == 2
        assert performance["revenue"]["pass_rate"] == pytest.approx(0.333, abs=0.01)

    def test_api_health_tracking(self, temp_metrics):
        """Test tracking API health metrics."""
        # Record API calls
        temp_metrics.histogram("api.places.latency_ms", 245.0)
        temp_metrics.histogram("api.places.latency_ms", 255.0)
        temp_metrics.increment("api.places.error")

        temp_metrics.histogram("api.openai.latency_ms", 1200.0)
        temp_metrics.histogram("api.openai.latency_ms", 1300.0)

        health = temp_metrics.get_api_health(hours=1)

        assert "places" in health
        assert health["places"]["avg_latency_ms"] == 250.0
        assert health["places"]["total_calls"] == 2
        assert health["places"]["errors"] == 1
        assert health["places"]["success_rate"] == 0.5

        assert "openai" in health
        assert health["openai"]["avg_latency_ms"] == 1250.0
        assert health["openai"]["total_calls"] == 2

    def test_cleanup_old_metrics(self, temp_metrics):
        """Test cleanup of old metrics."""
        # Record metrics
        temp_metrics.increment("test.cleanup")
        temp_metrics.increment("test.cleanup")

        # Verify they exist
        stats_before = temp_metrics.get_metric_stats("test.cleanup", hours=1)
        assert stats_before['count'] == 2

        # Cleanup with 0 days retention (removes everything)
        temp_metrics.cleanup_old_metrics(days=0)

        # Verify they're gone
        stats_after = temp_metrics.get_metric_stats("test.cleanup", hours=1)
        assert stats_after['count'] == 0

    def test_singleton_pattern(self):
        """Test that MetricsCollector is a singleton."""
        instance1 = MetricsCollector.get_instance()
        instance2 = MetricsCollector.get_instance()

        assert instance1 is instance2


class TestMetricEvent:
    """Test MetricEvent dataclass."""

    def test_metric_event_creation(self):
        """Test creating a metric event."""
        event = MetricEvent(
            timestamp="2025-01-01T12:00:00",
            name="test.metric",
            value=42.0,
            tags={"env": "test"}
        )

        assert event.name == "test.metric"
        assert event.value == 42.0
        assert event.tags == {"env": "test"}

    def test_metric_event_to_dict(self):
        """Test converting metric event to dict."""
        event = MetricEvent(
            timestamp="2025-01-01T12:00:00",
            name="test.metric",
            value=42.0,
            tags={"env": "test"}
        )

        d = event.to_dict()
        assert d["name"] == "test.metric"
        assert d["value"] == 42.0
        assert '"env": "test"' in d["tags"]  # JSON string


class TestConvenienceFunctions:
    """Test convenience tracking functions."""

    @pytest.fixture
    def temp_metrics(self):
        """Create temporary metrics collector."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Replace global instance
        from src.utils import metrics as metrics_module
        original = metrics_module._metrics_collector
        metrics_module._metrics_collector = MetricsCollector(db_path)

        yield metrics_module._metrics_collector

        # Restore and cleanup
        metrics_module._metrics_collector = original
        Path(db_path).unlink(missing_ok=True)

    def test_track_gate_result_pass(self, temp_metrics):
        """Test tracking gate pass."""
        track_gate_result("category", True, {"industry": "manufacturing"})

        performance = temp_metrics.get_gate_performance(hours=1)
        assert "category" in performance
        assert performance["category"]["passed"] == 1

    def test_track_gate_result_fail(self, temp_metrics):
        """Test tracking gate fail."""
        track_gate_result("revenue", False, {"reason": "low_confidence"})

        performance = temp_metrics.get_gate_performance(hours=1)
        assert "revenue" in performance
        assert performance["revenue"]["failed"] == 1

    def test_track_api_call_success(self, temp_metrics):
        """Test tracking successful API call."""
        track_api_call("places", 245.5, True, {"endpoint": "details"})

        health = temp_metrics.get_api_health(hours=1)
        assert "places" in health
        assert health["places"]["avg_latency_ms"] == 245.5
        assert health["places"]["errors"] == 0

    def test_track_api_call_error(self, temp_metrics):
        """Test tracking failed API call."""
        track_api_call("openai", 1200.0, False, {"error": "rate_limit"})

        health = temp_metrics.get_api_health(hours=1)
        assert "openai" in health
        assert health["openai"]["errors"] == 1

    def test_track_pipeline_metric(self, temp_metrics):
        """Test tracking pipeline metric."""
        track_pipeline_metric("leads_processed", 50, {"source": "yellowpages"})

        stats = temp_metrics.get_metric_stats("pipeline.leads_processed", hours=1)
        assert stats['latest'] == 50


class TestMetricsIntegration:
    """Integration tests for metrics system."""

    @pytest.fixture
    def temp_metrics(self):
        """Create temporary metrics collector."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        collector = MetricsCollector(db_path)
        yield collector

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    def test_realistic_pipeline_metrics(self, temp_metrics):
        """Test realistic pipeline scenario."""
        # Simulate processing 10 leads
        for i in range(10):
            # Category gate
            temp_metrics.increment(f"gate.category.{'pass' if i < 8 else 'fail'}")

            # Revenue gate
            if i < 8:  # Only passed category gate
                temp_metrics.increment(f"gate.revenue.{'pass' if i < 6 else 'fail'}")

            # Geo gate
            if i < 6:  # Only passed category and revenue
                temp_metrics.increment(f"gate.geo.{'pass' if i < 5 else 'fail'}")

        # Check gate performance
        performance = temp_metrics.get_gate_performance(hours=1)

        assert performance["category"]["total"] == 10
        assert performance["category"]["pass_rate"] == 0.8

        assert performance["revenue"]["total"] == 8
        assert performance["revenue"]["pass_rate"] == 0.75

        assert performance["geo"]["total"] == 6
        assert performance["geo"]["pass_rate"] == pytest.approx(0.833, abs=0.01)

    def test_realistic_api_tracking(self, temp_metrics):
        """Test realistic API tracking."""
        # Simulate 10 Places API calls
        for i in range(10):
            latency = 200 + (i * 10)  # 200-290ms
            temp_metrics.histogram("api.places.latency_ms", latency)
            if i == 9:  # One error
                temp_metrics.increment("api.places.error")

        # Simulate 5 OpenAI calls
        for i in range(5):
            latency = 1000 + (i * 100)  # 1000-1400ms
            temp_metrics.histogram("api.openai.latency_ms", latency)

        health = temp_metrics.get_api_health(hours=1)

        assert health["places"]["total_calls"] == 10
        assert health["places"]["avg_latency_ms"] == 245.0
        assert health["places"]["errors"] == 1
        assert health["places"]["success_rate"] == 0.9

        assert health["openai"]["total_calls"] == 5
        assert health["openai"]["avg_latency_ms"] == 1200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
