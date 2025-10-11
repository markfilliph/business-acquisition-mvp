"""
Acceptance tests for revenue gate enforcement.
These tests define the "Definition of Done" for strict revenue gate enforcement.

Per validator requirements:
- ZERO businesses with confidence < 0.6 should be exported
- ZERO businesses without staff/benchmark signal should be exported
- All rejections must have clear reasons
"""

import pytest
from src.gates.revenue_gate import revenue_gate, validate_revenue_estimate, get_rejection_summary
from src.core.config import config


class TestAcceptanceNoLowConfidence:
    """Acceptance: Zero businesses with low confidence exported."""

    def test_no_business_below_threshold_passes(self):
        """Test that NO business with confidence < threshold passes."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD

        # Test a range of low confidence values
        low_confidences = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, threshold - 0.01]

        for confidence in low_confidences:
            # Even with staff count
            result = revenue_gate(confidence=confidence, staff_count=10)
            assert result.passes is False, (
                f"ACCEPTANCE FAILURE: Business with confidence={confidence:.2f} "
                f"passed gate (should fail below {threshold:.2f})"
            )

            # Even with benchmark match
            result = revenue_gate(confidence=confidence, benchmark_match=True)
            assert result.passes is False, (
                f"ACCEPTANCE FAILURE: Business with confidence={confidence:.2f} "
                f"and benchmark_match=True passed gate (should fail below {threshold:.2f})"
            )

            # Even with both signals
            result = revenue_gate(confidence=confidence, staff_count=10, benchmark_match=True)
            assert result.passes is False, (
                f"ACCEPTANCE FAILURE: Business with confidence={confidence:.2f} "
                f"with both signals passed gate (should fail below {threshold:.2f})"
            )

    def test_batch_low_confidence_all_fail(self):
        """Test that a batch of low confidence businesses all fail."""
        # Simulate 100 businesses with low confidence
        results = []
        for i in range(100):
            confidence = i / 200  # 0.0 to 0.5
            result = revenue_gate(confidence=confidence, staff_count=10)
            results.append(result)

        # Count passes (should be ZERO)
        passed_count = sum(1 for r in results if r.passes)

        assert passed_count == 0, (
            f"ACCEPTANCE FAILURE: {passed_count}/100 low-confidence businesses "
            f"passed gate (expected 0)"
        )

    def test_edge_case_just_below_threshold(self):
        """Test that confidence just 0.01 below threshold fails."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD
        edge_confidence = threshold - 0.01

        result = revenue_gate(confidence=edge_confidence, staff_count=10, benchmark_match=True)

        assert result.passes is False, (
            f"ACCEPTANCE FAILURE: Business with confidence={edge_confidence:.2f} "
            f"(just below threshold {threshold:.2f}) passed gate"
        )


class TestAcceptanceNoMissingSignal:
    """Acceptance: Zero businesses without staff/benchmark signal exported."""

    def test_no_business_without_signal_passes(self):
        """Test that NO business without staff or benchmark passes."""
        # Test with high confidences
        high_confidences = [0.6, 0.7, 0.8, 0.9, 1.0]

        for confidence in high_confidences:
            result = revenue_gate(confidence=confidence, staff_count=None, benchmark_match=False)

            assert result.passes is False, (
                f"ACCEPTANCE FAILURE: Business with confidence={confidence:.2f} "
                f"but no staff/benchmark signal passed gate"
            )

    def test_none_staff_without_benchmark_fails(self):
        """Test that None staff_count without benchmark fails."""
        result = revenue_gate(confidence=0.9, staff_count=None, benchmark_match=False)

        assert result.passes is False
        assert "no staff/benchmark signal" in result.rejection_reason.lower()

    def test_batch_no_signal_all_fail(self):
        """Test that a batch of businesses without signals all fail."""
        # Simulate 50 businesses with high confidence but no signal
        results = []
        for i in range(50):
            confidence = 0.6 + (i / 100)  # 0.6 to 1.1 (high confidence)
            result = revenue_gate(confidence=min(confidence, 1.0), staff_count=None, benchmark_match=False)
            results.append(result)

        # Count passes (should be ZERO)
        passed_count = sum(1 for r in results if r.passes)

        assert passed_count == 0, (
            f"ACCEPTANCE FAILURE: {passed_count}/50 no-signal businesses "
            f"passed gate (expected 0)"
        )

    def test_perfect_confidence_without_signal_fails(self):
        """Test that even perfect confidence fails without signal."""
        result = revenue_gate(confidence=1.0, staff_count=None, benchmark_match=False)

        assert result.passes is False, (
            "ACCEPTANCE FAILURE: Business with perfect confidence (1.0) "
            "but no signal passed gate"
        )


