"""
Tests for address normalization and matching.
Ensures Canada Post-compliant address parsing and fuzzy matching work correctly.
"""

import pytest
from src.utils.address_normalizer import (
    normalize_address,
    addresses_match,
    parse_street_number,
    CANADA_POST_ABBREV
)


class TestAddressNormalization:
    """Test address parsing and normalization."""

    def test_simple_address(self):
        """Test simple address parsing."""
        result = normalize_address("123 Main St, Hamilton, ON L8H 3R2")

        assert result['street_number'] == '123'
        assert result['street_name'] == 'Main'
        assert result['street_type'] == 'Street'
        assert result['city'] == 'Hamilton'
        assert result['province'] == 'ON'
        assert result['postal_code'] == 'L8H 3R2'

    def test_address_with_direction(self):
        """Test address with directional."""
        result = normalize_address("456 King St E, Hamilton, ON")

        assert result['street_number'] == '456'
        assert result['street_name'] == 'King'
        assert result['street_type'] == 'Street'
        assert result['street_direction'] == 'East'
        assert result['city'] == 'Hamilton'

    def test_address_with_unit(self):
        """Test address with unit number."""
        result = normalize_address("789 Oak Ave, Unit 7, Hamilton")

        assert result['street_number'] == '789'
        assert result['street_name'] == 'Oak'
        assert result['street_type'] == 'Avenue'
        assert result['unit'] in ['Unit 7', '7']  # Either format OK

    def test_abbreviation_expansion(self):
        """Test that abbreviations are expanded."""
        result = normalize_address("100 Blvd Dr, Hamilton")

        assert result['street_type'] == 'Boulevard' or result['street_type'] == 'Drive'

    def test_postal_code_formats(self):
        """Test different postal code formats."""
        # With space
        result1 = normalize_address("123 Main St, Hamilton, ON L8H 3R2")
        assert result1['postal_code'] == 'L8H 3R2'

        # Without space
        result2 = normalize_address("123 Main St, Hamilton, ON L8H3R2")
        assert result2['postal_code'] == 'L8H 3R2'

    def test_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        result = normalize_address("123 main STREET, hamilton, on")

        assert result['street_name'] == 'Main'
        assert result['street_type'] == 'Street'
        assert result['city'] == 'Hamilton'

    def test_minimal_address(self):
        """Test parsing with minimal information."""
        result = normalize_address("123 Main")

        assert result['street_number'] == '123'
        assert result['street_name'] == 'Main'

    def test_empty_address(self):
        """Test handling of empty address."""
        result = normalize_address("")

        assert result['street_number'] == ''
        assert result['normalized'] == ''
        assert result['original'] == ''


class TestAddressMatching:
    """Test address comparison and matching."""

    def test_exact_match(self):
        """Test that identical addresses match."""
        addr1 = "123 Main St, Hamilton, ON"
        addr2 = "123 Main St, Hamilton, ON"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is True
        assert confidence >= 0.9

    def test_abbreviation_match(self):
        """Test that 'St' matches 'Street'."""
        addr1 = "123 Main St, Hamilton"
        addr2 = "123 Main Street, Hamilton"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is True, "St and Street should match"
        assert confidence >= 0.8

    def test_direction_match(self):
        """Test that 'E' matches 'East'."""
        addr1 = "456 King St E, Hamilton"
        addr2 = "456 King Street East, Hamilton"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is True
        assert confidence >= 0.8

    def test_unit_variation_match(self):
        """Test that different unit formats match."""
        addr1 = "789 Oak Ave, Unit 7, Hamilton"
        addr2 = "789 Oak Avenue #7, Hamilton"

        is_match, confidence = addresses_match(addr1, addr2, fuzzy=True)

        # Should match or be high confidence
        assert confidence >= 0.7

    def test_different_street_numbers_no_match(self):
        """Test that different street numbers don't match."""
        addr1 = "123 Main St, Hamilton"
        addr2 = "456 Main St, Hamilton"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is False

    def test_different_streets_no_match(self):
        """Test that different street names don't match."""
        addr1 = "123 Main St, Hamilton"
        addr2 = "123 King St, Hamilton"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is False

    def test_different_cities_no_match(self):
        """Test that different cities don't match."""
        addr1 = "123 Main St, Hamilton"
        addr2 = "123 Main St, Toronto"

        is_match, confidence = addresses_match(addr1, addr2)

        # Should not match (different city)
        assert is_match is False or confidence < 0.7

    def test_fuzzy_vs_strict_mode(self):
        """Test fuzzy mode is more lenient than strict mode."""
        addr1 = "123 Main St, Hamilton"
        addr2 = "123 Main Street, Hamilton, ON L8H 3R2"  # More complete

        fuzzy_match, fuzzy_conf = addresses_match(addr1, addr2, fuzzy=True)
        strict_match, strict_conf = addresses_match(addr1, addr2, fuzzy=False)

        # Fuzzy should match or have higher confidence
        assert fuzzy_conf >= strict_conf

    def test_postal_code_helps_matching(self):
        """Test that postal code increases confidence."""
        addr1 = "123 Main St, L8H 3R2"
        addr2 = "123 Main Street, L8H 3R2"

        is_match, confidence = addresses_match(addr1, addr2)

        assert confidence >= 0.8


