"""
Business type exclusion filters.
Removes retail, consumer-facing, and non-B2B businesses.

PRACTICAL PLAN: Task 2 & Task 3
- Task 2: Retail business filter (catches Container57-type leads)
- Task 3: Location label filter (catches Emerald Manufacturing Site-type leads)
"""
from typing import Tuple, Optional


class BusinessTypeFilter:
    """Filter out wrong business types."""

    def __init__(self):
        # E-commerce platforms (strong retail indicators)
        self.retail_platforms = [
            'shopify.com',
            'myshopify.com',
            'bigcartel.com',
            'wix.com/online-store',
            'squarespace.com/commerce',
            'etsy.com',
            'square.site',
        ]

        # Retail industry keywords
        self.retail_keywords = [
            'retail', 'shop', 'store', 'boutique',
            'mall', 'outlet', 'showroom', 'marketplace'
        ]

        # Consumer-facing indicators
        self.consumer_indicators = [
            'online store', 'e-commerce', 'ecommerce',
            'shopping', 'buy online', 'online shop',
            'consumer goods', 'direct to consumer'
        ]

        # Location/facility keywords
        self.location_keywords = [
            'site', 'facility', 'location', 'building',
            'complex', 'park', 'center', 'plaza',
            'industrial park', 'business park'
        ]

    def is_retail_business(self,
                          business_name: str,
                          industry: Optional[str],
                          website: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Detect retail/consumer-facing businesses.

        Checks:
        1. E-commerce platforms (Shopify, BigCartel, etc.)
        2. Industry classification (retail keywords)
        3. Business name + industry combination

        Args:
            business_name: Name of the business
            industry: Industry classification (optional)
            website: Business website URL (optional)

        Returns:
            (is_retail: bool, reason: str)

        Examples:
            >>> filter = BusinessTypeFilter()
            >>> # Container57: Shopify store
            >>> filter.is_retail_business("Container57", "Retail", "https://60424e-3.myshopify.com/")
            (True, "E-commerce platform detected: myshopify.com")

            >>> # Abarth Machining: B2B manufacturing
            >>> filter.is_retail_business("Abarth Machining Inc", "Manufacturing", "https://abarthmachining.com/")
            (False, None)
        """
        # Check 1: Website contains e-commerce platform
        if website:
            website_lower = website.lower()
            for platform in self.retail_platforms:
                if platform in website_lower:
                    return True, f"E-commerce platform detected: {platform}"

        # Check 2: Industry classification contains retail keywords
        if industry:
            industry_lower = industry.lower()
            for keyword in self.retail_keywords:
                if keyword in industry_lower:
                    return True, f"Retail industry: contains '{keyword}'"

        # Check 3: Business name contains retail keywords + consumer indicators
        if business_name and industry:
            name_lower = business_name.lower()
            industry_lower = industry.lower()

            for keyword in self.retail_keywords:
                if keyword in name_lower:
                    # Check if also has consumer indicators in industry
                    for indicator in self.consumer_indicators:
                        if indicator in industry_lower:
                            return True, f"Retail business: name contains '{keyword}' with consumer focus"

        return False, None

    def is_location_label(self,
                         business_name: str,
                         website: Optional[str],
                         review_count: Optional[int]) -> Tuple[bool, Optional[str]]:
        """
        Detect location labels vs. actual businesses.

        Location labels typically have:
        - Generic facility names ("X Manufacturing Site", "Y Industrial Complex")
        - No website or website is "N/A"
        - Very few or no reviews (0-1 reviews)

        Args:
            business_name: Name of the business
            website: Business website URL (optional)
            review_count: Number of Google reviews (optional)

        Returns:
            (is_location: bool, reason: str)

        Examples:
            >>> filter = BusinessTypeFilter()
            >>> # Emerald Manufacturing Site: Location label
            >>> filter.is_location_label("Emerald Manufacturing Site", None, 1)
            (True, "Location label: contains 'site' with no web presence")

            >>> # North Star Technical Inc: Real business
            >>> filter.is_location_label("North Star Technical Inc", "https://northstartech.com/", 11)
            (False, None)
        """
        name_lower = business_name.lower()

        # Step 1: Check for location keywords in name
        has_location_keyword = False
        matched_keyword = None

        for keyword in self.location_keywords:
            if keyword in name_lower:
                has_location_keyword = True
                matched_keyword = keyword
                break

        # If no location keyword found, not a location label
        if not has_location_keyword:
            return False, None

        # Step 2: Location keyword found - check for missing business signals
        has_no_website = (
            not website or
            website.lower() in ['n/a', 'na', 'none', '', 'null', 'not available']
        )
        has_no_reviews = (review_count is None or review_count <= 1)

        # Flag if location keyword + no web presence
        if has_no_website and has_no_reviews:
            return True, f"Location label: contains '{matched_keyword}' with no web presence"

        # Step 3: Check for suspicious name patterns (even with website)
        suspicious_patterns = [
            'manufacturing site',
            'facility location',
            'industrial site',
            'production facility',
            'business park',
            'industrial complex'
        ]

        for pattern in suspicious_patterns:
            if pattern in name_lower:
                return True, f"Location label: name pattern '{pattern}'"

        return False, None

    def should_exclude(self,
                      business_name: str,
                      industry: Optional[str] = None,
                      website: Optional[str] = None,
                      review_count: Optional[int] = None) -> Tuple[bool, str]:
        """
        Comprehensive business type exclusion check.

        Checks both retail and location label filters.

        Args:
            business_name: Name of the business
            industry: Industry classification (optional)
            website: Business website URL (optional)
            review_count: Number of Google reviews (optional)

        Returns:
            (should_exclude: bool, reason: str)

        Examples:
            >>> filter = BusinessTypeFilter()
            >>> # Exclude retail
            >>> filter.should_exclude("Container57", "Retail", "https://myshopify.com/", 4)
            (True, "RETAIL BUSINESS: E-commerce platform detected: myshopify.com")

            >>> # Exclude location label
            >>> filter.should_exclude("Emerald Manufacturing Site", None, "N/A", 1)
            (True, "LOCATION LABEL: Location label: contains 'site' with no web presence")

            >>> # Allow B2B manufacturing
            >>> filter.should_exclude("Abarth Machining Inc", "Manufacturing", "https://abarth.com/", 3)
            (False, "PASSED")
        """
        # Check 1: Retail business
        is_retail, reason = self.is_retail_business(business_name, industry, website)
        if is_retail:
            return True, f"RETAIL BUSINESS: {reason}"

        # Check 2: Location label
        is_location, reason = self.is_location_label(business_name, website, review_count)
        if is_location:
            return True, f"LOCATION LABEL: {reason}"

        return False, "PASSED"
