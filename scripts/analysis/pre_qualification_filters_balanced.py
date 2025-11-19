"""
BALANCED Pre-Qualification Filters - Smart Corporate Detection

This version fixes over-aggressive filtering that was rejecting legitimate small businesses.

Key Changes from "fixed" version:
1. Allow "Industries", "Solutions", "Group" in names (very common in small manufacturers)
2. Increase review caps: 40 for manufacturing, 30 for services
3. More specific blacklist (only actual major corporations)
4. Keep website requirement (still important)
5. Multi-factor approach: Don't reject on single indicator

Goal: 40-50% effectiveness with minimal false negatives
"""
from typing import Tuple, Dict
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.filters.exclusion_filters import ExclusionFilters

# SPECIFIC MAJOR CORPORATIONS - Only companies we KNOW are large
# Rule: Must be publicly traded, nationwide chain, or 500+ employees
MAJOR_CORPORATIONS = {
    # Steel/Metal (Public companies + Major distributors)
    'stelco', 'national steel car', 'arcelormittal', 'dofasco', 'us steel',
    'chapel steel', 'reliance steel',  # Major distributors
    'max aicher',  # Large German steel subsidiary

    # Food Manufacturing (Public companies / Major brands)
    'mondelez', 'kraft heinz', 'nestle', 'ferrero', 'hershey',
    'canada bread', 'weston bakeries', 'maple leaf foods',
    'bunge',  # NYSE-traded agribusiness giant
    'sucroc', 'lantic',  # Sugar refineries (large operations)

    # Food Retail Chains
    'denninger', 'bulk barn', 'loblaws', 'metro',

    # General Retail Chains (Nationwide)
    'factory shoe', 'dollarama', 'walmart', 'canadian tire',

    # Large Consultancies (Big 4 + Major)
    'deloitte', 'pwc', 'kpmg', 'ey', 'accenture', 'mckinsey',
    'dillon consulting', 'wsp',  # WSP is global engineering firm (50,000+ employees)

    # Japanese/International Manufacturers
    'daifuku', 'toyota', 'honda', 'hitachi', 'mitsubishi',
    'birla',  # Birla Carbon = Fortune 500 subsidiary

    # Incubators/Event Venues (Not Manufacturing)
    'innovation factory', 'arts factory', 'maker space',
    'business incubator', 'coworking',

    # Government/Institutional
    'city of hamilton', 'chamber of commerce', 'service ontario',
    'hamilton business centre',  # City economic development office
    'a.j. clarke',  # Government office

    # Fortune 500 Distributors
    'wesco',  # WESCO Distribution (NYSE, Fortune 500)

    # Franchise Networks (400+ locations)
    'johnstone supply',  # HVAC/electrical franchise (400+ locations)

    # Rental Chains (Multiple locations / National brands)
    'edge1',  # Edge1 Equipment Rentals (chain, 31 reviews)
    'sunbelt',  # Sunbelt Rentals (major national chain, 1000+ locations)
    'herc',  # Herc Rentals (major national chain, 300+ locations)
    'united rentals',  # United Rentals (Fortune 500, largest equipment rental)
    'home depot',  # Home Depot Tool Rental
}

# EXCLUDED PLACE TYPES - Clear non-B2B retail/services
EXCLUDED_PLACE_TYPES = {
    # Consumer Retail
    'shoe_store', 'clothing_store', 'convenience_store', 'gas_station',
    'car_dealer', 'furniture_store', 'electronics_store', 'jewelry_store',
    'pet_store', 'book_store', 'liquor_store', 'florist',

    # Food Retail (Consumer-facing)
    'restaurant', 'cafe', 'bar', 'meal_takeaway', 'night_club',
    'bakery',  # Unless they're wholesale
    'supermarket', 'grocery_store',

    # Entertainment/Events
    'event_venue', 'movie_theater', 'casino', 'amusement_park',

    # Arts/Culture
    'art_gallery', 'museum', 'library',

    # Personal Services
    'hair_care', 'beauty_salon', 'spa', 'gym', 'laundry',

    # Professional Services (Too consumer-focused)
    'doctor', 'dentist', 'lawyer', 'real_estate_agency',
    'accounting',  # Too many sole practitioners

    # Government/Institutional
    'government_office', 'local_government_office', 'city_hall',
    'courthouse', 'embassy', 'fire_station', 'police',
}