class TestStreetNumberParsing:
    """Test street number extraction."""

    def test_simple_number(self):
        """Test simple street number."""
        assert parse_street_number("123 Main St") == '123'

    def test_number_with_letter(self):
        """Test street number with letter suffix."""
        result = parse_street_number("456A Oak Ave")
        assert result in ['456A', '456']  # Either is acceptable

    def test_number_with_dash(self):
        """Test street number with dash."""
        result = parse_street_number("789-B King St")
        assert '789' in result

    def test_no_number(self):
        """Test address without street number."""
        assert parse_street_number("Main Street") is None


class TestRealWorldAddresses:
    """Test with real Hamilton addresses."""

    def test_hamilton_tool_and_die(self):
        """Test real business address - Hamilton Tool & Die."""
        addr1 = "55 Kenilworth Ave N, Hamilton, ON L8H 5R9"
        addr2 = "55 Kenilworth Avenue North, Hamilton, Ontario"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is True or confidence >= 0.75

    def test_downtown_hamilton(self):
        """Test downtown Hamilton address."""
        addr1 = "100 King St E, Hamilton, ON L8N 1A8"
        addr2 = "100 King Street East, Hamilton"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is True
        assert confidence >= 0.8

    def test_industrial_address(self):
        """Test industrial park address."""
        addr1 = "1250 Sandhill Dr, Unit 5, Ancaster, ON L9G 4V5"
        addr2 = "1250 Sandhill Drive, Suite 5, Ancaster"

        is_match, confidence = addresses_match(addr1, addr2, fuzzy=True)

        # Should have high confidence even if not exact match
        assert confidence >= 0.7

    def test_commercial_plaza(self):
        """Test commercial plaza address."""
        addr1 = "1059 King St W, Hamilton"
        addr2 = "1059 King Street West, Hamilton, ON"

        is_match, confidence = addresses_match(addr1, addr2)

        assert is_match is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_addresses(self):
        """Test matching empty addresses."""
        is_match, confidence = addresses_match("", "")

        assert is_match is False
        assert confidence == 0.0

    def test_one_empty_address(self):
        """Test matching with one empty address."""
        is_match, confidence = addresses_match("123 Main St", "")

        assert is_match is False
        assert confidence == 0.0

    def test_po_box(self):
        """Test PO Box address."""
        result = normalize_address("PO Box 123, Hamilton, ON")

        # Should handle gracefully (may not parse perfectly)
        assert result['original'] == "PO Box 123, Hamilton, ON"
        assert result['city'] == 'Hamilton'

    def test_rural_route(self):
        """Test rural route address."""
        result = normalize_address("RR 1, Waterdown, ON")

        # Should handle gracefully
        assert result['city'] == 'Waterdown'

    def test_very_long_street_name(self):
        """Test handling of very long street name."""
        result = normalize_address("123 The Really Very Long Street Name Boulevard, Hamilton")

        assert result['street_number'] == '123'
        assert 'Long' in result['street_name'] or 'Long' in result['normalized']

    def test_special_characters(self):
        """Test handling of special characters."""
        result = normalize_address("123 O'Connor St, Hamilton")

        assert result['street_number'] == '123'
        # Should handle apostrophe gracefully

    def test_french_accent(self):
        """Test handling of accented characters (for Quebec addresses)."""
        result = normalize_address("123 Rue Saint-André, Montréal")

        # Should handle gracefully
        assert result['street_number'] == '123'


class TestCanadaPostCompliance:
    """Test Canada Post standard compliance."""

    def test_all_abbreviations_defined(self):
        """Test that all common abbreviations are in dictionary."""
        required_abbrevs = ['St', 'Ave', 'Rd', 'Dr', 'Blvd', 'Ln', 'Crt', 'Cres']

        for abbrev in required_abbrevs:
            assert abbrev in CANADA_POST_ABBREV, f"{abbrev} should be in abbreviation dictionary"

    def test_directional_abbreviations(self):
        """Test directional abbreviations."""
        required_directions = ['E', 'W', 'N', 'S', 'NE', 'NW', 'SE', 'SW']

        for direction in required_directions:
            assert direction in CANADA_POST_ABBREV

    def test_normalized_output_format(self):
        """Test that normalized output follows standard format."""
        result = normalize_address("123 Main St E, Unit 7, Hamilton, ON L8H 3R2")
        normalized = result['normalized']

        # Should contain key components in order
        assert '123' in normalized  # Street number
        assert 'Main' in normalized  # Street name
        assert 'Hamilton' in normalized  # City


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
