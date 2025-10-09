"""
Golden test cases from diagnosis - regression prevention.
Tests known failure and success cases from IMPLEMENTATION_PLAN_UPDATES.md
"""

import pytest
from src.services.new_validation_service import ValidationService
from src.core.normalization import compute_fingerprint


class TestCategoryGate:
    """Test category validation gate with known cases."""

    def setup_method(self):
        self.validator = ValidationService()

    # Known failures from diagnosis
    GOLDEN_FAILURES = [
        {
            'name': 'Eastgate Variety',
            'address': '1505 Main St E, Hamilton',
            'place_types': ['convenience_store', 'variety_store'],
            'expected_reason_contains': 'blacklist'
        },
        {
            'name': 'Pioneer',
            'address': '603 King St E, Hamilton',
            'place_types': ['gas_station', 'convenience_store'],
            'expected_reason_contains': 'gas_station'
        },
        {
            'name': 'Performance Improvements',
            'place_types': ['auto_parts', 'retail_general'],
            'expected_reason_contains': 'blacklist'
        },
        {
            'name': 'Worldwide Mattress Outlet',
            'place_types': ['mattress_store', 'retail_general'],
            'expected_reason_contains': 'mattress'
        },
        {
            'name': 'Mountain Hyundai',
            'place_types': ['car_dealer'],
            'expected_reason_contains': 'dealer'
        },
    ]

    @pytest.mark.parametrize("case", GOLDEN_FAILURES)
    def test_known_failures_blocked(self, case):
        """Ensure known bad leads are blocked."""
        business = {'name': case['name']}
        passed, reason, action = self.validator.category_gate(business, case['place_types'])

        assert not passed, f"Expected {case['name']} to fail category gate"
        assert case['expected_reason_contains'] in reason.lower(), \
            f"Expected reason to contain '{case['expected_reason_contains']}', got: {reason}"
        assert action == 'AUTO_EXCLUDE', f"Expected AUTO_EXCLUDE, got: {action}"

    # Known passes
    GOLDEN_PASSES = [
        {
            'name': 'Landtek Limited',
            'address': '1234 Industrial Dr, Hamilton',
            'place_types': ['engineering_consulting', 'geotechnical_services'],
            'expected_pass': True
        },
        {
            'name': 'Valid Manufacturing Co',
            'address': '123 Industrial Dr, Hamilton',
            'place_types': ['manufacturing', 'industrial_equipment'],
            'expected_pass': True
        },
    ]

    @pytest.mark.parametrize("case", GOLDEN_PASSES)
    def test_known_passes_allowed(self, case):
        """Ensure valid leads pass gates."""
        business = {'name': case['name']}
        passed, reason, action = self.validator.category_gate(business, case['place_types'])

        assert passed == case['expected_pass'], \
            f"Expected {case['name']} to pass category gate, got: {reason}"


class TestGeoGate:
    """Test geographic validation gate."""

    def setup_method(self):
        self.validator = ValidationService()

    def test_within_radius_passes(self):
        """Business within Hamilton radius should pass."""
        business = {
            'name': 'Test Business',
            'latitude': 43.2557,  # Ancaster
            'longitude': -79.9537,
            'city': 'Hamilton'
        }

        passed, reason, action = self.validator.geo_gate(business)

        assert passed, f"Expected pass, got: {reason}"
        assert business['distance_km'] < 1.0  # Very close to centroid

    def test_outside_radius_fails(self):
        """Business in Burlington (outside radius) should fail."""
        business = {
            'name': 'Dee Signs',
            'latitude': 43.3255,  # Burlington
            'longitude': -79.7990,
            'city': 'Burlington'
        }

        passed, reason, action = self.validator.geo_gate(business)

        assert not passed, "Expected Burlington location to fail"
        assert 'outside target radius' in reason.lower()
        assert action == 'AUTO_EXCLUDE'

    def test_not_geocoded_requires_review(self):
        """Business without coordinates should require review."""
        business = {
            'name': 'Test Business',
            'city': 'Hamilton'
        }

        passed, reason, action = self.validator.geo_gate(business)

        assert not passed
        assert action == 'REVIEW_REQUIRED'


