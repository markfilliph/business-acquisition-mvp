"""
Exclusion Filters - Identify Franchises, Corporations, and Large Businesses

Filters out:
1. Publicly-traded companies
2. Franchises and chain stores
3. Subsidiaries of large corporations
4. Well-known national/international brands
"""
import re
from typing import Optional, Tuple


class ExclusionFilters:
    """
    Apply strict exclusion filters to identify businesses that are TOO LARGE.
    """

    def __init__(self):
        # Known franchises and chains (case-insensitive)
        self.franchise_brands = {
            'wholesale club', 'bulk barn', 'loblaws', 'sobeys', 'metro',
            'tim hortons', 'mcdonalds', 'subway', 'starbucks', 'wendy',
            'boston pizza', 'pizza hut', 'dominos', 'kfc', 'taco bell',
            'second cup', 'dairy queen', 'a&w', 'burger king',
            'shoppers drug mart', 'rexall', 'pharmasave', 'london drugs',
            'canadian tire', 'home depot', 'walmart', 'costco', 'home hardware',
            'beer store', 'lcbo', 'pizza pizza', 'swiss chalet'
        }

        # Large corporations and their subsidiaries
        self.corporate_brands = {
            'mondelez', 'kraft', 'nestle', 'unilever', 'procter', 'gamble',
            'coca cola', 'pepsi', 'general mills', 'kellogg',
            'stelco', 'arcelormittal', 'dofasco', 'us steel',
            'magna', 'linamar', 'martinrea',
            'bell', 'rogers', 'telus', 'shaw',
            'rbc', 'td bank', 'scotiabank', 'bmo', 'cibc',
            'manulife', 'sunlife', 'great west',
            'loblaw', 'empire company', 'sobeys'
        }

        # Corporate suffixes that indicate large companies
        self.large_company_indicators = [
            'international', 'worldwide', 'global', 'national',
            'corporation', 'industries', 'group', 'holdings',
            'enterprises', 'solutions', 'systems'
        ]

        # Exclude certain business types entirely
        self.excluded_types = {
            'bank', 'credit union', 'insurance', 'telecom',
            'hospital', 'university', 'college', 'school',
            'government', 'municipality', 'city of', 'town of',
            'chain', 'franchise', 'corporate'
        }

    def is_franchise(self, business_name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if business is a known franchise.

        Returns:
            (is_franchise, reason)
        """
        name_lower = business_name.lower()

        for brand in self.franchise_brands:
            if brand in name_lower:
                return True, f"Known franchise: {brand}"

        return False, None

    def is_large_corporation(self, business_name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if business is a large corporation or subsidiary.

        Returns:
            (is_corporation, reason)
        """
        name_lower = business_name.lower()

        # Check against known corporate brands
        for brand in self.corporate_brands:
            if brand in name_lower:
                return True, f"Large corporation: {brand}"

        # Check for corporate indicators
        for indicator in self.large_company_indicators:
            if indicator in name_lower:
                return True, f"Corporate indicator: {indicator}"

        return False, None

    def has_excluded_type(self, business_name: str, industry: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if business type should be excluded.

        Returns:
            (is_excluded, reason)
        """
        name_lower = business_name.lower()
        industry_lower = industry.lower() if industry else ""

        for excluded in self.excluded_types:
            if excluded in name_lower or excluded in industry_lower:
                return True, f"Excluded type: {excluded}"

        return False, None

    def has_corporate_suffix(self, business_name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if business name has patterns indicating large company.

        Patterns:
        - "Corp" or "Corporation" (without "Inc" - small businesses use Inc)
        - "Industries" (plural - indicates manufacturing conglomerate)
        - "Group" or "Holdings" (indicates holding company)
        - "International" or "Global" or "National"

        Returns:
            (has_suffix, reason)
        """
        name_lower = business_name.lower()

        # Large company patterns
        large_patterns = [
            (r'\b(corporation)\b', 'Corporation (large company indicator)'),
            (r'\b(industries)\b', 'Industries (conglomerate indicator)'),
            (r'\b(group)\b', 'Group (holding company indicator)'),
            (r'\b(holdings?)\b', 'Holdings (investment company indicator)'),
            (r'\b(international)\b', 'International (multinational indicator)'),
            (r'\b(global)\b', 'Global (multinational indicator)'),
            (r'\b(national)\b', 'National (large scale indicator)'),
            (r'\b(worldwide)\b', 'Worldwide (multinational indicator)'),
        ]

        for pattern, reason in large_patterns:
            if re.search(pattern, name_lower):
                return True, reason

        return False, None

    def should_exclude(self, business_name: str, industry: Optional[str] = None) -> Tuple[bool, str]:
        """
        Comprehensive exclusion check.

        Returns:
            (should_exclude, reason)
        """
        # Check franchise
        is_franchise, reason = self.is_franchise(business_name)
        if is_franchise:
            return True, f"FRANCHISE: {reason}"

        # Check large corporation
        is_corp, reason = self.is_large_corporation(business_name)
        if is_corp:
            return True, f"LARGE CORPORATION: {reason}"

        # Check excluded types
        is_excluded_type, reason = self.has_excluded_type(business_name, industry)
        if is_excluded_type:
            return True, f"EXCLUDED TYPE: {reason}"

        # Check corporate suffix
        has_suffix, reason = self.has_corporate_suffix(business_name)
        if has_suffix:
            return True, f"CORPORATE PATTERN: {reason}"

        return False, "PASSED"


def test_filters():
    """Test exclusion filters with known examples."""
    filters = ExclusionFilters()

    test_cases = [
        # Should be EXCLUDED
        ("Mondelez Canada", None, True, "Large corporation"),
        ("Wholesale Club Hamilton", "wholesale", True, "Franchise"),
        ("Bulk Barn", "wholesale", True, "Franchise"),
        ("Stelco Hamilton Works", "manufacturing", True, "Large corporation"),
        ("Atlantic Packaging Industries", None, True, "Industries suffix"),
        ("XYZ Corporation", None, True, "Corporation suffix"),
        ("ABC International", None, True, "International suffix"),
        ("Downtown Hamilton BIA", "business association", True, "Organization type"),

        # Should PASS
        ("Joe's Auto Repair", "automotive", False, "Small business"),
        ("Smith Manufacturing Inc.", "manufacturing", False, "Inc is okay"),
        ("Hamilton Print Shop", "printing", False, "Local business"),
        ("Karma Candy Inc", "food manufacturing", False, "Small manufacturer"),
        ("The Spice Factory", "manufacturing", False, "The is okay"),
        ("Ontario Ravioli", "food manufacturing", False, "Local food maker"),
    ]

    print("\n=== EXCLUSION FILTER TESTS ===\n")

    passed = 0
    failed = 0

    for name, industry, should_exclude, description in test_cases:
        is_excluded, reason = filters.should_exclude(name, industry)

        status = "✅ PASS" if is_excluded == should_exclude else "❌ FAIL"
        if is_excluded == should_exclude:
            passed += 1
        else:
            failed += 1

        print(f"{status} | {name}")
        print(f"         Expected: {'EXCLUDE' if should_exclude else 'ALLOW'} ({description})")
        print(f"         Got: {'EXCLUDE' if is_excluded else 'ALLOW'} ({reason})")
        print()

    print(f"Results: {passed} passed, {failed} failed\n")


if __name__ == '__main__':
    test_filters()
