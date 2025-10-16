"""
Business category rules: whitelists, blacklists, and patterns.
"""

# Positive whitelist (allowed business types)
TARGET_WHITELIST = {
    # Manufacturing & Industrial
    'manufacturing', 'printing', 'sign_shop', 'industrial_equipment',
    'equipment_rental', 'wholesale_distribution', 'fabrication',
    'metal_fabrication', 'plastic_manufacturing', 'food_manufacturing',
    'chemical_manufacturing', 'textile_manufacturing',

    # Professional Services (B2B)
    'engineering_consulting', 'environmental_consulting',
    'geotechnical_services', 'commercial_services', 'business_consulting',
    'logistics', 'warehousing', 'packaging_services',
    'it_consulting', 'management_consulting', 'marketing_agency',

    # Specialized services
    'commercial_printing', 'industrial_design', 'trade_services_commercial',
    'commercial_cleaning', 'facility_management', 'security_services',
    'commercial_landscaping', 'property_management_commercial',

    # General B2B (for sources with limited categorization)
    'general_business', 'industrial', 'commercial'
}

# Negative blacklist (explicitly excluded)
CATEGORY_BLACKLIST = {
    # Retail
    'convenience_store', 'gas_station', 'mattress_store', 'furniture_store',
    'car_dealer', 'auto_dealership', 'retail_general', 'boutique', 'outlet',
    'variety_store', 'dollar_store', 'vape_shop', 'liquor_store', 'cannabis',
    'pet_store', 'clothing_store', 'electronics_store', 'toy_store',
    'jewelry_store', 'gift_shop', 'bookstore', 'sporting_goods',

    # Personal services
    'barber', 'salon', 'nail_salon', 'spa', 'massage', 'tattoo', 'piercing',
    'gym', 'fitness_center', 'yoga_studio', 'personal_training',

    # Food & hospitality
    'restaurant', 'cafe', 'bar', 'food_truck', 'catering_retail',
    'bakery_retail', 'coffee_shop', 'fast_food', 'pizzeria',

    # Financial services (franchises)
    'bank_branch', 'insurance_agent', 'financial_advisor_franchise',
    'mortgage_broker', 'tax_preparation', 'accounting_retail',

    # Skilled trades (per README exclusion)
    'welding', 'hvac', 'roofing', 'plumbing', 'electrical', 'construction',
    'machining', 'carpentry', 'painting_residential', 'flooring',
    'drywall', 'masonry', 'landscaping_residential',

    # Auto services
    'auto_repair', 'towing', 'car_wash', 'auto_body', 'auto_parts',
    'tire_shop', 'oil_change', 'auto_detailing',

    # Other excluded
    'funeral_home', 'pawn_shop', 'payday_loans', 'check_cashing',
    'daycare', 'veterinary', 'medical_clinic', 'dental_office',
    'law_office', 'real_estate_agent', 'agr_tourism', 'farm_shop'
}

# Name pattern blacklist (regex)
NAME_BLACKLIST_PATTERNS = [
    # Retail indicators
    r'variety|mart|mattress|outlet',

    # Auto dealerships
    r'hyundai|toyota|honda|ford|chevrolet|nissan|mazda|subaru|bmw|mercedes|audi',
    r'kia|volkswagen|gmc|dodge|chrysler|jeep|ram|buick|cadillac',

    # Personal services
    r'nails?|salon|barber|spa|beauty|massage|tattoo',

    # Gas stations
    r'gas|petro|shell|esso|convenience|circle\s*k|7-eleven',

    # Retail/hospitality
    r'tobacco|vape|cannabis|liquor|beer\s*store',
    r'pawn|payday|outlet',
    r'restaurant|cafe|bistro|grill|pizza|burger|sushi',

    # Funeral
    r'funeral|memorial|cremation',

    # Franchise financial services
    r'edward\s+jones|state\s+farm|allstate|farmers\s+insurance',

    # Medical/legal
    r'clinic|medical|dental|orthodontic|optometry',
    r'law\s+office|attorney|legal\s+services',

    # Real estate
    r'realty|real\s+estate|realtor',

    # Auto services
    r'auto\s+repair|car\s+wash|tire\s+shop|muffler',

    # Retail chains
    r'walmart|costco|target|dollarama|canadian\s+tire'
]

# Categories that require manual review (borderline cases)
REVIEW_REQUIRED_CATEGORIES = {
    'funeral_home': 'High owner reliance, borderline',
    'franchise_office': 'Verify actual business vs franchise agent',
    'sign_shop': 'Verify B2B focus and website age >= 3 years'
}

# Geographic configuration (Hamilton/Ancaster target)
GEO_CONFIG = {
    'centroid_lat': 43.2557,    # Ancaster, ON
    'centroid_lng': -79.9537,
    'max_radius_km': 20,
    'allowed_cities': ['Hamilton', 'Ancaster', 'Dundas', 'Stoney Creek', 'Waterdown', 'Flamborough']
}

# Validation configuration
VALIDATION_CONFIG = {
    'min_corroboration_sources': 2,
    'min_website_age_years': 3,
    'min_revenue_confidence': 0.6,
    'require_staff_signal_or_benchmark': True,
    'current_validation_version': 1
}

# Export configuration
DEFAULT_EXPORT_CONFIG = {
    'TARGET_WHITELIST': TARGET_WHITELIST,
    'MAX_RADIUS_KM': GEO_CONFIG['max_radius_km'],
    'MIN_WEBSITE_AGE_YEARS': VALIDATION_CONFIG['min_website_age_years'],
    'MIN_CORROBORATION_SOURCES': VALIDATION_CONFIG['min_corroboration_sources'],
    'MIN_REVENUE_CONFIDENCE': VALIDATION_CONFIG['min_revenue_confidence'],
    'REQUIRE_STAFF_OR_BENCHMARK': VALIDATION_CONFIG['require_staff_signal_or_benchmark']
}
