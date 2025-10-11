"""
Wayback Machine service for website age verification.
PRIORITY: P0 - Critical for sign shop filtering (3+ year requirement).

Uses Internet Archive's Wayback Machine CDX API to determine when a website was first archived.
"""

import re
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse
import structlog
import requests

logger = structlog.get_logger(__name__)


class WaybackService:
    """
    Service for checking website age using Wayback Machine.

    Uses the CDX API to find the earliest snapshot of a domain.
    """

    CDX_API_URL = "http://web.archive.org/cdx/search/cdx"

    def __init__(self, timeout: int = 10, cache_ttl_days: int = 30):
        """
        Initialize Wayback service.

        Args:
            timeout: API request timeout in seconds
            cache_ttl_days: How long to cache results (default 30 days)
        """
        self.timeout = timeout
        self.cache_ttl_days = cache_ttl_days
        self.logger = logger

    def get_website_age(self, url: str) -> Dict:
        """
        Get website age by checking Wayback Machine archives.

        Args:
            url: Website URL to check

        Returns:
            Dictionary with:
            {
                'url': str,
                'first_seen': datetime or None,
                'age_years': float,
                'snapshot_count': int,
                'error': str or None
            }

        Examples:
            >>> service = WaybackService()
            >>> result = service.get_website_age("example.com")
            >>> result['age_years']
            15.3
        """
        try:
            # Normalize URL to domain only
            domain = self._extract_domain(url)

            if not domain:
                return {
                    'url': url,
                    'first_seen': None,
                    'age_years': 0.0,
                    'snapshot_count': 0,
                    'error': 'Invalid URL - could not extract domain'
                }

            self.logger.info("wayback_lookup_started", domain=domain)

            # Query CDX API for earliest snapshot
            params = {
                'url': domain,
                'limit': 1,  # Only need the first (earliest) snapshot
                'output': 'json',
                'fl': 'timestamp',  # Only return timestamp field
                'filter': '!statuscode:404'  # Exclude 404 snapshots
            }

            response = requests.get(
                self.CDX_API_URL,
                params=params,
                timeout=self.timeout
            )

            if response.status_code != 200:
                self.logger.warning("wayback_api_error",
                                   domain=domain,
                                   status_code=response.status_code)
                return {
                    'url': url,
                    'first_seen': None,
                    'age_years': 0.0,
                    'snapshot_count': 0,
                    'error': f'Wayback API returned status {response.status_code}'
                }

            data = response.json()

            # CDX API returns [['timestamp'], [...values...]] format
            # First row is headers, second row is data
            if len(data) < 2:
                self.logger.info("wayback_no_snapshots", domain=domain)
                return {
                    'url': url,
                    'first_seen': None,
                    'age_years': 0.0,
                    'snapshot_count': 0,
                    'error': None  # Not an error - just no snapshots
                }

            # Parse timestamp (format: YYYYMMDDhhmmss)
            timestamp_str = data[1][0]
            first_seen = self._parse_wayback_timestamp(timestamp_str)

            if not first_seen:
                return {
                    'url': url,
                    'first_seen': None,
                    'age_years': 0.0,
                    'snapshot_count': 0,
                    'error': f'Could not parse timestamp: {timestamp_str}'
                }

            # Calculate age in years
            age_years = (datetime.now() - first_seen).days / 365.25

            # Get total snapshot count (optional, for metadata)
            snapshot_count = self._get_snapshot_count(domain)

            self.logger.info("wayback_lookup_complete",
                           domain=domain,
                           first_seen=first_seen.isoformat(),
                           age_years=round(age_years, 2),
                           snapshot_count=snapshot_count)

            return {
                'url': url,
                'first_seen': first_seen,
                'age_years': age_years,
                'snapshot_count': snapshot_count,
                'error': None
            }

        except requests.Timeout:
            self.logger.error("wayback_timeout", url=url)
            return {
                'url': url,
                'first_seen': None,
                'age_years': 0.0,
                'snapshot_count': 0,
                'error': f'Wayback API timeout after {self.timeout}s'
            }

        except Exception as e:
            self.logger.error("wayback_error", url=url, error=str(e))
            return {
                'url': url,
                'first_seen': None,
                'age_years': 0.0,
                'snapshot_count': 0,
                'error': str(e)
            }

    def is_parked_domain(self, url: str) -> bool:
        """
        Detect if domain is a parked/for-sale page.

        Checks for common parking page indicators:
        - "This domain is for sale"
        - GoDaddy parking page
        - Namecheap parking page
        - Domain marketplace redirects

        Args:
            url: Website URL to check

        Returns:
            True if domain appears to be parked, False otherwise

        Examples:
            >>> service = WaybackService()
            >>> service.is_parked_domain("parked-example.com")
            True
        """
        try:
            # Normalize URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # Fetch page content
            response = requests.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; BusinessValidator/1.0)'}
            )

            if response.status_code != 200:
                return False

            content = response.text.lower()
            final_url = response.url.lower()

            # Check for parking page indicators
            parking_indicators = [
                'this domain is for sale',
                'this domain may be for sale',
                'buy this domain',
                'domain for sale',
                'parked by godaddy',
                'godaddy.com/forsale',
                'namecheap parking',
                'domain parking',
                'sedo domain parking',
                'hugedomains.com',
                'dan.com/buy-domain',
                'afternic.com',
                'undeveloped',
                'coming soon'
            ]

            for indicator in parking_indicators:
                if indicator in content:
                    self.logger.info("parked_domain_detected",
                                   url=url,
                                   indicator=indicator)
                    return True

            # Check if redirected to domain marketplace
            marketplace_domains = [
                'godaddy.com',
                'namecheap.com',
                'sedo.com',
                'afternic.com',
                'dan.com',
                'hugedomains.com'
            ]

            for marketplace in marketplace_domains:
                if marketplace in final_url:
                    self.logger.info("parked_domain_redirect",
                                   url=url,
                                   marketplace=marketplace)
                    return True

            return False

        except Exception as e:
            self.logger.error("parked_domain_check_failed",
                            url=url,
                            error=str(e))
            # If we can't check, assume not parked (don't block on errors)
            return False

    def _extract_domain(self, url: str) -> Optional[str]:
        """
        Extract clean domain from URL.

        Examples:
            >>> service = WaybackService()
            >>> service._extract_domain("https://www.example.com/page")
            'example.com'
        """
        if not url:
            return None

        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path

            # Remove www. prefix
            domain = re.sub(r'^www\.', '', domain)

            # Remove port if present
            domain = domain.split(':')[0]

            return domain.lower().strip()

        except Exception as e:
            self.logger.error("domain_extraction_failed",
                            url=url,
                            error=str(e))
            return None

    def _parse_wayback_timestamp(self, timestamp: str) -> Optional[datetime]:
        """
        Parse Wayback Machine timestamp format (YYYYMMDDhhmmss).

        Args:
            timestamp: Wayback timestamp string

        Returns:
            datetime object or None if parsing fails

        Examples:
            >>> service = WaybackService()
            >>> service._parse_wayback_timestamp("20100315120000")
            datetime(2010, 3, 15, 12, 0, 0)
        """
        try:
            # Wayback format: YYYYMMDDhhmmss (14 digits)
            if not timestamp or len(timestamp) < 8:
                return None

            year = int(timestamp[0:4])
            month = int(timestamp[4:6])
            day = int(timestamp[6:8])

            # Time components are optional
            hour = int(timestamp[8:10]) if len(timestamp) >= 10 else 0
            minute = int(timestamp[10:12]) if len(timestamp) >= 12 else 0
            second = int(timestamp[12:14]) if len(timestamp) >= 14 else 0

            return datetime(year, month, day, hour, minute, second)

        except (ValueError, IndexError) as e:
            self.logger.error("timestamp_parse_error",
                            timestamp=timestamp,
                            error=str(e))
            return None

    def _get_snapshot_count(self, domain: str) -> int:
        """
        Get total number of snapshots for a domain.

        This is metadata only - not used for age calculation.

        Args:
            domain: Domain to check

        Returns:
            Number of snapshots (0 if error)
        """
        try:
            params = {
                'url': domain,
                'output': 'json',
                'fl': 'timestamp',
                'showNumPages': 'true'
            }

            response = requests.get(
                self.CDX_API_URL,
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                # First row is headers, rest are snapshots
                return len(data) - 1 if len(data) > 1 else 0

            return 0

        except Exception:
            return 0


def check_website_age_gate(
    url: str,
    min_age_years: float = 3.0,
    check_parked: bool = True
) -> Dict:
    """
    Convenience function for website age gate checking.

    Args:
        url: Website URL to check
        min_age_years: Minimum required age in years (default 3.0)
        check_parked: Whether to check for parked domains (default True)

    Returns:
        Dictionary with:
        {
            'passes_gate': bool,
            'age_years': float,
            'is_parked': bool,
            'rejection_reason': str or None
        }

    Examples:
        >>> result = check_website_age_gate("example.com", min_age_years=3.0)
        >>> result['passes_gate']
        True
    """
    service = WaybackService()

    # Get website age
    age_result = service.get_website_age(url)

    if age_result['error']:
        return {
            'passes_gate': False,
            'age_years': 0.0,
            'is_parked': False,
            'rejection_reason': f"Age check failed: {age_result['error']}"
        }

    age_years = age_result['age_years']

    # Check if parked
    is_parked = False
    if check_parked:
        is_parked = service.is_parked_domain(url)

    # Determine if passes gate
    passes_gate = age_years >= min_age_years and not is_parked

    # Build rejection reason
    rejection_reason = None
    if not passes_gate:
        if is_parked:
            rejection_reason = f"Domain is parked/for sale"
        elif age_years < min_age_years:
            rejection_reason = f"Domain too new ({age_years:.1f} years, need {min_age_years}+ years)"
        else:
            rejection_reason = "Unknown website age gate failure"

    return {
        'passes_gate': passes_gate,
        'age_years': age_years,
        'is_parked': is_parked,
        'first_seen': age_result['first_seen'],
        'snapshot_count': age_result['snapshot_count'],
        'rejection_reason': rejection_reason
    }