class TestCorroborationGate:
    """Test field corroboration with multiple sources."""

    def setup_method(self):
        self.validator = ValidationService()

    def test_postal_mismatch_requires_review(self):
        """
        1-vs-1 postal code conflict should require human review.
        Test case from diagnosis: Pardon Applications (L4P vs L8P)
        """
        from src.core.evidence import Observation

        observations = [
            Observation(business_id=1, source_url='source1', field='postal_code', value='L4P 1A1'),
            Observation(business_id=1, source_url='source2', field='postal_code', value='L8P 4W7')
        ]

        passed, reason, action = self.validator.corroboration_gate(observations, 'postal_code', min_sources=2)

        assert not passed, "Mismatched postal codes should fail corroboration"
        assert '1-vs-1 conflict' in reason.lower()
        assert action == 'REVIEW_REQUIRED'

    def test_address_corroboration_passes(self):
        """Two sources agreeing on address should pass."""
        from src.core.evidence import Observation

        observations = [
            Observation(business_id=1, source_url='website', field='address', value='123 Main St, Hamilton, ON'),
            Observation(business_id=1, source_url='yelp', field='address', value='123 Main Street, Hamilton ON')
        ]

        passed, reason, action = self.validator.corroboration_gate(observations, 'address', min_sources=2)

        assert passed, f"Matching addresses should pass: {reason}"

    def test_single_source_requires_review(self):
        """Only one source for field should require review."""
        from src.core.evidence import Observation

        observations = [
            Observation(business_id=1, source_url='website', field='phone', value='905-555-1234')
        ]

        passed, reason, action = self.validator.corroboration_gate(observations, 'phone', min_sources=2)

        assert not passed
        assert action == 'REVIEW_REQUIRED'


class TestFingerprinting:
    """Test entity resolution fingerprinting."""

    def test_same_business_same_fingerprint(self):
        """Same business with slight variations should have same fingerprint."""
        business1 = {
            'name': 'ABC Manufacturing Inc.',
            'street': '123 Main St',
            'city': 'Hamilton',
            'postal_code': 'L8H 3R2',
            'phone': '905-555-1234'
        }

        business2 = {
            'name': 'ABC Manufacturing',  # No Inc.
            'street': '123 Main Street',  # Full "Street"
            'city': 'Hamilton',
            'postal_code': 'L8H 3R2',
            'phone': '(905) 555-1234'  # Formatted differently
        }

        fp1 = compute_fingerprint(business1)
        fp2 = compute_fingerprint(business2)

        assert fp1 == fp2, "Same business should have same fingerprint"

    def test_different_businesses_different_fingerprint(self):
        """Different businesses should have different fingerprints."""
        business1 = {
            'name': 'ABC Manufacturing',
            'street': '123 Main St',
            'city': 'Hamilton',
            'postal_code': 'L8H 3R2'
        }

        business2 = {
            'name': 'XYZ Manufacturing',
            'street': '123 Main St',
            'city': 'Hamilton',
            'postal_code': 'L8H 3R2'
        }

        fp1 = compute_fingerprint(business1)
        fp2 = compute_fingerprint(business2)

        assert fp1 != fp2, "Different businesses should have different fingerprints"


class TestWebsiteGate:
    """Test website age validation."""

    def setup_method(self):
        self.validator = ValidationService()

    def test_old_website_passes(self):
        """Website older than 3 years should pass."""
        business = {
            'website_ok': True,
            'website_age_years': 5.0
        }

        passed, reason, action = self.validator.website_gate(business, min_age_years=3)

        assert passed

    def test_new_website_fails(self):
        """Website younger than 3 years should fail."""
        business = {
            'website_ok': True,
            'website_age_years': 2.0
        }

        passed, reason, action = self.validator.website_gate(business, min_age_years=3)

        assert not passed
        assert action == 'AUTO_EXCLUDE'

    def test_borderline_website_requires_review(self):
        """Website 2.5-3.0 years should require review."""
        business = {
            'website_ok': True,
            'website_age_years': 2.8
        }

        passed, reason, action = self.validator.website_gate(business, min_age_years=3)

        assert not passed
        assert action == 'REVIEW_REQUIRED'


class TestRevenueGate:
    """Test strict revenue validation."""

    def setup_method(self):
        self.validator = ValidationService()

    def test_high_confidence_with_staff_passes(self):
        """Revenue with confidence >= 0.6 and staff signal should pass."""
        business = {
            'revenue_estimate': {
                'revenue_min': 1000000,
                'confidence': 0.7,
                'methodology': 'staff_based'
            },
            'staff_count': 12
        }

        passed, reason, action = self.validator.revenue_gate(business)

        assert passed

    def test_low_confidence_fails(self):
        """Revenue with confidence < 0.6 should fail."""
        business = {
            'revenue_estimate': {
                'revenue_min': 1000000,
                'confidence': 0.4,
                'methodology': 'benchmark'
            },
            'staff_count': None
        }

        passed, reason, action = self.validator.revenue_gate(business)

        assert not passed
        assert 'too low' in reason.lower()

    def test_no_signals_fails(self):
        """High confidence but no underlying signals should fail."""
        business = {
            'revenue_estimate': {
                'revenue_min': 1000000,
                'confidence': 0.7,
                'methodology': 'unknown'
            },
            'staff_count': None,
            'category_benchmark': None
        }

        passed, reason, action = self.validator.revenue_gate(business)

        assert not passed
        assert 'no staff signal' in reason.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
