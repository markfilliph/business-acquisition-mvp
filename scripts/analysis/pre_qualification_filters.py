"""
PRE-QUALIFICATION FILTERS
Apply these BEFORE enrichment to save API calls and improve lead quality

This reduces bad leads from entering the pipeline, saving enrichment costs
and improving final qualification rate from 62% to 80%+
"""

import re
from typing import Dict, List, Optional, Tuple

# ===== CONFIGURATION =====

# Chain/franchise keywords to exclude immediately
CHAIN_KEYWORDS = [
    # National chains
    'wholesale club', 'sunbelt', 'herc rentals', 'minuteman press',
    'allegra', 'tph', 'print three', 'kwik kopy', 'staples',
    'fedex', 'ups store', 'office depot', 'canada post',
    
    # Printing chains
    'kwik kopy', 'allegra', 'minuteman', 'print three', 'printthree',
    'fedex office', 'staples print', 'office depot print',
    
    # Equipment rental chains  
    'sunbelt', 'herc', 'united rentals', 'home depot rental',
    
    # Big industrial
    'siemens', 'ge ', 'general electric', 'caterpillar', 'deere',
    'honeywell', 'emerson', '3m ', 'dow ', 'dupont',
    
    # Food/beverage conglomerates
    'nestle', 'kraft', 'mondelez', 'pepsico', 'coca-cola',
    'unilever', 'procter & gamble', 'kellogg',
    
    # Wholesale big box
    'costco', 'sams club', 'metro', 'sobeys', 'loblaws'
]

# Corporate structure indicators (usually not owner-operated SMBs)
CORPORATE_INDICATORS = [
    'holdings', 'ventures', 'capital', 'partners',
    'group inc', 'corporation', 'international',
    'north america', 'canada inc', 'llp'
]

# Office/suite indicators (manufacturing shouldn't be in office buildings)
OFFICE_INDICATORS = [
    'suite', 'floor', 'unit #', 'level', 'plaza',
    'tower', 'building', 'centre', 'complex'
]

# Excluded business types from Google Places
EXCLUDED_PLACE_TYPES = [
    'shopping_mall', 'department_store', 'supermarket',
    'convenience_store', 'gas_station', 'car_dealer',
    'real_estate_agency', 'lawyer', 'doctor',
    'bank', 'atm', 'insurance_agency'
]

# Minimum review threshold (chains have tons of reviews)
MAX_REVIEW_COUNT = 500  # If >500 reviews, likely a chain

# ===== HELPER FUNCTIONS =====

def normalize_text(text: str) -> str:
    """Normalize text for matching"""
    if not text:
        return ""
    return text.lower().strip()

def is_chain_or_franchise(name: str, types: List[str] = None) -> Tuple[bool, str]:
    """
    Check if business is a chain/franchise
    Returns (is_chain, reason)
    """
    name_norm = normalize_text(name)
    
    # Check chain keywords
    for keyword in CHAIN_KEYWORDS:
        if keyword in name_norm:
            return True, f"Chain keyword: '{keyword}'"
    
    # Check corporate indicators
    for indicator in CORPORATE_INDICATORS:
        if indicator in name_norm:
            # Exception: if it's clearly a small local business with corporate suffix
            if 'ltd' in name_norm or 'inc' in name_norm:
                # This is normal, don't reject
                pass
            else:
                return True, f"Corporate structure: '{indicator}'"
    
    # Check place types
    if types:
        for excluded_type in EXCLUDED_PLACE_TYPES:
            if excluded_type in types:
                return True, f"Excluded place type: '{excluded_type}'"
    
    return False, ""

def is_office_location(address: str, name: str) -> Tuple[bool, str]:
    """
    Check if location is in an office building
    Manufacturing should be in industrial areas, not office suites
    """
    address_norm = normalize_text(address)
    name_norm = normalize_text(name)
    
    # If business claims to be manufacturing/industrial but has office indicators
    if any(term in name_norm for term in ['manufacturing', 'machining', 'industrial', 'fabrication']):
        for indicator in OFFICE_INDICATORS:
            if indicator in address_norm:
                return True, f"Manufacturing business in office location: '{indicator}'"
    
    return False, ""

def estimate_size_from_reviews(rating_count: int) -> Tuple[bool, str]:
    """
    Estimate if business is too large based on review count
    Small SMBs don't have 500+ Google reviews
    """
    if rating_count > MAX_REVIEW_COUNT:
        return True, f"Too many reviews ({rating_count}), likely chain/large operation"
    
    return False, ""