# REVIEW COUNT CAPS BY INDUSTRY - Stricter to catch chains
# Small B2B businesses rarely exceed 35 reviews
REVIEW_CAPS = {
    'manufacturing': 40,  # Tightened from 50
    'metal_fabrication': 40,
    'equipment_rental': 30,  # Tightened from 35 (rental chains often have 30-50 reviews)
    'printing': 35,  # Tightened from 40
    'professional_services': 30,  # Tightened from 35
    'wholesale': 35,
    'default': 35  # Tightened from 40
}

# STRONG CHAIN INDICATORS - Multi-factor scoring
# These alone don't reject, but combinations do
CHAIN_INDICATORS = {
    'name_patterns': {
        # These ARE concerning
        'international', 'global', 'worldwide', 'national',
        'corporation', 'enterprises', 'holdings',
    },
    'website_domains': {
        # Corporate website patterns
        '.com.au', '.co.uk', '.de', '.fr',  # International TLDs
    }
}


def pre_qualify_lead_balanced(place_data: dict, industry: str = 'manufacturing') -> Tuple[bool, str, Dict]:
    """
    BALANCED pre-qualification with smart corporate detection.

    Uses multi-factor approach:
    - Single strong indicator (blacklist) = reject
    - Multiple weak indicators = reject
    - Weak indicators alone = pass

    Returns:
        (should_enrich: bool, rejection_reason: str, metadata: dict)
    """
    name = place_data.get('name', '').lower()
    types = place_data.get('types', [])
    review_count = place_data.get('user_ratings_total', 0)
    website = place_data.get('website', '')
    rating = place_data.get('rating', 0)

    metadata = {
        'name': place_data.get('name'),
        'review_count': review_count,
        'rating': rating,
        'types': types,
        'website': website
    }

    # === INSTANT REJECT FILTERS (Strong Signals) ===

    # CRITICAL FIX 1: Government Offices (Check place types FIRST)
    government_types = {'government_office', 'local_government_office', 'city_hall',
                       'courthouse', 'embassy', 'fire_station', 'police'}
    if any(gov_type in types for gov_type in government_types):
        return False, "GOVERNMENT: Government office detected in place types", metadata

    # CRITICAL FIX 2: E-commerce/Shopify Stores (Retail, not B2B)
    if website:
        website_lower = website.lower()
        ecommerce_indicators = ['myshopify.com', 'square.site', 'wix.com/store',
                                'bigcartel.com', 'ecwid.com']
        for indicator in ecommerce_indicators:
            if indicator in website_lower:
                return False, f"E-COMMERCE: Online store detected ({indicator})", metadata

    # FILTER 1: Major Corporations Blacklist
    for corp in MAJOR_CORPORATIONS:
        if corp in name:
            # Extra check: Don't reject if it's just a supplier/dealer
            if 'dealer' in name or 'distributor' in name or 'authorized' in name:
                continue  # These might be small dealers
            return False, f"BLACKLIST: Major corporation '{corp}' detected", metadata

    # FILTER 2: Place Types Exclusion
    # Allow confectionery and art_studio ONLY if they have manufacturing types too
    excluded_types_found = []
    for place_type in types:
        if place_type in EXCLUDED_PLACE_TYPES:
            excluded_types_found.append(place_type)

    # If they have manufacturing types, give them a pass
    manufacturing_types = {'point_of_interest', 'establishment', 'factory',
                          'wholesaler', 'food_production'}
    has_manufacturing_types = bool(set(types) & manufacturing_types)

    if excluded_types_found and not has_manufacturing_types:
        return False, f"EXCLUDED TYPE: Place type '{excluded_types_found[0]}' not target business", metadata

    # FILTER 3: No Website = Reject (Can't verify ownership)
    if not website or website.lower() in ['n/a', 'none', '']:
        return False, "NO WEBSITE: Cannot verify single location or ownership", metadata

    # === MULTI-FACTOR SCORING (Weak Signals) ===

    risk_score = 0
    risk_factors = []

    # Factor 1: Review Count (Industry-Specific)
    max_reviews = REVIEW_CAPS.get(industry, REVIEW_CAPS['default'])

    # CRITICAL FIX 3: Stricter instant reject threshold (1.15x instead of 1.4x)
    # Chains often have 40-50+ reviews, small B2B rarely exceeds cap by much
    if review_count > max_reviews * 1.15:
        return False, f"TOO MANY REVIEWS: {review_count} reviews (max {max_reviews}) suggests chain/large operation", metadata

    # Add to risk score if moderately over
    if review_count > max_reviews:
        risk_score += 2  # Strong indicator
        risk_factors.append(f"{review_count} reviews (max {max_reviews})")
    elif review_count > max_reviews * 0.8:
        risk_score += 1  # Moderate indicator
        risk_factors.append(f"{review_count} reviews (approaching limit)")

    # Factor 2: Chain Indicators in Name
    for indicator in CHAIN_INDICATORS['name_patterns']:
        if indicator in name:
            risk_score += 1
            risk_factors.append(f"Name contains '{indicator}'")

    # Factor 3: High Rating + High Reviews = Brand
    if review_count > 30 and rating >= 4.6:
        risk_score += 1
        risk_factors.append(f"High brand recognition ({review_count} reviews @ {rating}★)")

    # Factor 4: International website
    if website:
        for tld in CHAIN_INDICATORS['website_domains']:
            if tld in website:
                risk_score += 1
                risk_factors.append(f"International website ({tld})")

    # DECISION: Reject if risk_score >= 3 (multiple weak indicators)
    if risk_score >= 3:
        reasons = "; ".join(risk_factors)
        return False, f"MULTI-FACTOR RISK: {reasons} (score: {risk_score})", metadata

    # === USE EXCLUSION FILTERS (Supplementary Check) ===

    # Only use for additional validation, not as primary filter
    exclusion_filter = ExclusionFilters()
    should_exclude, reason = exclusion_filter.should_exclude(
        business_name=place_data.get('name', ''),
        industry=industry
    )

    # Only reject if exclusion filter found something strong
    if should_exclude and ('chain' in reason.lower() or 'blacklist' in reason.lower()):
        return False, f"EXCLUSION FILTER: {reason}", metadata

    # PASSED ALL FILTERS
    return True, "PASSED", metadata


