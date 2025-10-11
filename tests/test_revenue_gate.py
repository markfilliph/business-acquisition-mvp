"""
Tests for strict revenue gate enforcement.
Validates that revenue gate enforces all requirements without "warn and pass" logic.
"""

import pytest
from src.gates.revenue_gate import (
    revenue_gate,
    validate_revenue_estimate,
    get_rejection_summary,
    RevenueGateResult
)
from src.core.config import config


class TestRevenueGateBasics:
    """Test basic revenue gate functionality."""

    def test_high_confidence_with_staff_passes(self):
        """Test that high confidence + staff count passes gate."""
        result = revenue_gate(confidence=0.7, staff_count=10)

        assert result.passes is True
        assert result.confidence == 0.7
        assert result.has_staff_signal is True
        assert result.rejection_reason is None

    def test_high_confidence_with_benchmark_passes(self):
        """Test that high confidence + benchmark match passes gate."""
        result = revenue_gate(confidence=0.7, benchmark_match=True)

        assert result.passes is True
        assert result.confidence == 0.7
        assert result.has_benchmark_signal is True
        assert result.rejection_reason is None

    def test_exact_threshold_confidence_passes(self):
        """Test that confidence exactly at threshold passes."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD
        result = revenue_gate(confidence=threshold, staff_count=10)

        assert result.passes is True

    def test_just_below_threshold_fails(self):
        """Test that confidence just below threshold fails."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD
        result = revenue_gate(confidence=threshold - 0.01, staff_count=10)

        assert result.passes is False
        assert "confidence too low" in result.rejection_reason.lower()


class TestRevenueGateStrictEnforcement:
    """Test strict enforcement - no warn and pass."""

    def test_low_confidence_fails_even_with_staff(self):
        """Test that low confidence fails even with staff count."""
        result = revenue_gate(confidence=0.5, staff_count=10)

        assert result.passes is False
        assert result.has_staff_signal is True
        assert "confidence too low" in result.rejection_reason.lower()

    def test_low_confidence_fails_even_with_benchmark(self):
        """Test that low confidence fails even with benchmark match."""
        result = revenue_gate(confidence=0.5, benchmark_match=True)

        assert result.passes is False
        assert result.has_benchmark_signal is True
        assert "confidence too low" in result.rejection_reason.lower()

    def test_high_confidence_fails_without_signal(self):
        """Test that high confidence fails without staff or benchmark."""
        result = revenue_gate(confidence=0.7)

        assert result.passes is False
        assert result.has_staff_signal is False
        assert result.has_benchmark_signal is False
        assert "no staff/benchmark signal" in result.rejection_reason.lower()

    def test_high_confidence_fails_with_zero_staff(self):
        """Test that staff_count=0 is treated as a signal (business exists)."""
        result = revenue_gate(confidence=0.7, staff_count=0)

        # staff_count=0 is still a signal (we know the count)
        assert result.passes is True
        assert result.has_staff_signal is True

    def test_none_staff_count_is_not_a_signal(self):
        """Test that None staff_count is not treated as a signal."""
        result = revenue_gate(confidence=0.7, staff_count=None)

        assert result.passes is False
        assert result.has_staff_signal is False


