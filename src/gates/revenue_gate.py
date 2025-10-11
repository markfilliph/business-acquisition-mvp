"""
Revenue gate for business qualification.
PRIORITY: P1 - Strict enforcement of revenue requirements per validator feedback.

Task 7: Strict Revenue Gate Enforcement
- Requires confidence >= threshold (from config)
- Requires staff signal OR benchmark match
- No "warn and pass" logic - strict enforcement only
"""

from dataclasses import dataclass
from typing import Optional
import structlog

from ..core.config import config

logger = structlog.get_logger(__name__)


@dataclass
class RevenueGateResult:
    """Result of revenue gate validation."""
    passes: bool
    confidence: float
    has_staff_signal: bool
    has_benchmark_signal: bool
    rejection_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage."""
        return {
            "passes": self.passes,
            "confidence": self.confidence,
            "has_staff_signal": self.has_staff_signal,
            "has_benchmark_signal": self.has_benchmark_signal,
            "rejection_reason": self.rejection_reason
        }


def revenue_gate(
    confidence: float,
    staff_count: Optional[int] = None,
    benchmark_match: bool = False,
    revenue_estimate: Optional[float] = None
) -> RevenueGateResult:
    """
    Validate business against revenue gate requirements.

    STRICT ENFORCEMENT - No "warn and pass" logic.

    Requirements for passing:
    1. confidence >= config.REVENUE_CONFIDENCE_THRESHOLD (default 0.6)
    2. AND (staff_count is not None OR benchmark_match is True)

    Args:
        confidence: Revenue confidence score (0.0-1.0)
        staff_count: Number of staff (None if unknown)
        benchmark_match: Whether revenue matches industry benchmark
        revenue_estimate: Estimated revenue (optional, for logging)

    Returns:
        RevenueGateResult with pass/fail and rejection reason

    Examples:
        >>> # Pass: High confidence + staff signal
        >>> result = revenue_gate(confidence=0.7, staff_count=10)
        >>> assert result.passes is True

        >>> # Fail: Low confidence
        >>> result = revenue_gate(confidence=0.5, staff_count=10)
        >>> assert result.passes is False
        >>> assert "confidence too low" in result.rejection_reason

        >>> # Fail: No staff or benchmark signal
        >>> result = revenue_gate(confidence=0.7)
        >>> assert result.passes is False
        >>> assert "no staff/benchmark signal" in result.rejection_reason
    """
    threshold = config.REVENUE_CONFIDENCE_THRESHOLD

    # Check confidence threshold
    if confidence < threshold:
        rejection_reason = f"Revenue confidence too low: {confidence:.2f} < {threshold:.2f}"
        logger.info(
            "revenue_gate_failed",
            reason="confidence_too_low",
            confidence=confidence,
            threshold=threshold,
            staff_count=staff_count,
            benchmark_match=benchmark_match
        )
        return RevenueGateResult(
            passes=False,
            confidence=confidence,
            has_staff_signal=staff_count is not None,
            has_benchmark_signal=benchmark_match,
            rejection_reason=rejection_reason
        )

    # Check for staff or benchmark signal
    has_staff_signal = staff_count is not None
    has_benchmark_signal = benchmark_match

    if not has_staff_signal and not has_benchmark_signal:
        rejection_reason = (
            f"No staff/benchmark signal (confidence={confidence:.2f} is sufficient, "
            f"but requires either staff_count or benchmark_match)"
        )
        logger.info(
            "revenue_gate_failed",
            reason="no_staff_benchmark_signal",
            confidence=confidence,
            staff_count=staff_count,
            benchmark_match=benchmark_match
        )
        return RevenueGateResult(
            passes=False,
            confidence=confidence,
            has_staff_signal=has_staff_signal,
            has_benchmark_signal=has_benchmark_signal,
            rejection_reason=rejection_reason
        )

    # Passed all checks
    logger.info(
        "revenue_gate_passed",
        confidence=confidence,
        staff_count=staff_count,
        benchmark_match=benchmark_match,
        revenue_estimate=revenue_estimate
    )

    return RevenueGateResult(
        passes=True,
        confidence=confidence,
        has_staff_signal=has_staff_signal,
        has_benchmark_signal=has_benchmark_signal,
        rejection_reason=None
    )


def validate_revenue_estimate(
    revenue_estimate: float,
    confidence: float,
    staff_count: Optional[int] = None,
    benchmark_match: bool = False
) -> RevenueGateResult:
    """
    Validate a complete revenue estimate against gate requirements.

    This is a convenience wrapper around revenue_gate() that includes
    revenue range validation.

    Args:
        revenue_estimate: Estimated revenue in USD
        confidence: Confidence score (0.0-1.0)
        staff_count: Number of staff (optional)
        benchmark_match: Whether revenue matches benchmark (optional)

    Returns:
        RevenueGateResult with pass/fail and rejection reason
    """
    # First check if revenue is in target range
    min_revenue = config.TARGET_REVENUE_MIN
    max_revenue = config.TARGET_REVENUE_MAX

    if revenue_estimate < min_revenue or revenue_estimate > max_revenue:
        rejection_reason = (
            f"Revenue ${revenue_estimate:,.0f} outside target range "
            f"${min_revenue:,.0f}-${max_revenue:,.0f}"
        )
        logger.info(
            "revenue_gate_failed",
            reason="revenue_out_of_range",
            revenue_estimate=revenue_estimate,
            min_revenue=min_revenue,
            max_revenue=max_revenue
        )
        return RevenueGateResult(
            passes=False,
            confidence=confidence,
            has_staff_signal=staff_count is not None,
            has_benchmark_signal=benchmark_match,
            rejection_reason=rejection_reason
        )

    # Then check confidence and signals
    return revenue_gate(
        confidence=confidence,
        staff_count=staff_count,
        benchmark_match=benchmark_match,
        revenue_estimate=revenue_estimate
    )


def get_rejection_summary(results: list[RevenueGateResult]) -> dict:
    """
    Get summary statistics of revenue gate rejections.

    Args:
        results: List of RevenueGateResult objects

    Returns:
        Dict with rejection statistics

    Example:
        >>> results = [revenue_gate(0.5, 10), revenue_gate(0.7, None)]
        >>> summary = get_rejection_summary(results)
        >>> summary['total_checked']
        2
        >>> summary['rejection_rate']
        1.0
    """
    total = len(results)
    passed = sum(1 for r in results if r.passes)
    failed = total - passed

    # Categorize rejection reasons
    low_confidence = sum(
        1 for r in results
        if not r.passes and r.confidence < config.REVENUE_CONFIDENCE_THRESHOLD
    )
    no_signal = sum(
        1 for r in results
        if not r.passes and not r.has_staff_signal and not r.has_benchmark_signal
    )

    return {
        "total_checked": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "rejection_rate": failed / total if total > 0 else 0.0,
        "rejections_by_reason": {
            "confidence_too_low": low_confidence,
            "no_staff_benchmark_signal": no_signal
        }
    }
