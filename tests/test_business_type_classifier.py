#!/usr/bin/env python3
"""
Test script for Business Type Classifier
Verifies that convenience stores, gas stations, and other excluded types are properly detected.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.business_type_classifier import BusinessTypeClassifier
from src.core.models import BusinessLead, ContactInfo, LocationInfo


async def test_business_type_classifier():
    """Test the business type classifier with various business types."""

    classifier = BusinessTypeClassifier()

    # Test cases: (business_name, website, expected_result, description)
    test_cases = [
        # Convenience stores - SHOULD BE REJECTED
        ("Circle K", "https://www.circlek.com", False, "Major convenience store chain"),
        ("Mac's Convenience", None, False, "Convenience store keyword in name"),
        ("Hasty Market Hamilton", None, False, "Convenience store chain"),
        ("7-Eleven", "https://www.7-eleven.com", False, "International convenience chain"),

        # Gas stations - SHOULD BE REJECTED
        ("Esso Gas Station", None, False, "Gas station - Esso brand"),
        ("Petro-Canada", "https://www.petro-canada.ca", False, "Gas station chain"),
        ("Shell Hamilton", None, False, "Gas station - Shell brand"),

        # Retail chains - SHOULD BE REJECTED
        ("Canadian Tire", "https://www.canadiantire.ca", False, "Major retail chain"),
        ("Walmart", "https://www.walmart.ca", False, "Big box retail"),

        # Fast food franchises - SHOULD BE REJECTED
        ("McDonald's", "https://www.mcdonalds.com", False, "Fast food franchise"),
        ("Tim Hortons", "https://www.timhortons.com", False, "Coffee/fast food chain"),

        # Grocery stores - SHOULD BE REJECTED
        ("Fortinos", "https://www.fortinos.ca", False, "Grocery store chain"),
        ("Food Basics", None, False, "Grocery store chain"),

        # Manufacturing - SHOULD BE APPROVED
        ("Hamilton Metal Fabrication Inc.", "https://example-metal-fab.com", True, "Metal fabrication company"),
        ("Advanced Manufacturing Solutions", None, True, "Manufacturing business"),
        ("Precision Machine Shop", "https://example-machine.com", True, "Machine shop"),

        # Professional services - SHOULD BE APPROVED
        ("Hamilton Business Consulting Ltd.", "https://example-consulting.com", True, "Consulting firm"),
        ("Professional Services Group", None, True, "Professional services"),

        # Printing - SHOULD BE APPROVED
        ("Hamilton Print Shop", "https://hamiltonprintshop.ca", True, "Printing business"),
        ("Commercial Graphics Ltd.", None, True, "Graphics/printing"),

        # Edge cases
        ("Hamilton Convenience Manufacturing", None, True, "Manufacturing with 'convenience' in name - should check deeper"),
    ]

    print("=" * 80)
    print("BUSINESS TYPE CLASSIFIER TEST")
    print("=" * 80)
    print()

    passed = 0
    failed = 0
    results = []

    for business_name, website, expected_suitable, description in test_cases:
        # Create a test lead
        lead = BusinessLead(
            business_name=business_name,
            industry="unknown",
            contact=ContactInfo(
                phone="(905) 555-1234",
                email="info@example.com",
                website=website
            ),
            location=LocationInfo(
                address="123 Main St",
                city="Hamilton",
                province="ON",
                postal_code="L8N 1A1",
                country="Canada"
            ),
            years_in_business=10,
            employee_count=15
        )

        # Test classification
        is_suitable, reason, evidence = await classifier.classify_business_type(lead)

        # Check result
        test_passed = (is_suitable == expected_suitable)
        status = "✓ PASS" if test_passed else "✗ FAIL"

        if test_passed:
            passed += 1
        else:
            failed += 1

        results.append({
            'business_name': business_name,
            'description': description,
            'expected': 'APPROVED' if expected_suitable else 'REJECTED',
            'actual': 'APPROVED' if is_suitable else 'REJECTED',
            'reason': reason,
            'status': status,
            'evidence': evidence
        })

        print(f"{status} | {business_name}")
        print(f"     Description: {description}")
        print(f"     Expected: {results[-1]['expected']}, Got: {results[-1]['actual']}")
        print(f"     Reason: {reason}")

        # Show evidence for failed tests
        if not test_passed and evidence:
            print(f"     Evidence:")
            print(f"       - Keyword matches: {len(evidence.get('keyword_matches', []))}")
            website_analysis = evidence.get('website_analysis', {})
            if website_analysis:
                print(f"       - Website indicators: {len(website_analysis.get('category_indicators', []))}")
            yp_category = evidence.get('yellowpages_category', {})
            if yp_category:
                print(f"       - YP categories: {yp_category.get('categories', [])}")

        print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {len(test_cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {(passed / len(test_cases) * 100):.1f}%")
    print()

    # Show classifier statistics
    stats = classifier.get_classification_stats()
    print("Classifier Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    # Show failed tests in detail
    if failed > 0:
        print("=" * 80)
        print("FAILED TESTS DETAIL")
        print("=" * 80)
        for result in results:
            if result['status'] == "✗ FAIL":
                print(f"\nBusiness: {result['business_name']}")
                print(f"Expected: {result['expected']}")
                print(f"Got: {result['actual']}")
                print(f"Reason: {result['reason']}")
                print(f"Evidence: {result['evidence']}")

    return passed, failed


if __name__ == "__main__":
    print("\nStarting Business Type Classifier Tests...\n")
    passed, failed = asyncio.run(test_business_type_classifier())

    # Exit with error code if any tests failed
    sys.exit(0 if failed == 0 else 1)