def has_required_categories(types: List[str], categories: List[str]) -> Tuple[bool, str]:
    """
    Check if business has any of the required category indicators
    """
    if not types and not categories:
        return False, "No category information"
    
    required_categories = [
        'manufacturer', 'factory', 'machine_shop',
        'industrial', 'wholesale', 'distributor',
        'fabrication', 'machining', 'equipment',
        'printing', 'print_shop'
    ]
    
    all_categories = [normalize_text(t) for t in (types or []) + (categories or [])]
    
    for req_cat in required_categories:
        if any(req_cat in cat for cat in all_categories):
            return True, ""
    
    return False, "No relevant business category found"

# ===== MAIN PRE-QUALIFICATION FUNCTION =====

def pre_qualify_lead(place_data: Dict) -> Tuple[bool, str, Dict]:
    """
    Pre-qualify a Google Places result BEFORE enrichment
    
    Args:
        place_data: Dict from Google Places API with keys:
            - name: Business name
            - formatted_address: Full address
            - types: List of place types
            - user_ratings_total: Number of reviews
            - rating: Average rating
            - business_status: OPERATIONAL, CLOSED_TEMPORARILY, etc.
    
    Returns:
        (should_enrich, reason, metadata)
        - should_enrich: Boolean, True if lead should be enriched
        - reason: String explaining rejection if should_enrich=False
        - metadata: Dict with additional scoring info
    """
    metadata = {
        'pre_qualification_score': 50,
        'warning_flags': [],
        'positive_signals': []
    }
    
    name = place_data.get('name', '')
    address = place_data.get('formatted_address', '')
    types = place_data.get('types', [])
    rating_count = place_data.get('user_ratings_total', 0)
    business_status = place_data.get('business_status', 'OPERATIONAL')
    
    # === HARD REJECTIONS ===
    
    # 1. Business closed
    if business_status != 'OPERATIONAL':
        return False, f"Business status: {business_status}", metadata
    
    # 2. Chain/franchise check
    is_chain, chain_reason = is_chain_or_franchise(name, types)
    if is_chain:
        metadata['warning_flags'].append(chain_reason)
        return False, chain_reason, metadata
    
    # 3. Office location check (for manufacturing)
    is_office, office_reason = is_office_location(address, name)
    if is_office:
        metadata['warning_flags'].append(office_reason)
        return False, office_reason, metadata
    
    # 4. Size estimate from reviews
    too_large, size_reason = estimate_size_from_reviews(rating_count)
    if too_large:
        metadata['warning_flags'].append(size_reason)
        return False, size_reason, metadata
    
    # 5. Required category check
    has_category, category_reason = has_required_categories(types, [])
    if not has_category:
        metadata['warning_flags'].append(category_reason)
        return False, category_reason, metadata
    
    # === POSITIVE SIGNALS (adjust score) ===
    
    # Good review count (10-200 is sweet spot for SMB)
    if 10 <= rating_count <= 200:
        metadata['positive_signals'].append('Good review count for SMB')
        metadata['pre_qualification_score'] += 10
    
    # High rating
    rating = place_data.get('rating', 0)
    if rating >= 4.0:
        metadata['positive_signals'].append('High rating (≥4.0)')
        metadata['pre_qualification_score'] += 5
    
    # Has website
    if place_data.get('website'):
        metadata['positive_signals'].append('Has website')
        metadata['pre_qualification_score'] += 5
    
    # Has phone
    if place_data.get('formatted_phone_number'):
        metadata['positive_signals'].append('Has phone')
        metadata['pre_qualification_score'] += 5
    
    # Industrial area indicators in address
    industrial_keywords = ['industrial', 'park', 'avenue', 'road', 'drive', 'boulevard']
    if any(keyword in normalize_text(address) for keyword in industrial_keywords):
        metadata['positive_signals'].append('Industrial area location')
        metadata['pre_qualification_score'] += 5
    
    return True, "Pre-qualified for enrichment", metadata

# ===== BATCH PROCESSING =====

def pre_qualify_batch(places_results: List[Dict]) -> Dict:
    """
    Pre-qualify a batch of Google Places results
    
    Returns dict with:
        - qualified: List of places to enrich
        - rejected: List of rejected places with reasons
        - stats: Summary statistics
    """
    qualified = []
    rejected = []
    
    for place in places_results:
        should_enrich, reason, metadata = pre_qualify_lead(place)
        
        if should_enrich:
            qualified.append({
                **place,
                'pre_qualification_metadata': metadata
            })
        else:
            rejected.append({
                **place,
                'rejection_reason': reason,
                'pre_qualification_metadata': metadata
            })
    
    stats = {
        'total': len(places_results),
        'qualified': len(qualified),
        'rejected': len(rejected),
        'qualification_rate': len(qualified) / len(places_results) * 100 if places_results else 0
    }
    
    return {
        'qualified': qualified,
        'rejected': rejected,
        'stats': stats
    }

