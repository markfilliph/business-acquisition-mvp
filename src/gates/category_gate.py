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


# EXCLUDED categories - automatically disqualified (NOT manufacturing/wholesale/B2B)
EXCLUDED_CATEGORIES = [
    # Food service - NOT our target
    "restaurant", "cafe", "bar", "pub", "food_court", "fast_food",
    "bakery", "coffee_shop", "catering", "bistro", "eatery", "diner",
    "pizzeria", "steakhouse", "seafood", "sushi", "brewery", "winery",

    # Retail - NOT our target
    "retail", "store", "shop", "boutique", "mall", "supermarket",
    "convenience_store", "gas_station", "clothing_store", "shoe_store",
    "book_store", "gift_shop", "department_store", "pharmacy",

    # Consumer services - NOT B2B
    "salon", "spa", "gym", "fitness", "hotel", "motel", "accommodation",
    "car_wash", "dry_cleaning", "laundromat", "barbershop",

    # Entertainment/Recreation - NOT our target
    "theater", "cinema", "amusement", "arcade", "bowling", "casino",
    "nightclub", "stripclub",

    # Government/Non-profit - NOT our target
    "government", "city_hall", "library", "museum", "church", "temple",
    "mosque", "synagogue", "school", "university", "hospital",

    # Coworking/Incubators - NOT real businesses
    "coworking", "co-working", "shared_workspace", "incubator", "accelerator",
    "innovation_center", "startup_hub", "business_center", "event_space",
    "event_venue", "arts_center", "community_space",
]

# Major franchise/chain brand names - automatically exclude
FRANCHISE_BRANDS = [
    # Food chains
    "mcdonald", "burger_king", "wendy", "subway", "tim_horton", "starbucks",
    "pizza_hut", "domino", "kfc", "taco_bell", "a&w",

    # Retail chains
    "walmart", "target", "costco", "bulk_barn", "dollarama", "dollar_tree",
    "loblaws", "sobeys", "metro", "food_basics", "no_frills",
    "shoppers_drug_mart", "rexall", "london_drugs",

    # Service chains
    "jiffy_lube", "midas", "canadian_tire", "home_depot", "rona",
    "factory_shoe", "payless", "footlocker",

    # Wholesale clubs (not our target - too large)
    "wholesale_club", "costco", "sams_club",

    # Large corporations & public companies
    "stelco", "arcelormittal", "dofasco",  # Steel manufacturers
    "chapel_steel", "ryerson", "reliance_steel",  # Steel distributors (multi-location)
    "national_steel_car", "greenbrier", "trinity_industries",  # Railcar manufacturers
    "atlantic_packaging", "cascades", "westrock",  # Packaging companies
    "mondelez", "nestle", "kraft", "general_mills",  # Food conglomerates
    "pepsico", "coca-cola", "unilever",  # Beverage/consumer goods
    "bunge", "cargill", "archer_daniels", "adm",  # Agribusiness giants
    "daifuku", "kion", "toyota_industries",  # Material handling corporations

    # Major distributors/wholesalers
    "sysco", "gordon_food_service", "gfs", "canada_bread",
    "traynor", "fiddes", "tree_of_life",  # Known Hamilton area wholesalers

    # Additional retail chains
    "winners", "marshalls", "homesense", "michael", "staples",
    "best_buy", "future_shop", "the_brick", "leon",

    # Known Hamilton non-manufacturing venues/spaces (event spaces, coworking, etc.)
    "innovation_factory", "cotton_factory", "arts_factory",  # Coworking/event venues
    "spice_factory", "denninger",  # Event venue and retail chain
    "sucro", "sucrocan",  # Large publicly-traded corporations
]

# Large company indicators in names/descriptions
LARGE_COMPANY_INDICATORS = [
    "inc.", "incorporated", "corp.", "corporation", "ltd.", "limited",
    "industries", "international", "holdings", "group", "global",
    "worldwide", "enterprises", "systems", "solutions"
]

# Website patterns that indicate large companies
CORPORATE_WEBSITE_PATTERNS = [
    # Public company domains
    ".com/locations/", "/our-locations", "/store-locator", "/find-a-store",
    # Multi-language sites (usually large corps)
    "/en-ca/", "/fr-ca/", "/en/", "/fr/",
    # Investor relations (public companies)
    "/investors/", "/investor-relations/", "/shareholders/",
]

# Franchise indicators in business names or descriptions
FRANCHISE_INDICATORS = [
    "franchise", "franchisee", "chain", "locations nationwide",
    "part of", "subsidiary of", "owned by", "division of",
    "branch of", "affiliate of", "licensed by"
]

