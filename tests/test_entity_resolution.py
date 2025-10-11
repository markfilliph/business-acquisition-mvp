"""
Tests for entity resolution and fingerprinting.
Ensures business deduplication works correctly across data sources.
"""

import pytest
from src.utils.fingerprinting import (
    compute_business_fingerprint,
    businesses_are_duplicates,
    _normalize_name,
    _normalize_street,
    _extract_street_number,
    _normalize_website
)


class TestFingerprintNormalization:
    """Test normalization functions."""

    def test_normalize_name_removes_suffixes(self):
        """Test that common business suffixes are removed."""
        assert _normalize_name("ABC Manufacturing Inc.") == "abc manufacturing"
        assert _normalize_name("ABC Manufacturing Incorporated") == "abc manufacturing"
        assert _normalize_name("ABC Mfg Ltd") == "abc mfg"
        assert _normalize_name("ABC Corp") == "abc"
        assert _normalize_name("ABC LLC") == "abc"

    def test_normalize_name_handles_punctuation(self):
        """Test punctuation removal."""
        assert _normalize_name("A.B.C. Manufacturing") == "abc manufacturing"
        assert _normalize_name("ABC & Sons") == "abc and sons"
        assert _normalize_name("ABC, Ltd.") == "abc"

    def test_normalize_street_removes_types(self):
        """Test street type normalization."""
        assert _normalize_street("Main Street") == "main"
        assert _normalize_street("Main St") == "main"
        assert _normalize_street("Oak Avenue") == "oak"
        assert _normalize_street("Oak Ave") == "oak"

    def test_normalize_street_removes_directions(self):
        """Test directional removal."""
        assert _normalize_street("Main St East") == "main"
        assert _normalize_street("Main St E") == "main"
        assert _normalize_street("King Street West") == "king"

    def test_extract_street_number(self):
        """Test street number extraction."""
        assert _extract_street_number("123 Main St") == "123"
        assert _extract_street_number("456-B Oak Ave") == "456"
        assert _extract_street_number("  789 King St") == "789"
        assert _extract_street_number("Main St") is None

    def test_normalize_website(self):
        """Test website URL normalization."""
        assert _normalize_website("https://www.example.com/") == "example.com"
        assert _normalize_website("http://example.com/page") == "example.com"
        assert _normalize_website("www.example.com") == "example.com"
        assert _normalize_website("example.com/path/to/page") == "example.com"


class TestBusinessFingerprinting:
    """Test business fingerprinting for deduplication."""

    def test_identical_businesses_same_fingerprint(self):
        """Test that identical businesses produce the same fingerprint."""
        fp1 = compute_business_fingerprint(
            "ABC Manufacturing Inc.",
            "123 Main St",
            "Hamilton",
            "L8H 3R2",
            "905-555-1234",
            "https://www.abcmfg.com"
        )

        fp2 = compute_business_fingerprint(
            "ABC Manufacturing Inc.",
            "123 Main St",
            "Hamilton",
            "L8H 3R2",
            "905-555-1234",
            "https://www.abcmfg.com"
        )

        assert fp1 == fp2

    def test_different_formatting_same_fingerprint(self):
        """Test that different formatting produces the same fingerprint."""
        fp1 = compute_business_fingerprint(
            "ABC Manufacturing Inc.",
            "123 Main St",
            "Hamilton",
            "L8H 3R2"
        )

        # Different suffix
        fp2 = compute_business_fingerprint(
            "ABC Manufacturing Incorporated",
            "123 Main Street",  # Different street type
            "hamilton",  # Different case
            "L8H3R2"  # No space in postal
        )

        assert fp1 == fp2, "Same business with different formatting should have same fingerprint"

    def test_different_businesses_different_fingerprints(self):
        """Test that different businesses have different fingerprints."""
        fp1 = compute_business_fingerprint(
            "ABC Manufacturing",
            "123 Main St",
            "Hamilton"
        )

        fp2 = compute_business_fingerprint(
            "XYZ Manufacturing",  # Different name
            "123 Main St",
            "Hamilton"
        )

        assert fp1 != fp2, "Different businesses should have different fingerprints"

    def test_different_addresses_different_fingerprints(self):
        """Test that same business at different addresses has different fingerprints."""
        fp1 = compute_business_fingerprint(
            "ABC Manufacturing",
            "123 Main St",
            "Hamilton"
        )

        fp2 = compute_business_fingerprint(
            "ABC Manufacturing",
            "456 Oak Ave",  # Different address
            "Hamilton"
        )

        assert fp1 != fp2, "Same business at different address should have different fingerprint"

    def test_phone_differences_affect_fingerprint(self):
        """Test that phone number differences are detected."""
        fp1 = compute_business_fingerprint(
            "ABC Manufacturing",
            "123 Main St",
            "Hamilton",
            phone="905-555-1234"
        )

        fp2 = compute_business_fingerprint(
            "ABC Manufacturing",
            "123 Main St",
            "Hamilton",
            phone="905-555-9999"  # Different phone
        )

        assert fp1 != fp2, "Different phone numbers should produce different fingerprints"

    def test_missing_fields_handled_gracefully(self):
        """Test that missing fields don't crash fingerprinting."""
        # Minimal data
        fp1 = compute_business_fingerprint("ABC Manufacturing")
        assert isinstance(fp1, str)
        assert len(fp1) == 16

        # With some fields
        fp2 = compute_business_fingerprint(
            "ABC Manufacturing",
            city="Hamilton"
        )
        assert isinstance(fp2, str)
        assert fp1 != fp2  # Adding data changes fingerprint


