"""
Website validation service for verifying business websites.
Ensures all websites are accessible and match business information.
"""

import asyncio
import re
import ssl
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import certifi
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

from src.core.exceptions import ValidationError
from src.utils.logging_config import get_logger
from src.services.wayback_service import check_website_age_gate

logger = get_logger(__name__)


class WebsiteValidationResult:
    """Result of website validation."""

    def __init__(
        self,
        url: str,
        is_accessible: bool = False,
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        has_ssl: bool = False,
        business_name_match: float = 0.0,
        contact_info_match: bool = False,
        has_business_content: bool = False,
        validation_timestamp: Optional[datetime] = None,
        error_message: Optional[str] = None,
        # Website age fields (Task 3)
        website_age_years: float = 0.0,
        website_first_seen: Optional[datetime] = None,
        is_parked: bool = False,
        passes_age_gate: bool = False,
        age_gate_rejection_reason: Optional[str] = None
    ):
        self.url = url
        self.is_accessible = is_accessible
        self.status_code = status_code
        self.response_time = response_time
        self.has_ssl = has_ssl
        self.business_name_match = business_name_match
        self.contact_info_match = contact_info_match
        self.has_business_content = has_business_content
        self.validation_timestamp = validation_timestamp or datetime.utcnow()
        self.error_message = error_message
        # Website age
        self.website_age_years = website_age_years
        self.website_first_seen = website_first_seen
        self.is_parked = is_parked
        self.passes_age_gate = passes_age_gate
        self.age_gate_rejection_reason = age_gate_rejection_reason

    @property
    def is_valid(self) -> bool:
        """Check if website meets all validation criteria."""
        return (
            self.is_accessible and
            self.status_code == 200 and
            self.business_name_match >= 0.6 and
            self.has_business_content and
            self.response_time and self.response_time < 10.0 and
            self.passes_age_gate  # Task 3: Require age gate pass
        )
        
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'url': self.url,
            'is_accessible': self.is_accessible,
            'status_code': self.status_code,
            'response_time': self.response_time,
            'has_ssl': self.has_ssl,
            'business_name_match': self.business_name_match,
            'contact_info_match': self.contact_info_match,
            'has_business_content': self.has_business_content,
            'validation_timestamp': self.validation_timestamp.isoformat(),
            'error_message': self.error_message,
            'is_valid': self.is_valid,
            # Website age fields
            'website_age_years': self.website_age_years,
            'website_first_seen': self.website_first_seen.isoformat() if self.website_first_seen else None,
            'is_parked': self.is_parked,
            'passes_age_gate': self.passes_age_gate,
            'age_gate_rejection_reason': self.age_gate_rejection_reason
        }


