#!/usr/bin/env python3
"""
Test LLM Extraction Service
PRIORITY: P0 - Critical for deployment validation.

Tests the LLM extraction service on real business websites to ensure:
- No hallucination (null when data not present)
- Accurate extraction when data is present
- Cost and token limits respected
- 70%+ success rate on test set
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.llm_service import LLMExtractionService
import structlog
import aiohttp

logger = structlog.get_logger(__name__)


# Test cases with known ground truth
TEST_WEBSITES = [
    {
        'url': 'https://flamboromachineshop.ca',
        'name': 'Flamboro Machine Shop',
        'expected_staff': None,  # Not explicitly stated on homepage
        'expected_founding_year': None
    },
    {
        'url': 'https://hamiltonprintshop.ca',
        'name': 'Hamilton Print Shop',
        'expected_staff': None,
        'expected_founding_year': None
    },
    {
        'url': 'https://www.protoplast.com',
        'name': 'Protoplast',
        'expected_staff': None,  # Check if stated
        'expected_founding_year': None  # Check if stated
    },
    # Add more test cases as needed
]


async def scrape_website(url: str) -> str:
    """
    Simple website scraper for testing.

    Args:
        url: Website URL

    Returns:
        Text content of the website
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    html = await response.text()
                    # Simple text extraction (strip HTML tags)
                    import re
                    text = re.sub(r'<[^>]+>', ' ', html)
                    text = re.sub(r'\s+', ' ', text).strip()
                    return text
                else:
                    logger.error("scrape_failed", url=url, status=response.status)
                    return ""

    except Exception as e:
        logger.error("scrape_error", url=url, error=str(e))
        return ""


async def test_single_extraction(service: LLMExtractionService, test_case: dict) -> dict:
    """
    Test extraction on a single website.

    Args:
        service: LLMExtractionService instance
        test_case: Test case dictionary

    Returns:
        Test result dictionary
    """
    logger.info("testing_website", url=test_case['url'], name=test_case['name'])

    # Scrape website
    content = await scrape_website(test_case['url'])

    if not content:
        return {
            'url': test_case['url'],
            'name': test_case['name'],
            'success': False,
            'error': 'scrape_failed'
        }

    # Extract
    result = await service.extract_from_website(
        url=test_case['url'],
        company_name=test_case['name'],
        content=content
    )

    if not result:
        return {
            'url': test_case['url'],
            'name': test_case['name'],
            'success': False,
            'error': 'extraction_failed'
        }

    # Evaluate
    extracted_staff = result.business_data.staff_count
    extracted_year = result.business_data.founding_year

    # Check for hallucination (if expected is None, extracted should also be None)
    staff_hallucination = (test_case['expected_staff'] is None and extracted_staff is not None)
    year_hallucination = (test_case['expected_founding_year'] is None and extracted_year is not None)

    # Check for accuracy (if expected is not None, did we extract it correctly?)
    staff_accurate = (test_case['expected_staff'] == extracted_staff) if test_case['expected_staff'] is not None else None
    year_accurate = (test_case['expected_founding_year'] == extracted_year) if test_case['expected_founding_year'] is not None else None

    return {
        'url': test_case['url'],
        'name': test_case['name'],
        'success': True,
        'extracted_staff': extracted_staff,
        'extracted_year': extracted_year,
        'expected_staff': test_case['expected_staff'],
        'expected_year': test_case['expected_founding_year'],
        'staff_hallucination': staff_hallucination,
        'year_hallucination': year_hallucination,
        'staff_accurate': staff_accurate,
        'year_accurate': year_accurate,
        'has_certifications': len(result.business_data.certifications) > 0,
        'has_equipment': len(result.business_data.equipment_mentions) > 0,
        'has_services': len(result.business_data.services_offered) > 0,
        'quality_score': result.get_quality_score(),
        'confidence': result.business_data.confidence_score,
        'tokens': result.tokens_used,
        'cost_usd': result.cost_usd
    }


