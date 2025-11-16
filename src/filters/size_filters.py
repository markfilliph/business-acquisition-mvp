"""
Size-based filtering for business leads.
Enforces hard caps on employee count, revenue, and review count.

PRACTICAL PLAN: Task 1
Keep businesses within strict SMB acquisition parameters.
"""
from typing import Tuple
from ..core.config import config


def filter_by_size(lead) -> Tuple[bool, str]:
    """
    Apply hard caps on business size.

    Enforces:
    - MAX_EMPLOYEE_COUNT: 25 employees
    - TARGET_REVENUE_MAX: $1.5M revenue
    - MAX_REVIEW_COUNT: 30 reviews (high visibility flag)

    Args:
        lead: BusinessLead object or dict with revenue_estimate, employee_count

    Returns:
        (should_exclude: bool, reason: str)

    Examples:
        >>> # VP Expert Machining: Revenue $1.4M-$2.7M
        >>> filter_by_size({'revenue_estimate': 2_000_000, 'employee_count': 15})
        (True, "EXCLUDED: Revenue $2.0M exceeds $1.5M cap")

        >>> # Abarth Machining: Revenue $780K-$1.5M, 10 employees
        >>> filter_by_size({'revenue_estimate': 1_000_000, 'employee_count': 10})
        (False, "PASSED")
    """
    # Handle both dict and object access
    if hasattr(lead, 'revenue_estimate'):
        revenue = getattr(lead, 'revenue_estimate', None)
        if hasattr(revenue, 'estimated_amount'):
            revenue = revenue.estimated_amount
        employee_count = getattr(lead, 'employee_count', None)
        review_count = getattr(lead, 'review_count', None)
    else:
        revenue = lead.get('revenue_estimate') or lead.get('revenue_max')
        employee_count = lead.get('employee_count')
        review_count = lead.get('review_count')

    # Check 1: Revenue cap ($1.5M hard limit)
    if revenue and revenue > config.TARGET_REVENUE_MAX:
        return True, f"EXCLUDED: Revenue ${revenue/1_000_000:.1f}M exceeds ${config.TARGET_REVENUE_MAX/1_000_000:.1f}M cap"

    # Check 2: Employee cap (25 employees)
    if employee_count and employee_count > config.MAX_EMPLOYEE_COUNT:
        return True, f"EXCLUDED: {employee_count} employees exceeds {config.MAX_EMPLOYEE_COUNT} employee cap"

    # Check 3: Review count (30+ reviews suggests larger operation)
    # Note: This is informational, not exclusionary - handled in warnings
    # if review_count and review_count > config.MAX_REVIEW_COUNT:
    #     return True, f"EXCLUDED: {review_count} reviews exceeds {config.MAX_REVIEW_COUNT} review cap (suggests chain/brand)"

    return False, "PASSED"


def check_revenue_fit(revenue: float) -> Tuple[bool, str]:
    """
    Check if revenue fits target range.

    Target: $800K - $1.5M

    Args:
        revenue: Estimated revenue in USD

    Returns:
        (fits_range: bool, reason: str)
    """
    if revenue < config.TARGET_REVENUE_MIN:
        return False, f"Revenue ${revenue/1_000_000:.1f}M below minimum ${config.TARGET_REVENUE_MIN/1_000_000:.1f}M"

    if revenue > config.TARGET_REVENUE_MAX:
        return False, f"Revenue ${revenue/1_000_000:.1f}M above maximum ${config.TARGET_REVENUE_MAX/1_000_000:.1f}M"

    return True, f"Revenue ${revenue/1_000_000:.1f}M fits target range"


def check_employee_fit(employee_count: int) -> Tuple[bool, str]:
    """
    Check if employee count fits target range.

    Target: 5 - 25 employees

    Args:
        employee_count: Number of employees

    Returns:
        (fits_range: bool, reason: str)
    """
    if employee_count < config.MIN_EMPLOYEE_COUNT:
        return False, f"{employee_count} employees below minimum {config.MIN_EMPLOYEE_COUNT}"

    if employee_count > config.MAX_EMPLOYEE_COUNT:
        return False, f"{employee_count} employees above maximum {config.MAX_EMPLOYEE_COUNT}"

    return True, f"{employee_count} employees fits target range"