class WebsiteValidationService:
    """Service for validating business websites."""

    def __init__(
        self,
        timeout: float = 10.0,
        max_retries: int = 3,
        min_website_age_years: float = 3.0,
        check_parked: bool = True
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_website_age_years = min_website_age_years
        self.check_parked = check_parked
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None
            
    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if not self._session:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'Business Validation Bot/1.0 (+https://example.com/bot)'
                }
            )
    
    async def validate_website(
        self, 
        url: str, 
        business_name: str,
        business_phone: Optional[str] = None,
        business_address: Optional[str] = None
    ) -> WebsiteValidationResult:
        """
        Validate a business website comprehensively.
        
        Args:
            url: Website URL to validate
            business_name: Expected business name to match
            business_phone: Expected phone number (optional)
            business_address: Expected address (optional)
            
        Returns:
            WebsiteValidationResult with validation details
        """
        await self._ensure_session()
        
        try:
            # Normalize URL
            normalized_url = self._normalize_url(url)
            
            # Perform HTTP request with timing
            start_time = time.time()
            response_data = await self._make_request(normalized_url)
            response_time = time.time() - start_time
            
            if not response_data or len(response_data) != 3:
                return WebsiteValidationResult(
                    url=normalized_url,
                    error_message="Failed to fetch website or invalid response"
                )
            
            status_code, content, final_url = response_data
            
            # Check SSL
            has_ssl = final_url.startswith('https://')
            
            # Parse content for validation
            soup = BeautifulSoup(content, 'html.parser')
            
            # Business name matching
            business_name_match = self._calculate_business_name_match(
                soup, business_name
            )
            
            # Contact info matching
            contact_info_match = self._validate_contact_info(
                soup, business_phone, business_address
            )
            
            # Business content validation
            has_business_content = self._validate_business_content(soup)

            # Website age gate (Task 3)
            age_gate_result = check_website_age_gate(
                normalized_url,
                min_age_years=self.min_website_age_years,
                check_parked=self.check_parked
            )

            return WebsiteValidationResult(
                url=normalized_url,
                is_accessible=True,
                status_code=status_code,
                response_time=response_time,
                has_ssl=has_ssl,
                business_name_match=business_name_match,
                contact_info_match=contact_info_match,
                has_business_content=has_business_content,
                # Website age fields
                website_age_years=age_gate_result['age_years'],
                website_first_seen=age_gate_result.get('first_seen'),
                is_parked=age_gate_result['is_parked'],
                passes_age_gate=age_gate_result['passes_gate'],
                age_gate_rejection_reason=age_gate_result.get('rejection_reason')
            )
            
        except Exception as e:
            logger.error(f"Website validation failed for {url}: {str(e)}")
            return WebsiteValidationResult(
                url=url,
                error_message=str(e)
            )
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL format."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.lower().strip()
    
    async def _make_request(self, url: str) -> Optional[Tuple[int, str, str]]:
        """Make HTTP request with retries."""
        if not self._session:
            raise ValidationError("HTTP session not initialized")
            
        for attempt in range(self.max_retries):
            try:
                async with self._session.get(url, allow_redirects=True) as response:
                    content = await response.text()
                    return response.status, content, str(response.url)
                    
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    raise ValidationError(f"Timeout after {self.max_retries} attempts")
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                raise ValidationError("Request was cancelled")
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise ValidationError(f"Request failed: {str(e)}")
                await asyncio.sleep(1)
        
        raise ValidationError("All retry attempts failed")
    
    def _calculate_business_name_match(self, soup: BeautifulSoup, business_name: str) -> float:
        """Calculate how well the business name matches website content."""
        if not business_name:
            return 0.0
            
        # Extract text content
        text_content = soup.get_text().lower()
        title_content = soup.title.string.lower() if soup.title else ""
        
        # Clean business name for matching
        clean_business_name = re.sub(r'[^\w\s]', '', business_name.lower())
        business_words = clean_business_name.split()
        
        # Check title match (higher weight)
        title_match = SequenceMatcher(None, clean_business_name, title_content).ratio()
        
        # Check content match
        content_match = SequenceMatcher(None, clean_business_name, text_content).ratio()
        
        # Check individual word matches
        word_matches = 0
        for word in business_words:
            if len(word) > 2 and word in text_content:
                word_matches += 1
        
        word_match_ratio = word_matches / len(business_words) if business_words else 0
        
        # Weighted average
        final_score = (title_match * 0.5 + content_match * 0.3 + word_match_ratio * 0.2)
        
        return min(final_score, 1.0)
    
    def _validate_contact_info(
        self, 
        soup: BeautifulSoup, 
        phone: Optional[str], 
        address: Optional[str]
    ) -> bool:
        """Validate contact information consistency."""
        text_content = soup.get_text().lower()
        
        # Check phone number if provided
        if phone:
            # Clean phone for matching
            clean_phone = re.sub(r'[^\d]', '', phone)
            if len(clean_phone) >= 10:
                phone_pattern = clean_phone[-10:]  # Last 10 digits
                if phone_pattern not in re.sub(r'[^\d]', '', text_content):
                    return False
        
        # Check address if provided
        if address:
            address_words = address.lower().split()
            matched_words = sum(1 for word in address_words if word in text_content)
            if len(address_words) > 0 and matched_words / len(address_words) < 0.3:
                return False
        
        return True
    
    def _validate_business_content(self, soup: BeautifulSoup) -> bool:
        """Validate that website has legitimate business content."""
        # Check for essential business indicators
        business_indicators = [
            'about', 'services', 'products', 'contact', 'hours',
            'location', 'phone', 'email', 'business', 'company'
        ]
        
        text_content = soup.get_text().lower()
        
        # Count indicators
        indicator_count = sum(1 for indicator in business_indicators if indicator in text_content)
        
        # Check for multiple pages/sections
        nav_links = soup.find_all(['nav', 'menu', 'a'])
        has_navigation = len(nav_links) > 5
        
        # Check for professional content
        has_enough_content = len(text_content.split()) > 100
        
        # Must have at least 3 business indicators and professional content
        return indicator_count >= 3 and has_enough_content and has_navigation

    async def validate_multiple_websites(
        self, 
        website_data: List[Dict]
    ) -> List[WebsiteValidationResult]:
        """
        Validate multiple websites concurrently.
        
        Args:
            website_data: List of dicts with 'url', 'business_name', etc.
            
        Returns:
            List of WebsiteValidationResult objects
        """
        await self._ensure_session()
        
        tasks = []
        for data in website_data:
            task = self.validate_website(
                url=data['url'],
                business_name=data['business_name'],
                business_phone=data.get('phone'),
                business_address=data.get('address')
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        validated_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                validated_results.append(WebsiteValidationResult(
                    url=website_data[i]['url'],
                    error_message=str(result)
                ))
            else:
                validated_results.append(result)
        
        return validated_results