"""
Tests for website age gate using Wayback Machine.
Ensures sign shops < 3 years are blocked and parked domains are detected.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.services.wayback_service import (
    WaybackService,
    check_website_age_gate
)


class TestWaybackTimestampParsing:
    """Test Wayback timestamp parsing."""

    def test_parse_full_timestamp(self):
        """Test parsing complete timestamp."""
        service = WaybackService()
        result = service._parse_wayback_timestamp("20100315120000")

        assert result == datetime(2010, 3, 15, 12, 0, 0)

    def test_parse_date_only_timestamp(self):
        """Test parsing timestamp with date only."""
        service = WaybackService()
        result = service._parse_wayback_timestamp("20100315")

        assert result == datetime(2010, 3, 15, 0, 0, 0)

    def test_parse_invalid_timestamp(self):
        """Test handling of invalid timestamp."""
        service = WaybackService()
        result = service._parse_wayback_timestamp("invalid")

        assert result is None

    def test_parse_empty_timestamp(self):
        """Test handling of empty timestamp."""
        service = WaybackService()
        result = service._parse_wayback_timestamp("")

        assert result is None


class TestDomainExtraction:
    """Test domain extraction from URLs."""

    def test_extract_from_https_url(self):
        """Test extracting domain from HTTPS URL."""
        service = WaybackService()
        result = service._extract_domain("https://www.example.com/page")

        assert result == "example.com"

    def test_extract_from_http_url(self):
        """Test extracting domain from HTTP URL."""
        service = WaybackService()
        result = service._extract_domain("http://example.com")

        assert result == "example.com"

    def test_extract_from_bare_domain(self):
        """Test extracting from bare domain."""
        service = WaybackService()
        result = service._extract_domain("example.com")

        assert result == "example.com"

    def test_remove_www_prefix(self):
        """Test that www prefix is removed."""
        service = WaybackService()
        result = service._extract_domain("www.example.com")

        assert result == "example.com"

    def test_remove_port(self):
        """Test that port is removed."""
        service = WaybackService()
        result = service._extract_domain("example.com:8080")

        assert result == "example.com"

    def test_invalid_url(self):
        """Test handling of invalid URL."""
        service = WaybackService()
        result = service._extract_domain("")

        assert result is None


class TestWaybackAgeChecking:
    """Test Wayback Machine age checking."""

    @patch('src.services.wayback_service.requests.get')
    def test_old_domain_passes(self, mock_get):
        """Test that old domain (> 3 years) passes gate."""
        # Mock Wayback API response with old timestamp
        old_date = datetime.now() - timedelta(days=5*365)  # 5 years ago
        timestamp = old_date.strftime("%Y%m%d%H%M%S")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            ['timestamp'],  # Header row
            [timestamp]     # Data row with old timestamp
        ]
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.get_website_age("example.com")

        assert result['age_years'] >= 3.0
        assert result['error'] is None
        assert result['first_seen'] is not None

    @patch('src.services.wayback_service.requests.get')
    def test_new_domain_fails(self, mock_get):
        """Test that new domain (< 3 years) is detected."""
        # Mock Wayback API response with recent timestamp
        recent_date = datetime.now() - timedelta(days=365)  # 1 year ago
        timestamp = recent_date.strftime("%Y%m%d%H%M%S")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            ['timestamp'],
            [timestamp]
        ]
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.get_website_age("newdomain.com")

        assert result['age_years'] < 3.0
        assert result['age_years'] > 0.0
        assert result['error'] is None

    @patch('src.services.wayback_service.requests.get')
    def test_no_snapshots_returns_zero_age(self, mock_get):
        """Test that domains with no snapshots return age 0."""
        # Mock Wayback API response with only header
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            ['timestamp']  # Only header, no data
        ]
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.get_website_age("nosnapshots.com")

        assert result['age_years'] == 0.0
        assert result['first_seen'] is None
        assert result['snapshot_count'] == 0
        assert result['error'] is None  # Not an error, just no data

    @patch('src.services.wayback_service.requests.get')
    def test_api_timeout_handled(self, mock_get):
        """Test that API timeout is handled gracefully."""
        import requests
        mock_get.side_effect = requests.Timeout("Connection timeout")

        service = WaybackService()
        result = service.get_website_age("example.com")

        assert result['age_years'] == 0.0
        assert result['error'] is not None
        assert 'timeout' in result['error'].lower()

    @patch('src.services.wayback_service.requests.get')
    def test_api_error_handled(self, mock_get):
        """Test that API errors are handled gracefully."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.get_website_age("example.com")

        assert result['age_years'] == 0.0
        assert result['error'] is not None