class TestRevenueGateRejectionReasons:
    """Test that rejection reasons are logged correctly."""

    def test_low_confidence_rejection_reason(self):
        """Test rejection reason for low confidence."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD
        result = revenue_gate(confidence=0.5, staff_count=10)

        assert result.passes is False
        assert result.rejection_reason is not None
        assert "confidence too low" in result.rejection_reason.lower()
        assert "0.50" in result.rejection_reason
        assert str(threshold) in result.rejection_reason

    def test_no_signal_rejection_reason(self):
        """Test rejection reason for missing staff/benchmark signal."""
        result = revenue_gate(confidence=0.7)

        assert result.passes is False
        assert result.rejection_reason is not None
        assert "no staff/benchmark signal" in result.rejection_reason.lower()

    def test_rejection_reason_includes_confidence(self):
        """Test that rejection reason includes confidence value."""
        result = revenue_gate(confidence=0.7, staff_count=None)

        assert "0.70" in result.rejection_reason


class TestRevenueGateSignals:
    """Test staff and benchmark signal detection."""

    def test_staff_signal_detected(self):
        """Test that staff count is detected as a signal."""
        result = revenue_gate(confidence=0.7, staff_count=5)

        assert result.has_staff_signal is True

    def test_benchmark_signal_detected(self):
        """Test that benchmark match is detected as a signal."""
        result = revenue_gate(confidence=0.7, benchmark_match=True)

        assert result.has_benchmark_signal is True

    def test_both_signals_detected(self):
        """Test that both signals can be present."""
        result = revenue_gate(confidence=0.7, staff_count=5, benchmark_match=True)

        assert result.has_staff_signal is True
        assert result.has_benchmark_signal is True
        assert result.passes is True

    def test_neither_signal_detected(self):
        """Test that absence of both signals is detected."""
        result = revenue_gate(confidence=0.7, staff_count=None, benchmark_match=False)

        assert result.has_staff_signal is False
        assert result.has_benchmark_signal is False
        assert result.passes is False


class TestValidateRevenueEstimate:
    """Test revenue estimate validation with range checking."""

    def test_revenue_in_range_passes(self):
        """Test that revenue in target range passes."""
        min_rev = config.TARGET_REVENUE_MIN
        max_rev = config.TARGET_REVENUE_MAX
        mid_revenue = (min_rev + max_rev) / 2

        result = validate_revenue_estimate(
            revenue_estimate=mid_revenue,
            confidence=0.7,
            staff_count=10
        )

        assert result.passes is True

    def test_revenue_below_min_fails(self):
        """Test that revenue below minimum fails."""
        min_rev = config.TARGET_REVENUE_MIN
        low_revenue = min_rev - 100_000

        result = validate_revenue_estimate(
            revenue_estimate=low_revenue,
            confidence=0.7,
            staff_count=10
        )

        assert result.passes is False
        assert "outside target range" in result.rejection_reason.lower()

    def test_revenue_above_max_fails(self):
        """Test that revenue above maximum fails."""
        max_rev = config.TARGET_REVENUE_MAX
        high_revenue = max_rev + 100_000

        result = validate_revenue_estimate(
            revenue_estimate=high_revenue,
            confidence=0.7,
            staff_count=10
        )

        assert result.passes is False
        assert "outside target range" in result.rejection_reason.lower()

    def test_revenue_at_min_boundary_passes(self):
        """Test that revenue exactly at minimum passes."""
        min_rev = config.TARGET_REVENUE_MIN

        result = validate_revenue_estimate(
            revenue_estimate=min_rev,
            confidence=0.7,
            staff_count=10
        )

        assert result.passes is True

    def test_revenue_at_max_boundary_passes(self):
        """Test that revenue exactly at maximum passes."""
        max_rev = config.TARGET_REVENUE_MAX

        result = validate_revenue_estimate(
            revenue_estimate=max_rev,
            confidence=0.7,
            staff_count=10
        )

        assert result.passes is True


class TestRevenueGateResult:
    """Test RevenueGateResult dataclass."""

    def test_result_to_dict(self):
        """Test that result converts to dict correctly."""
        result = RevenueGateResult(
            passes=True,
            confidence=0.7,
            has_staff_signal=True,
            has_benchmark_signal=False,
            rejection_reason=None
        )

        result_dict = result.to_dict()

        assert result_dict["passes"] is True
        assert result_dict["confidence"] == 0.7
        assert result_dict["has_staff_signal"] is True
        assert result_dict["has_benchmark_signal"] is False
        assert result_dict["rejection_reason"] is None

    def test_failed_result_to_dict(self):
        """Test that failed result converts to dict with reason."""
        result = RevenueGateResult(
            passes=False,
            confidence=0.5,
            has_staff_signal=False,
            has_benchmark_signal=False,
            rejection_reason="Confidence too low"
        )

        result_dict = result.to_dict()

        assert result_dict["passes"] is False
        assert result_dict["rejection_reason"] == "Confidence too low"


class TestRejectionSummary:
    """Test rejection summary statistics."""

    def test_all_passed_summary(self):
        """Test summary when all results pass."""
        results = [
            revenue_gate(confidence=0.7, staff_count=10),
            revenue_gate(confidence=0.8, benchmark_match=True),
            revenue_gate(confidence=0.9, staff_count=5)
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 3
        assert summary["passed"] == 3
        assert summary["failed"] == 0
        assert summary["pass_rate"] == 1.0
        assert summary["rejection_rate"] == 0.0

    def test_all_failed_summary(self):
        """Test summary when all results fail."""
        results = [
            revenue_gate(confidence=0.5, staff_count=10),  # Low confidence
            revenue_gate(confidence=0.7, staff_count=None),  # No signal
            revenue_gate(confidence=0.4, benchmark_match=False)  # Low conf + no signal
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 3
        assert summary["passed"] == 0
        assert summary["failed"] == 3
        assert summary["pass_rate"] == 0.0
        assert summary["rejection_rate"] == 1.0

    def test_mixed_results_summary(self):
        """Test summary with mixed pass/fail results."""
        results = [
            revenue_gate(confidence=0.7, staff_count=10),  # Pass
            revenue_gate(confidence=0.5, staff_count=5),   # Fail: low confidence
            revenue_gate(confidence=0.8, staff_count=None),  # Fail: no signal
            revenue_gate(confidence=0.9, benchmark_match=True)  # Pass
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 4
        assert summary["passed"] == 2
        assert summary["failed"] == 2
        assert summary["pass_rate"] == 0.5
        assert summary["rejection_rate"] == 0.5
        assert summary["rejections_by_reason"]["confidence_too_low"] == 1
        assert summary["rejections_by_reason"]["no_staff_benchmark_signal"] == 1

    def test_empty_results_summary(self):
        """Test summary with empty results list."""
        results = []
        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 0
        assert summary["pass_rate"] == 0.0
        assert summary["rejection_rate"] == 0.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_confidence_fails(self):
        """Test that zero confidence fails."""
        result = revenue_gate(confidence=0.0, staff_count=10)

        assert result.passes is False

    def test_perfect_confidence_passes(self):
        """Test that perfect confidence (1.0) passes with signal."""
        result = revenue_gate(confidence=1.0, staff_count=10)

        assert result.passes is True

    def test_negative_staff_count_is_signal(self):
        """Test that negative staff count (invalid but present) is treated as signal."""
        # Note: This is a data quality issue, but we still treat it as "we have data"
        result = revenue_gate(confidence=0.7, staff_count=-1)

        assert result.has_staff_signal is True
        # Gate passes because we have a signal (even if data is invalid)
        assert result.passes is True

    def test_very_large_staff_count(self):
        """Test that very large staff count still passes."""
        result = revenue_gate(confidence=0.7, staff_count=10000)

        assert result.passes is True
        assert result.has_staff_signal is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