class TestAcceptanceRejectionReasons:
    """Acceptance: All rejections have clear reasons."""

    def test_all_rejections_have_reasons(self):
        """Test that all failed results have rejection reasons."""
        # Create various failing scenarios
        failing_cases = [
            (0.5, 10, False, "low confidence with staff"),
            (0.7, None, False, "high confidence without signal"),
            (0.4, None, False, "low confidence without signal"),
            (0.5, None, True, "low confidence with benchmark"),
        ]

        for confidence, staff, benchmark, description in failing_cases:
            result = revenue_gate(confidence=confidence, staff_count=staff, benchmark_match=benchmark)

            assert result.passes is False, f"Case '{description}' should fail"
            assert result.rejection_reason is not None, (
                f"ACCEPTANCE FAILURE: Rejected business ({description}) "
                f"has no rejection reason"
            )
            assert len(result.rejection_reason) > 0, (
                f"ACCEPTANCE FAILURE: Rejected business ({description}) "
                f"has empty rejection reason"
            )

    def test_rejection_reasons_are_specific(self):
        """Test that rejection reasons are specific and actionable."""
        # Low confidence case
        low_conf_result = revenue_gate(confidence=0.5, staff_count=10)
        assert "confidence" in low_conf_result.rejection_reason.lower()
        assert "0.5" in low_conf_result.rejection_reason or "0.50" in low_conf_result.rejection_reason

        # No signal case
        no_signal_result = revenue_gate(confidence=0.7, staff_count=None)
        assert "staff" in no_signal_result.rejection_reason.lower() or "benchmark" in no_signal_result.rejection_reason.lower()

    def test_rejection_reasons_include_threshold(self):
        """Test that low confidence rejections include threshold value."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD
        result = revenue_gate(confidence=0.5, staff_count=10)

        # Should mention the threshold
        assert str(threshold) in result.rejection_reason or f"{threshold:.2f}" in result.rejection_reason


class TestAcceptanceRevenueRange:
    """Acceptance: Revenue estimates outside target range are rejected."""

    def test_revenue_below_minimum_rejected(self):
        """Test that revenue below minimum is rejected."""
        min_revenue = config.TARGET_REVENUE_MIN
        low_revenues = [
            min_revenue - 1,
            min_revenue - 100_000,
            min_revenue - 500_000,
            min_revenue / 2
        ]

        for revenue in low_revenues:
            result = validate_revenue_estimate(
                revenue_estimate=revenue,
                confidence=0.7,
                staff_count=10
            )

            assert result.passes is False, (
                f"ACCEPTANCE FAILURE: Revenue ${revenue:,.0f} "
                f"(below minimum ${min_revenue:,.0f}) passed gate"
            )

    def test_revenue_above_maximum_rejected(self):
        """Test that revenue above maximum is rejected."""
        max_revenue = config.TARGET_REVENUE_MAX
        high_revenues = [
            max_revenue + 1,
            max_revenue + 100_000,
            max_revenue + 500_000,
            max_revenue * 2
        ]

        for revenue in high_revenues:
            result = validate_revenue_estimate(
                revenue_estimate=revenue,
                confidence=0.7,
                staff_count=10
            )

            assert result.passes is False, (
                f"ACCEPTANCE FAILURE: Revenue ${revenue:,.0f} "
                f"(above maximum ${max_revenue:,.0f}) passed gate"
            )

    def test_revenue_in_range_passes(self):
        """Test that revenue in target range passes (with valid confidence/signal)."""
        min_revenue = config.TARGET_REVENUE_MIN
        max_revenue = config.TARGET_REVENUE_MAX

        # Test at boundaries and middle
        valid_revenues = [
            min_revenue,
            (min_revenue + max_revenue) / 2,
            max_revenue
        ]

        for revenue in valid_revenues:
            result = validate_revenue_estimate(
                revenue_estimate=revenue,
                confidence=0.7,
                staff_count=10
            )

            assert result.passes is True, (
                f"ACCEPTANCE FAILURE: Valid revenue ${revenue:,.0f} "
                f"(in range ${min_revenue:,.0f}-${max_revenue:,.0f}) failed gate"
            )


class TestAcceptanceGoldenBadCases:
    """Acceptance: Test against golden set of known bad cases."""

    def test_golden_bad_case_1_low_confidence_only(self):
        """Golden bad case: Low confidence with staff (should fail)."""
        result = revenue_gate(confidence=0.45, staff_count=8)

        assert result.passes is False
        assert "confidence too low" in result.rejection_reason.lower()

    def test_golden_bad_case_2_no_signal(self):
        """Golden bad case: High confidence but no signal (should fail)."""
        result = revenue_gate(confidence=0.85, staff_count=None, benchmark_match=False)

        assert result.passes is False
        assert "no staff/benchmark signal" in result.rejection_reason.lower()

    def test_golden_bad_case_3_barely_below_threshold(self):
        """Golden bad case: Confidence just below threshold (should fail)."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD
        result = revenue_gate(confidence=threshold - 0.001, staff_count=15)

        assert result.passes is False

    def test_golden_good_case_1_minimum_viable(self):
        """Golden good case: Exactly at threshold with staff (should pass)."""
        threshold = config.REVENUE_CONFIDENCE_THRESHOLD
        result = revenue_gate(confidence=threshold, staff_count=1)

        assert result.passes is True

    def test_golden_good_case_2_high_conf_benchmark(self):
        """Golden good case: High confidence with benchmark (should pass)."""
        result = revenue_gate(confidence=0.9, benchmark_match=True)

        assert result.passes is True


class TestAcceptanceStatistics:
    """Acceptance: Validate rejection statistics are accurate."""

    def test_rejection_statistics_accuracy(self):
        """Test that rejection statistics accurately reflect results."""
        # Create known distribution
        results = [
            revenue_gate(0.7, 10),   # Pass
            revenue_gate(0.8, 15),   # Pass
            revenue_gate(0.5, 10),   # Fail: low confidence
            revenue_gate(0.7, None), # Fail: no signal
            revenue_gate(0.4, None), # Fail: both issues
            revenue_gate(0.9, 20),   # Pass
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 6
        assert summary["passed"] == 3
        assert summary["failed"] == 3
        assert summary["pass_rate"] == 0.5
        assert summary["rejection_rate"] == 0.5

        # Check specific rejection reasons
        assert summary["rejections_by_reason"]["confidence_too_low"] >= 2
        assert summary["rejections_by_reason"]["no_staff_benchmark_signal"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "acceptance"])