class TestParkedDomainDetection:
    """Test parked domain detection."""

    @patch('src.services.wayback_service.requests.get')
    def test_godaddy_parking_detected(self, mock_get):
        """Test GoDaddy parking page detection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>This domain is parked by GoDaddy</body></html>"
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.is_parked_domain("example.com")

        assert result is True

    @patch('src.services.wayback_service.requests.get')
    def test_for_sale_detected(self, mock_get):
        """Test 'for sale' page detection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>This domain is for sale! Buy it now.</body></html>"
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.is_parked_domain("example.com")

        assert result is True

    @patch('src.services.wayback_service.requests.get')
    def test_marketplace_redirect_detected(self, mock_get):
        """Test redirect to domain marketplace."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Domain listing</body></html>"
        mock_response.url = "https://www.godaddy.com/forsale/example.com"
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.is_parked_domain("example.com")

        assert result is True

    @patch('src.services.wayback_service.requests.get')
    def test_legitimate_site_not_parked(self, mock_get):
        """Test that legitimate business site is not flagged as parked."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <body>
                <h1>ABC Manufacturing</h1>
                <p>Welcome to our website. We provide quality products.</p>
                <a href="/about">About Us</a>
                <a href="/contact">Contact</a>
            </body>
        </html>
        """
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.is_parked_domain("example.com")

        assert result is False

    @patch('src.services.wayback_service.requests.get')
    def test_http_error_not_flagged_as_parked(self, mock_get):
        """Test that HTTP errors don't flag domain as parked."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.is_parked_domain("example.com")

        assert result is False


class TestWebsiteAgeGate:
    """Test complete website age gate logic."""

    @patch('src.services.wayback_service.requests.get')
    def test_old_domain_passes_gate(self, mock_get):
        """Test that old, legitimate domain passes gate."""
        # Mock age check (5 years old)
        old_date = datetime.now() - timedelta(days=5*365)
        timestamp = old_date.strftime("%Y%m%d%H%M%S")

        def mock_get_side_effect(url, **kwargs):
            mock_resp = Mock()
            if 'web.archive.org' in url:
                # Wayback API response
                mock_resp.status_code = 200
                mock_resp.json.return_value = [['timestamp'], [timestamp]]
            else:
                # Parked check response
                mock_resp.status_code = 200
                mock_resp.text = "<html><body>Legitimate business content</body></html>"
                mock_resp.url = url
            return mock_resp

        mock_get.side_effect = mock_get_side_effect

        result = check_website_age_gate("example.com", min_age_years=3.0)

        assert result['passes_gate'] is True
        assert result['age_years'] >= 3.0
        assert result['is_parked'] is False
        assert result['rejection_reason'] is None

    @patch('src.services.wayback_service.requests.get')
    def test_new_domain_fails_gate(self, mock_get):
        """Test that new domain (< 3 years) fails gate."""
        # Mock age check (1 year old)
        recent_date = datetime.now() - timedelta(days=365)
        timestamp = recent_date.strftime("%Y%m%d%H%M%S")

        def mock_get_side_effect(url, **kwargs):
            mock_resp = Mock()
            if 'web.archive.org' in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = [['timestamp'], [timestamp]]
            else:
                mock_resp.status_code = 200
                mock_resp.text = "<html>Content</html>"
                mock_resp.url = url
            return mock_resp

        mock_get.side_effect = mock_get_side_effect

        result = check_website_age_gate("newdomain.com", min_age_years=3.0)

        assert result['passes_gate'] is False
        assert result['age_years'] < 3.0
        assert "too new" in result['rejection_reason'].lower()

    @patch('src.services.wayback_service.requests.get')
    def test_parked_domain_fails_gate(self, mock_get):
        """Test that parked domain fails gate even if old."""
        # Mock age check (5 years old)
        old_date = datetime.now() - timedelta(days=5*365)
        timestamp = old_date.strftime("%Y%m%d%H%M%S")

        def mock_get_side_effect(url, **kwargs):
            mock_resp = Mock()
            if 'web.archive.org' in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = [['timestamp'], [timestamp]]
            else:
                # Parked domain
                mock_resp.status_code = 200
                mock_resp.text = "<html>This domain is for sale</html>"
                mock_resp.url = url
            return mock_resp

        mock_get.side_effect = mock_get_side_effect

        result = check_website_age_gate("parked.com", min_age_years=3.0)

        assert result['passes_gate'] is False
        assert result['is_parked'] is True
        assert "parked" in result['rejection_reason'].lower()

    @patch('src.services.wayback_service.requests.get')
    def test_age_check_error_fails_gate(self, mock_get):
        """Test that age check errors fail the gate safely."""
        import requests
        mock_get.side_effect = requests.Timeout("Connection timeout")

        result = check_website_age_gate("example.com", min_age_years=3.0)

        assert result['passes_gate'] is False
        assert result['age_years'] == 0.0
        assert "failed" in result['rejection_reason'].lower()