# ===== REFINED SEARCH QUERIES =====

def get_refined_search_queries(location: str = "Hamilton, ON") -> List[Dict]:
    """
    Generate refined Google Places search queries
    These are more specific than broad searches like "manufacturing Hamilton ON"
    """
    return [
        # Manufacturing - specific types
        {'query': f"metal fabrication {location}", 'category': 'manufacturing'},
        {'query': f"plastic manufacturing {location}", 'category': 'manufacturing'},
        {'query': f"food processing {location}", 'category': 'manufacturing'},
        {'query': f"industrial manufacturing {location}", 'category': 'manufacturing'},
        {'query': f"contract manufacturing {location}", 'category': 'manufacturing'},
        {'query': f"custom manufacturing {location}", 'category': 'manufacturing'},
        
        # Machining/Fabrication
        {'query': f"machine shop {location}", 'category': 'machining'},
        {'query': f"tool and die {location}", 'category': 'machining'},
        {'query': f"precision machining {location}", 'category': 'machining'},
        {'query': f"cnc machining {location}", 'category': 'machining'},
        {'query': f"metal fabrication shop {location}", 'category': 'fabrication'},
        
        # Industrial equipment
        {'query': f"industrial equipment {location}", 'category': 'industrial'},
        {'query': f"industrial supply {location}", 'category': 'industrial'},
        
        # Wholesale - specific
        {'query': f"wholesale distributor {location}", 'category': 'wholesale'},
        {'query': f"industrial distributor {location}", 'category': 'wholesale'},
        {'query': f"food wholesale {location}", 'category': 'wholesale'},
        
        # Equipment rental - local operations
        {'query': f"local equipment rental {location}", 'category': 'equipment_rental'},
        {'query': f"construction equipment rental {location}", 'category': 'equipment_rental'},
        
        # Printing - independent shops
        {'query': f"independent printing {location}", 'category': 'printing'},
        {'query': f"commercial printing {location}", 'category': 'printing'},
        {'query': f"print shop {location}", 'category': 'printing'},
        
        # Size indicators
        {'query': f"small manufacturing company {location}", 'category': 'manufacturing'},
        {'query': f"family owned manufacturing {location}", 'category': 'manufacturing'},
    ]

# ===== USAGE EXAMPLE =====

def example_usage():
    """
    Example of how to integrate pre-qualification into lead generation pipeline
    """
    
    print("=" * 70)
    print("PRE-QUALIFICATION PIPELINE EXAMPLE")
    print("=" * 70)
    
    # Step 1: Get refined queries
    queries = get_refined_search_queries("Hamilton, ON")
    print(f"\n1. Generated {len(queries)} refined search queries")
    
    # Step 2: Search Google Places (mock example)
    print("\n2. Searching Google Places...")
    # In real code: results = google_places_search(query)
    
    # Step 3: Pre-qualify results
    print("\n3. Pre-qualifying results...")
    
    # Mock example data
    example_places = [
        {
            'name': 'Smith Manufacturing Ltd',
            'formatted_address': '123 Industrial Drive, Hamilton, ON',
            'types': ['manufacturer', 'point_of_interest'],
            'user_ratings_total': 45,
            'rating': 4.3,
            'business_status': 'OPERATIONAL',
            'website': 'http://example.com',
            'formatted_phone_number': '(905) 555-1234'
        },
        {
            'name': 'Sunbelt Rentals',
            'formatted_address': '456 Main St, Hamilton, ON',
            'types': ['equipment_rental'],
            'user_ratings_total': 850,
            'rating': 4.1,
            'business_status': 'OPERATIONAL'
        }
    ]
    
    results = pre_qualify_batch(example_places)
    
    print(f"\n4. Pre-qualification Results:")
    print(f"   Total: {results['stats']['total']}")
    print(f"   Qualified: {results['stats']['qualified']}")
    print(f"   Rejected: {results['stats']['rejected']}")
    print(f"   Rate: {results['stats']['qualification_rate']:.1f}%")
    
    print("\n5. Qualified for enrichment:")
    for place in results['qualified']:
        print(f"   ✓ {place['name']}")
        print(f"     Score: {place['pre_qualification_metadata']['pre_qualification_score']}/100")
    
    print("\n6. Rejected:")
    for place in results['rejected']:
        print(f"   ✗ {place['name']}")
        print(f"     Reason: {place['rejection_reason']}")
    
    print("\n" + "=" * 70)
    print("NEXT STEP: Only enrich the qualified leads")
    print("This saves API costs and improves final qualification rate")
    print("=" * 70)

if __name__ == "__main__":
    example_usage()