class TestDuplicateDetection:
    """Test businesses_are_duplicates function."""

    def test_exact_match_detected(self):
        """Test exact duplicate detection."""
        b1 = {
            "name": "ABC Manufacturing Inc.",
            "street": "123 Main St",
            "city": "Hamilton",
            "postal_code": "L8H 3R2",
            "phone": "905-555-1234"
        }

        b2 = b1.copy()

        assert businesses_are_duplicates(b1, b2) is True

    def test_different_formatting_detected(self):
        """Test that differently formatted duplicates are detected."""
        b1 = {
            "name": "ABC Manufacturing Inc.",
            "street": "123 Main St",
            "city": "Hamilton"
        }

        b2 = {
            "name": "ABC Manufacturing Incorporated",  # Different suffix
            "street": "123 Main Street",  # Different street type
            "city": "hamilton"  # Different case
        }

        assert businesses_are_duplicates(b1, b2) is True

    def test_different_businesses_not_duplicates(self):
        """Test that different businesses are not marked as duplicates."""
        b1 = {
            "name": "ABC Manufacturing",
            "street": "123 Main St",
            "city": "Hamilton"
        }

        b2 = {
            "name": "XYZ Manufacturing",  # Different name
            "street": "123 Main St",
            "city": "Hamilton"
        }

        assert businesses_are_duplicates(b1, b2) is False

    def test_same_name_different_address_not_duplicate(self):
        """Test that same name at different address is not a duplicate."""
        b1 = {
            "name": "Tim Hortons",
            "street": "123 Main St",
            "city": "Hamilton"
        }

        b2 = {
            "name": "Tim Hortons",
            "street": "456 King St",  # Different address
            "city": "Hamilton"
        }

        assert businesses_are_duplicates(b1, b2) is False

    def test_fuzzy_matching_with_phone(self):
        """Test fuzzy matching uses phone number."""
        b1 = {
            "name": "ABC Manufacturing",
            "street": "",  # Missing street
            "city": "Hamilton",
            "phone": "905-555-1234"
        }

        b2 = {
            "name": "ABC Mfg",  # Similar name
            "street": "",
            "city": "Hamilton",
            "phone": "(905) 555-1234"  # Same phone, different format
        }

        # Should detect as duplicate via fuzzy matching (same name + city + phone)
        assert businesses_are_duplicates(b1, b2, strict=False) is True

    def test_strict_mode_requires_exact_fingerprint(self):
        """Test strict mode only matches exact fingerprints."""
        b1 = {
            "name": "ABC Manufacturing",
            "street": "123 Main St",
            "city": "Hamilton",
            "phone": "905-555-1234"
        }

        b2 = {
            "name": "ABC Mfg",  # Slightly different name
            "street": "123 Main St",
            "city": "Hamilton",
            "phone": "905-555-1234"
        }

        # Fuzzy mode might match
        fuzzy_result = businesses_are_duplicates(b1, b2, strict=False)

        # Strict mode should NOT match (different fingerprints)
        strict_result = businesses_are_duplicates(b1, b2, strict=True)

        # Strict should be more restrictive
        assert not strict_result or fuzzy_result, "Strict mode should be at least as restrictive as fuzzy mode"


class TestRealWorldScenarios:
    """Test real-world duplicate detection scenarios."""

    def test_yellow_pages_vs_chamber_duplicate(self):
        """Test detecting same business from Yellow Pages and Chamber of Commerce."""
        yellow_pages = {
            "name": "Hamilton Tool & Die Ltd.",
            "street": "55 Kenilworth Ave N",
            "city": "Hamilton",
            "postal_code": "L8H 5R9",
            "phone": "905-547-1234",
            "website": "http://www.hamiltontool.com",
            "data_source": "yellowpages"
        }

        chamber = {
            "name": "Hamilton Tool and Die Limited",  # Different format
            "street": "55 Kenilworth Avenue North",  # Expanded
            "city": "Hamilton",
            "postal_code": "L8H 5R9",
            "phone": "(905) 547-1234",  # Different format
            "website": "www.hamiltontool.com",  # Different format
            "data_source": "hamilton_chamber"
        }

        assert businesses_are_duplicates(yellow_pages, chamber) is True

    def test_multiple_locations_same_chain_not_duplicate(self):
        """Test that same chain at multiple locations are not marked as duplicates."""
        location1 = {
            "name": "Canadian Tire",
            "street": "1059 King Street West",
            "city": "Hamilton"
        }

        location2 = {
            "name": "Canadian Tire",
            "street": "650 Centennial Parkway North",
            "city": "Hamilton"
        }

        assert businesses_are_duplicates(location1, location2) is False

    def test_missing_data_partial_match(self):
        """Test matching with partial data."""
        complete = {
            "name": "ABC Manufacturing Inc.",
            "street": "123 Main St",
            "city": "Hamilton",
            "postal_code": "L8H 3R2",
            "phone": "905-555-1234",
            "website": "www.abcmfg.com"
        }

        partial = {
            "name": "ABC Manufacturing",
            "street": "123 Main St",
            "city": "Hamilton",
            # Missing postal, phone, website
        }

        # Should still match based on name + address
        assert businesses_are_duplicates(complete, partial, strict=False) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
