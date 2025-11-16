"""
Generate warnings for leads that need manual verification.
Non-fatal - leads pass through but flagged for review.

PRACTICAL PLAN: Task 4
Flags potential issues without hard exclusions.
"""
from typing import List
from ..core.models import BusinessLead
from ..core.config import config


def generate_warnings(lead: BusinessLead) -> List[str]:
    """
    Add warning flags for potential issues.

    Warnings are NOT exclusions - they're "hey, double-check this"

    Warning Categories:
    1. HIGH_VISIBILITY: Many reviews suggest larger operation
    2. UPPER_RANGE: Revenue near cap
    3. VERIFY_SIZE: Employee count + reviews suggest undercount
    4. NO_WEBSITE: Limited online presence
    5. NEW_BUSINESS: Less than 2 years old
    6. ESTABLISHED: 40+ years (succession opportunity)

    Args:
        lead: BusinessLead object to check

    Returns:
        List of warning strings
    """
    warnings = []

    # Get review count (handle both attribute and dict access)
    review_count = getattr(lead, 'review_count', None)
    if review_count is None and hasattr(lead, '__getitem__'):
        review_count = lead.get('review_count')

    # Warning 1: High review count (may indicate larger business)
    if review_count and review_count > 20:
        warnings.append(
            "HIGH_VISIBILITY: 20+ reviews suggests larger operation or chain. "
            "Verify this is single-location SMB."
        )

    # Warning 2: Revenue approaching upper limit
    revenue = None
    if hasattr(lead, 'revenue_estimate'):
        if hasattr(lead.revenue_estimate, 'estimated_amount'):
            revenue = lead.revenue_estimate.estimated_amount
    elif hasattr(lead, '__getitem__'):
        revenue = lead.get('revenue_estimate') or lead.get('revenue_max')

    if revenue and revenue > 1_200_000:
        warnings.append(
            f"UPPER_RANGE: Revenue ${revenue/1_000_000:.1f}M near $1.5M cap. "
            "Confirm size fits acquisition thesis."
        )

    # Warning 3: Employee count + reviews suggest possible undercount
    employee_count = getattr(lead, 'employee_count', None)
    if employee_count is None and hasattr(lead, '__getitem__'):
        employee_count = lead.get('employee_count')

    if (employee_count and employee_count > 15 and
        review_count and review_count > 20):
        warnings.append(
            "VERIFY_SIZE: High employee count + high reviews may indicate "
            "Google Places showing location headcount only. Cross-check company-wide size."
        )

    # Warning 4: No website (harder due diligence)
    website = None
    if hasattr(lead, 'contact'):
        website = lead.contact.website
    elif hasattr(lead, '__getitem__'):
        website = lead.get('website')

    if not website or website.lower() in ['n/a', 'none', '']:
        warnings.append(
            "NO_WEBSITE: Limited online presence makes due diligence harder. "
            "Prioritize leads with websites."
        )

    # Warning 5: Very old or very new business
    years_in_business = getattr(lead, 'years_in_business', None)
    if years_in_business is None and hasattr(lead, '__getitem__'):
        years_in_business = lead.get('years_in_business')

    if years_in_business:
        if years_in_business < 2:
            warnings.append(
                "NEW_BUSINESS: Less than 2 years old. Higher risk profile."
            )
        elif years_in_business > 40:
            warnings.append(
                "ESTABLISHED: 40+ years old. May have succession opportunities."
            )

    # Warning 6: Food manufacturing (hybrid retail risk)
    industry = getattr(lead, 'industry', None)
    if industry is None and hasattr(lead, '__getitem__'):
        industry = lead.get('industry')

    business_name = getattr(lead, 'business_name', '')
    if not business_name and hasattr(lead, '__getitem__'):
        business_name = lead.get('business_name', '')

    if industry and 'food' in industry.lower():
        # Check if name suggests retail component
        retail_indicators = ['cafe', 'restaurant', 'bakery', 'deli', 'shop', 'market']
        if any(indicator in business_name.lower() for indicator in retail_indicators):
            warnings.append(
                "HYBRID_BUSINESS: Food business with possible retail component. "
                "Verify if primarily B2B manufacturing or consumer-facing."
            )

    return warnings


def apply_warnings(lead: BusinessLead) -> BusinessLead:
    """
    Apply warnings to lead.

    Args:
        lead: BusinessLead object to check

    Returns:
        Lead with warnings applied (if any)
    """
    warnings = generate_warnings(lead)
    for warning in warnings:
        lead.add_warning("MANUAL_REVIEW", warning)
    return lead


def filter_high_priority_leads(leads: List[BusinessLead]) -> tuple[List[BusinessLead], List[BusinessLead]]:
    """
    Separate leads into high-priority (no warnings) and needs-review (has warnings).

    Args:
        leads: List of BusinessLead objects

    Returns:
        (high_priority_leads, needs_review_leads)
    """
    high_priority = []
    needs_review = []

    for lead in leads:
        if not lead.warnings:
            high_priority.append(lead)
        else:
            needs_review.append(lead)

    return high_priority, needs_review