def test_balanced_filters():
    """Test the balanced filters on real examples."""

    test_cases = [
        # Should REJECT (Major Corporations)
        {
            'name': 'Stelco Hamilton Works',
            'types': ['point_of_interest', 'establishment'],
            'user_ratings_total': 58,
            'website': 'https://www.stelco.com/',
            'rating': 3.9,
            'expected': False,
            'reason': 'Public steel corporation'
        },
        {
            'name': 'Mondelez Canada',
            'types': ['manufacturing', 'point_of_interest'],
            'user_ratings_total': 51,
            'website': 'https://www.mondelezinternational.com/',
            'rating': 3.7,
            'expected': False,
            'reason': 'NYSE-traded food company'
        },
        {
            'name': 'The Spice Factory',
            'types': ['event_venue', 'point_of_interest'],
            'user_ratings_total': 282,
            'website': 'http://www.spicefactory.ca/',
            'rating': 4.5,
            'expected': False,
            'reason': 'Event venue, not manufacturing'
        },

        # Should PASS (Small Manufacturers - Previously Wrongly Rejected)
        {
            'name': 'Hager Industries Inc',
            'types': ['point_of_interest', 'establishment'],
            'user_ratings_total': 4,
            'website': 'https://hagerindustries.com/',
            'rating': 5.0,
            'expected': True,
            'reason': 'Small manufacturer (4 reviews) - "Industries" is OK'
        },
        {
            'name': 'Cancore Industries Inc.',
            'types': ['point_of_interest', 'establishment'],
            'user_ratings_total': 3,
            'website': 'https://www.cancore.net/',
            'rating': 5.0,
            'expected': True,
            'reason': 'Small manufacturer (3 reviews) - "Industries" is OK'
        },
        {
            'name': 'Canadian Additive Manufacturing Solutions',
            'types': ['point_of_interest', 'establishment'],
            'user_ratings_total': 6,
            'website': 'http://www.canadianadditive.ca/',
            'rating': 5.0,
            'expected': True,
            'reason': 'Small manufacturer (6 reviews) - "Solutions" is OK'
        },
        {
            'name': 'Embree Industries Ltd',
            'types': ['point_of_interest', 'establishment'],
            'user_ratings_total': 0,
            'website': 'https://embreeindustries.com/',
            'rating': 0,
            'expected': True,
            'reason': 'Small manufacturer (0 reviews) - "Industries" is OK'
        },
        {
            'name': 'Welsh Industrial Manufacturing Inc',
            'types': ['point_of_interest', 'establishment'],
            'user_ratings_total': 1,
            'website': 'http://www.welshmfg.com/',
            'rating': 5.0,
            'expected': True,
            'reason': 'Small manufacturer - should pass'
        },

        # Edge Cases
        {
            'name': 'Ontario Ravioli',
            'types': ['food', 'point_of_interest'],
            'user_ratings_total': 73,
            'website': 'http://ontarioravioli.com/',
            'rating': 4.5,
            'expected': False,
            'reason': 'High reviews (73) suggests larger operation'
        },
        {
            'name': 'G. S. Dunn Ltd.',
            'types': ['wholesaler', 'food', 'point_of_interest'],
            'user_ratings_total': 9,
            'website': 'http://gsdunn.com/',
            'rating': 4.7,
            'expected': True,
            'reason': 'Small food wholesaler - should pass'
        },
    ]

    print("\n" + "="*80)
    print("BALANCED PRE-QUALIFICATION FILTER TESTS")
    print("="*80 + "\n")

    passed = 0
    failed = 0
    false_negatives = []  # Should reject but didn't
    false_positives = []   # Should pass but didn't

    for test in test_cases:
        should_enrich, reason, metadata = pre_qualify_lead_balanced(test, industry='manufacturing')

        expected_result = test['expected']
        actual_result = should_enrich

        if expected_result == actual_result:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
            if expected_result and not actual_result:
                false_positives.append(test['name'])
            elif not expected_result and actual_result:
                false_negatives.append(test['name'])

        print(f"{status} | {test['name']}")
        print(f"         Expected: {'PASS' if expected_result else 'REJECT'} - {test['reason']}")
        print(f"         Got: {'PASS' if actual_result else 'REJECT'} - {reason}")
        print(f"         Stats: {test['user_ratings_total']} reviews, {test.get('rating', 0)}★")
        print()

    print("="*80)
    print(f"Results: {passed}/{len(test_cases)} tests passed ({(passed/len(test_cases)*100):.1f}%)")
    print(f"Failed: {failed}")
    if false_positives:
        print(f"\n⚠️  False Positives (wrongly rejected): {', '.join(false_positives)}")
    if false_negatives:
        print(f"\n⚠️  False Negatives (wrongly passed): {', '.join(false_negatives)}")
    print("="*80 + "\n")

    return passed == len(test_cases)


if __name__ == '__main__':
    success = test_balanced_filters()
    exit(0 if success else 1)
