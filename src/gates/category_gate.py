"""
Category gate for business qualification.
PRIORITY: P1 - Flags borderline categories for human review.

Task 10: HITL Review Queue
- Automatically flags businesses in borderline categories for human review
- Prevents automatic qualification/disqualification of edge cases
"""

from dataclasses import dataclass
from typing import Optional, List
import structlog

from ..core.models import LeadStatus

logger = structlog.get_logger(__name__)


# Borderline categories that require human judgment
REVIEW_REQUIRED_CATEGORIES = [
    "funeral_home",          # Often small businesses but not target market
    "franchise_office",       # Might be owner-operated or corporate
    "real_estate_agent",     # Could be individual or small firm
    "insurance_agent",       # Could be individual or small firm
    "church",                 # Non-profit but sometimes has business operations
    "government",             # Usually not target market
    "school",                 # Educational institutions - edge case
    "hospital",               # Healthcare - edge case
    "lawyer",                 # Could be solo practice or small firm
    "dentist",                # Could be solo practice or small firm
    "doctor",                 # Could be solo practice or small firm
]


@dataclass
class CategoryGateResult:
    """Result of category gate validation."""
    passes: bool
    requires_review: bool
    category: str
    review_reason: Optional[str] = None
    suggested_status: Optional[LeadStatus] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage."""
        return {
            "passes": self.passes,
            "requires_review": self.requires_review,
            "category": self.category,
            "review_reason": self.review_reason,
            "suggested_status": self.suggested_status.value if self.suggested_status else None
        }


def category_gate(
    industry: str,
    business_types: Optional[List[str]] = None
) -> CategoryGateResult:
    """
    Validate business category against qualification criteria.

    Borderline categories are flagged for human review instead of
    automatic qualification/disqualification.

    Args:
        industry: Primary industry/category
        business_types: List of business types from various sources

    Returns:
        CategoryGateResult with review flag if needed

    Examples:
        >>> # Borderline case - requires review
        >>> result = category_gate("funeral_home")
        >>> assert result.requires_review is True
        >>> assert result.suggested_status == LeadStatus.REVIEW_REQUIRED

        >>> # Clear case - passes automatically
        >>> result = category_gate("manufacturing")
        >>> assert result.requires_review is False
        >>> assert result.passes is True

        >>> # Disqualified case
        >>> result = category_gate("gas_station")
        >>> assert result.requires_review is False
        >>> assert result.passes is False
    """
    # Normalize industry/category
    normalized_industry = industry.lower().strip().replace(" ", "_") if industry else ""

    # Check if category requires human review
    if normalized_industry in REVIEW_REQUIRED_CATEGORIES:
        logger.info(
            "category_requires_review",
            industry=industry,
            normalized=normalized_industry
        )

        return CategoryGateResult(
            passes=False,  # Don't auto-pass
            requires_review=True,
            category=industry,
            review_reason=f"Borderline category: {industry} - requires human judgment",
            suggested_status=LeadStatus.REVIEW_REQUIRED
        )

    # Check business_types if provided
    if business_types:
        for btype in business_types:
            normalized_type = btype.lower().strip().replace(" ", "_")
            if normalized_type in REVIEW_REQUIRED_CATEGORIES:
                logger.info(
                    "business_type_requires_review",
                    business_type=btype,
                    normalized=normalized_type
                )

                return CategoryGateResult(
                    passes=False,
                    requires_review=True,
                    category=btype,
                    review_reason=f"Borderline business type: {btype} - requires human judgment",
                    suggested_status=LeadStatus.REVIEW_REQUIRED
                )

    # Not a borderline category - passes category gate
    logger.debug(
        "category_gate_passed",
        industry=industry
    )

    return CategoryGateResult(
        passes=True,
        requires_review=False,
        category=industry,
        review_reason=None,
        suggested_status=None
    )


def get_review_categories() -> List[str]:
    """
    Get list of categories that require human review.

    Returns:
        List of category names that trigger review

    Example:
        >>> categories = get_review_categories()
        >>> assert "funeral_home" in categories
        >>> assert "franchise_office" in categories
    """
    return REVIEW_REQUIRED_CATEGORIES.copy()


def add_review_category(category: str):
    """
    Add a category to the review list.

    Args:
        category: Category name to add

    Example:
        >>> add_review_category("tattoo_parlor")
        >>> assert "tattoo_parlor" in get_review_categories()
    """
    normalized = category.lower().strip().replace(" ", "_")
    if normalized not in REVIEW_REQUIRED_CATEGORIES:
        REVIEW_REQUIRED_CATEGORIES.append(normalized)
        logger.info("review_category_added", category=normalized)


def remove_review_category(category: str):
    """
    Remove a category from the review list.

    Args:
        category: Category name to remove

    Example:
        >>> remove_review_category("funeral_home")
        >>> assert "funeral_home" not in get_review_categories()
    """
    normalized = category.lower().strip().replace(" ", "_")
    if normalized in REVIEW_REQUIRED_CATEGORIES:
        REVIEW_REQUIRED_CATEGORIES.remove(normalized)
        logger.info("review_category_removed", category=normalized)