# Borderline categories that require human judgment
REVIEW_REQUIRED_CATEGORIES = [
    "funeral_home",          # Often small businesses but not target market
    "real_estate_agent",     # Could be individual or small firm
    "insurance_agent",       # Could be individual or small firm
    "lawyer",                 # Could be solo practice or small firm
    "dentist",                # Could be solo practice or small firm
    "doctor",                 # Could be solo practice or small firm
    "consultant",             # Could be B2B or consumer
    "contractor",             # Could be construction (good) or handyman (bad)
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
    business_types: Optional[List[str]] = None,
    business_name: Optional[str] = None,
    website: Optional[str] = None
) -> CategoryGateResult:
    """
    Validate business category against qualification criteria.

    STRICT ENFORCEMENT:
    1. Exclude restaurants, retail, consumer services
    2. Exclude major franchises/chains
    3. Flag borderline cases for review
    4. Only pass manufacturing, wholesale, B2B services

    Args:
        industry: Primary industry/category
        business_types: List of business types from various sources
        business_name: Business name (for franchise detection)

    Returns:
        CategoryGateResult with pass/fail/review

    Examples:
        >>> # Excluded - restaurant
        >>> result = category_gate("restaurant")
        >>> assert result.passes is False

        >>> # Excluded - franchise brand
        >>> result = category_gate("manufacturing", business_name="McDonald's")
        >>> assert result.passes is False

        >>> # Pass - manufacturing
        >>> result = category_gate("manufacturing")
        >>> assert result.passes is True
    """
    # Normalize industry/category
    normalized_industry = industry.lower().strip().replace(" ", "_") if industry else ""
    normalized_name = business_name.lower().strip().replace(" ", "_") if business_name else ""

    # STEP 1: Check if business is a franchise/chain brand
    if business_name:
        for brand in FRANCHISE_BRANDS:
            if brand in normalized_name:
                logger.info(
                    "franchise_brand_excluded",
                    business_name=business_name,
                    brand=brand
                )
                return CategoryGateResult(
                    passes=False,
                    requires_review=False,
                    category=industry,
                    review_reason=f"Major franchise/chain: {business_name}",
                    suggested_status=LeadStatus.DISQUALIFIED
                )

        # Check for franchise indicators in name
        for indicator in FRANCHISE_INDICATORS:
            if indicator in normalized_name:
                logger.info(
                    "franchise_indicator_found",
                    business_name=business_name,
                    indicator=indicator
                )
                return CategoryGateResult(
                    passes=False,
                    requires_review=False,
                    category=industry,
                    review_reason=f"Franchise indicator in name: {indicator}",
                    suggested_status=LeadStatus.DISQUALIFIED
                )

    # STEP 1b: Check for large company indicators in business name
    if business_name:
        normalized_lower = business_name.lower()
        # Check for multiple indicators (2+ = likely large corp)
        indicator_count = sum(1 for ind in LARGE_COMPANY_INDICATORS if ind in normalized_lower)

        # Special check for "Industries", "International", etc. in name
        # These often indicate large corporations
        large_corp_keywords = ["industries", "international", "holdings", "group", "global", "worldwide"]
        has_large_keyword = any(keyword in normalized_name for keyword in large_corp_keywords)

        if indicator_count >= 2 or has_large_keyword:
            logger.info(
                "large_company_excluded",
                business_name=business_name,
                indicator_count=indicator_count,
                has_large_keyword=has_large_keyword
            )
            return CategoryGateResult(
                passes=False,
                requires_review=False,
                category=industry,
                review_reason=f"Large corporation indicator in name: {business_name}",
                suggested_status=LeadStatus.DISQUALIFIED
            )

    # STEP 1c: Check corporate website patterns
    if website:
        normalized_website = website.lower()
        for pattern in CORPORATE_WEBSITE_PATTERNS:
            if pattern in normalized_website:
                logger.info(
                    "corporate_website_pattern_excluded",
                    business_name=business_name,
                    website=website,
                    pattern=pattern
                )
                return CategoryGateResult(
                    passes=False,
                    requires_review=False,
                    category=industry,
                    review_reason=f"Corporate website pattern detected: {pattern}",
                    suggested_status=LeadStatus.DISQUALIFIED
                )

    # STEP 2: Check if category is EXCLUDED (retail, food, etc.)
    for excluded in EXCLUDED_CATEGORIES:
        if excluded in normalized_industry:
            logger.info(
                "excluded_category",
                industry=industry,
                excluded=excluded
            )
            return CategoryGateResult(
                passes=False,
                requires_review=False,
                category=industry,
                review_reason=f"Excluded category: {industry} (not manufacturing/wholesale/B2B)",
                suggested_status=LeadStatus.DISQUALIFIED
            )

    # Check business_types for excluded categories
    if business_types:
        for btype in business_types:
            normalized_type = btype.lower().strip().replace(" ", "_")
            for excluded in EXCLUDED_CATEGORIES:
                if excluded in normalized_type:
                    logger.info(
                        "excluded_business_type",
                        business_type=btype,
                        excluded=excluded
                    )
                    return CategoryGateResult(
                        passes=False,
                        requires_review=False,
                        category=btype,
                        review_reason=f"Excluded type: {btype}",
                        suggested_status=LeadStatus.DISQUALIFIED
                    )

    # STEP 3: Check if category requires human review
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

    # Check business_types for review categories
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

    # STEP 4: Passed all checks - manufacturing/wholesale/B2B
    logger.debug(
        "category_gate_passed",
        industry=industry,
        business_name=business_name
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