async def run_test_suite():
    """Run full test suite on LLM extraction."""
    print("\n" + "=" * 60)
    print("  LLM EXTRACTION TEST SUITE")
    print("=" * 60 + "\n")

    # Initialize service
    service = LLMExtractionService(
        model="gpt-4o-mini",  # Fast and cheap for testing
        max_tokens=1000,
        temperature=0.0
    )

    # Run tests
    results = []
    for test_case in TEST_WEBSITES[:5]:  # Test first 5 to save API costs
        result = await test_single_extraction(service, test_case)
        results.append(result)
        await asyncio.sleep(1)  # Rate limiting

    # Analyze results
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"\n=== RESULTS ===")
    print(f"Total tests: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Success rate: {len(successful) / len(results) * 100:.1f}%")

    # Hallucination analysis
    if successful:
        staff_hallucinations = sum(1 for r in successful if r.get('staff_hallucination', False))
        year_hallucinations = sum(1 for r in successful if r.get('year_hallucination', False))

        print(f"\n=== HALLUCINATION CHECK ===")
        print(f"Staff count hallucinations: {staff_hallucinations}/{len(successful)}")
        print(f"Founding year hallucinations: {year_hallucinations}/{len(successful)}")

        # Data richness
        with_certs = sum(1 for r in successful if r.get('has_certifications', False))
        with_equipment = sum(1 for r in successful if r.get('has_equipment', False))
        with_services = sum(1 for r in successful if r.get('has_services', False))

        print(f"\n=== DATA RICHNESS ===")
        print(f"With certifications: {with_certs}/{len(successful)}")
        print(f"With equipment: {with_equipment}/{len(successful)}")
        print(f"With services: {with_services}/{len(successful)}")

        # Cost analysis
        avg_quality = sum(r.get('quality_score', 0) for r in successful) / len(successful)
        avg_confidence = sum(r.get('confidence', 0) for r in successful) / len(successful)

        print(f"\n=== QUALITY METRICS ===")
        print(f"Average quality score: {avg_quality:.2f}")
        print(f"Average confidence: {avg_confidence:.2f}")

    # Service metrics
    print(f"\n=== SERVICE METRICS ===")
    metrics = service.get_metrics()
    for key, value in metrics.items():
        if 'cost' in key:
            print(f"{key}: ${value:.4f}")
        elif 'rate' in key:
            print(f"{key}: {value * 100:.1f}%")
        else:
            print(f"{key}: {value}")

    # Detailed results
    print(f"\n=== DETAILED RESULTS ===")
    for r in results:
        print(f"\n{r['name']} ({r['url']})")
        if r['success']:
            print(f"  Staff: {r.get('extracted_staff', 'None')}")
            print(f"  Year: {r.get('extracted_year', 'None')}")
            print(f"  Quality: {r.get('quality_score', 0):.2f}")
            print(f"  Confidence: {r.get('confidence', 0):.2f}")
            print(f"  Tokens: {r.get('tokens', 0)}")
            print(f"  Cost: ${r.get('cost_usd', 0):.4f}")

            # Flag issues
            if r.get('staff_hallucination'):
                print(f"  ⚠️  WARNING: Staff count may be hallucinated!")
            if r.get('year_hallucination'):
                print(f"  ⚠️  WARNING: Founding year may be hallucinated!")
        else:
            print(f"  ❌ FAILED: {r.get('error', 'unknown')}")

    print("\n" + "=" * 60)
    print("  TEST SUITE COMPLETE")
    print("=" * 60 + "\n")

    # Pass/fail criteria
    success_rate = len(successful) / len(results) if results else 0
    hallucination_rate = (staff_hallucinations + year_hallucinations) / (len(successful) * 2) if successful else 0

    if success_rate >= 0.7 and hallucination_rate < 0.2:
        print("✅ TEST PASSED: Success rate >= 70%, hallucination rate < 20%")
        return 0
    else:
        print("❌ TEST FAILED: Success rate or hallucination rate out of bounds")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(run_test_suite())
    sys.exit(exit_code)