class TestRealWorldScenarios:
    """Test with realistic business scenarios."""

    @patch('src.services.wayback_service.requests.get')
    def test_sign_shop_filtering(self, mock_get):
        """Test that sign shops < 3 years are blocked."""
        # Mock 2-year-old sign shop
        recent_date = datetime.now() - timedelta(days=2*365)
        timestamp = recent_date.strftime("%Y%m%d%H%M%S")

        def mock_get_side_effect(url, **kwargs):
            mock_resp = Mock()
            if 'web.archive.org' in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = [['timestamp'], [timestamp]]
            else:
                mock_resp.status_code = 200
                mock_resp.text = "<html><h1>ABC Signs</h1><p>Custom signage</p></html>"
                mock_resp.url = url
            return mock_resp

        mock_get.side_effect = mock_get_side_effect

        result = check_website_age_gate("abcsigns.com", min_age_years=3.0)

        assert result['passes_gate'] is False
        assert result['age_years'] < 3.0
        assert "too new" in result['rejection_reason'].lower()

    @patch('src.services.wayback_service.requests.get')
    def test_established_manufacturer_passes(self, mock_get):
        """Test that established manufacturer passes."""
        # Mock 10-year-old manufacturer
        old_date = datetime.now() - timedelta(days=10*365)
        timestamp = old_date.strftime("%Y%m%d%H%M%S")

        def mock_get_side_effect(url, **kwargs):
            mock_resp = Mock()
            if 'web.archive.org' in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = [['timestamp'], [timestamp]]
            else:
                mock_resp.status_code = 200
                mock_resp.text = """
                <html>
                    <h1>Hamilton Manufacturing</h1>
                    <p>Established 1990. Quality parts manufacturing.</p>
                    <a href="/about">About</a>
                    <a href="/products">Products</a>
                </html>
                """
                mock_resp.url = url
            return mock_resp

        mock_get.side_effect = mock_get_side_effect

        result = check_website_age_gate("hamiltonmfg.com", min_age_years=3.0)

        assert result['passes_gate'] is True
        assert result['age_years'] >= 3.0
        assert result['is_parked'] is False


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch('src.services.wayback_service.requests.get')
    def test_domain_with_no_protocol(self, mock_get):
        """Test handling domain without http/https."""
        old_date = datetime.now() - timedelta(days=5*365)
        timestamp = old_date.strftime("%Y%m%d%H%M%S")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [['timestamp'], [timestamp]]
        mock_get.return_value = mock_response

        service = WaybackService()
        result = service.get_website_age("example.com")

        assert result['age_years'] >= 3.0

    @patch('src.services.wayback_service.requests.get')
    def test_subdomain_handling(self, mock_get):
        """Test handling of subdomains."""
        service = WaybackService()
        domain = service._extract_domain("https://shop.example.com")

        assert domain == "shop.example.com"

    def test_malformed_url(self):
        """Test handling of completely malformed URL."""
        service = WaybackService()
        result = service.get_website_age("not a url at all")

        # Should not crash, return error
        assert result['age_years'] == 0.0

    @patch('src.services.wayback_service.requests.get')
    def test_wayback_rate_limiting(self, mock_get):
        """Test that we don't hammer Wayback API."""
        import time

        old_date = datetime.now() - timedelta(days=5*365)
        timestamp = old_date.strftime("%Y%m%d%H%M%S")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [['timestamp'], [timestamp]]
        mock_get.return_value = mock_response

        service = WaybackService()

        # Multiple requests should work
        start = time.time()
        for i in range(3):
            service.get_website_age(f"example{i}.com")
        elapsed = time.time() - start

        # Should complete quickly (not rate limited in our implementation)
        assert elapsed < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
