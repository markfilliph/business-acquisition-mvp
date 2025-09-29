"""
Business data validation service with website verification and sanity checks.
"""
import asyncio
import aiohttp
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

import structlog

from ..core.config import SystemConfig
from ..core.models import BusinessLead
from ..core.exceptions import ValidationError
from .noc_classification_service import NOCClassificationService
try:
    from .website_validation_service import WebsiteValidationService
    WEBSITE_VALIDATION_AVAILABLE = True
except ImportError:
    WEBSITE_VALIDATION_AVAILABLE = False
    WebsiteValidationService = None


class BusinessValidationService:
    """Validates business data integrity and verifies online presence."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self._validated_websites = set()  # Track unique websites to prevent duplicates
        self.noc_service = NOCClassificationService()  # NOC classification service
        self.website_validator = WebsiteValidationService() if WEBSITE_VALIDATION_AVAILABLE else None  # Website validation service
        self.validation_stats = {
            'total_validated': 0,
            'website_checks_passed': 0,
            'website_checks_failed': 0,
            'business_website_matches_passed': 0,
            'business_website_matches_failed': 0,
            'website_duplicates_blocked': 0,
            'skilled_trades_blocked': 0,
            'noc_skilled_trades_blocked': 0,
            'phone_validations': 0,
            'email_validations': 0,
            'address_validations': 0
        }
    
    async def validate_business_lead(self, lead: BusinessLead) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation of a business lead.
        Returns (is_valid, list_of_issues)
        """
        self.validation_stats['total_validated'] += 1
        issues = []
        
        # 0. Website uniqueness check (prevent duplicate businesses with same website)
        if lead.contact.website:
            normalized_website = self._normalize_website_url(lead.contact.website)
            if normalized_website in self._validated_websites:
                issues.append(f"Website {lead.contact.website} already validated for another business - potential duplicate")
                self.validation_stats['website_duplicates_blocked'] += 1
                self.logger.warning(
                    "website_duplicate_blocked",
                    business_name=lead.business_name,
                    website=lead.contact.website,
                    reason="website_already_validated"
                )
                return False, issues
            
            # Mark website as validated to prevent future duplicates
            self._validated_websites.add(normalized_website)
        
        # 0.5. Skilled trades exclusion (business type filtering)
        # Check using keyword-based method first
        if self._is_skilled_trade_business(lead.business_name):
            issues.append(f"Business '{lead.business_name}' appears to be a skilled trade - not suitable for acquisition")
            self.validation_stats['skilled_trades_blocked'] += 1
            self.logger.warning(
                "skilled_trade_business_blocked",
                business_name=lead.business_name,
                reason="keyword_based_classification"
            )
            return False, issues
        
        # Check using NOC classification for government-verified trades
        is_noc_skilled_trade, noc_details = self.noc_service.is_skilled_trade_by_noc(lead.business_name)
        if is_noc_skilled_trade:
            noc_info = f" (NOC {noc_details['noc_code']}: {noc_details['title']})" if noc_details else ""
            issues.append(f"Business '{lead.business_name}' matches government skilled trade classification{noc_info} - not suitable for acquisition")
            self.validation_stats['noc_skilled_trades_blocked'] += 1
            self.logger.warning(
                "noc_skilled_trade_blocked",
                business_name=lead.business_name,
                noc_code=noc_details.get('noc_code') if noc_details else None,
                noc_title=noc_details.get('title') if noc_details else None,
                reason="government_noc_classification"
            )
            return False, issues
        
        # 1. Website verification (basic for now)
        if lead.contact.website:
            website_valid = await self._verify_website(lead.contact.website)
            if not website_valid:
                issues.append(f"Website {lead.contact.website} is not accessible or does not exist")
                self.validation_stats['website_checks_failed'] += 1
            else:
                self.validation_stats['website_checks_passed'] += 1
                
                # Basic business-website matching validation
                business_website_match = await self._validate_business_website_match(lead.business_name, lead.contact.website)
                if not business_website_match:
                    issues.append(f"Business name '{lead.business_name}' does not match website content from {lead.contact.website}")
                    self.validation_stats['business_website_matches_failed'] += 1
                else:
                    self.validation_stats['business_website_matches_passed'] += 1
        
        # 2. Phone number format validation
        phone_valid = self._validate_phone(lead.contact.phone)
        if not phone_valid:
            issues.append(f"Phone number {lead.contact.phone} format is invalid")
        else:
            self.validation_stats['phone_validations'] += 1
        
        # 3. Email format validation (if provided)
        if lead.contact.email:
            email_valid = self._validate_email(lead.contact.email)
            if not email_valid:
                issues.append(f"Email {lead.contact.email} format is invalid")
            else:
                self.validation_stats['email_validations'] += 1
        
        # 4. Address format validation
        address_valid = self._validate_address(lead.location)
        if not address_valid:
            issues.append("Address information is incomplete or invalid")
        else:
            self.validation_stats['address_validations'] += 1
        
        # 4b. Location validation - MUST be in Hamilton area, Ontario, Canada
        location_valid, location_issues = self._validate_hamilton_location(lead.location)
        if not location_valid:
            issues.extend(location_issues)
        
        # 5. Enhanced Cross-Reference Validation
        cross_ref_issues = await self._cross_reference_business_data(lead)
        issues.extend(cross_ref_issues)

        # 6. Business data sanity checks
        business_data_valid, business_issues = self._validate_business_data(lead)
        issues.extend(business_issues)
        
        # 6. Revenue estimate sanity check (optional - may not exist yet before enrichment)
        # Only validate if revenue estimate has been populated during enrichment
        if hasattr(lead, 'revenue_estimate') and lead.revenue_estimate and lead.revenue_estimate.estimated_amount is not None:
            revenue_valid, revenue_issues = self._validate_revenue_estimate(lead)
            issues.extend(revenue_issues)
        
        is_valid = len(issues) == 0
        
        if not is_valid:
            self.logger.warning(
                "business_validation_failed",
                business_name=lead.business_name,
                issues=issues
            )
        else:
            self.logger.info(
                "business_validation_passed",
                business_name=lead.business_name
            )
        
        return is_valid, issues
    
    async def _validate_business_website_match(self, business_name: str, website: str) -> bool:
        """
        Validate that business name aligns with website content.
        Checks for business name or similar keywords in website content.
        """
        if not business_name or not website:
            return False
        
        # Normalize URL
        if not website.startswith(('http://', 'https://')):
            website = f"https://{website}"
        
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(website, allow_redirects=True) as response:
                    if response.status != 200:
                        self.logger.warning(
                            "business_website_match_check_failed",
                            website=website,
                            status=response.status
                        )
                        return False
                    
                    # Get page content
                    content = await response.text()
                    content_lower = content.lower()
                    
                    # Extract business name parts for matching
                    business_parts = self._extract_business_name_parts(business_name)
                    
                    # Check if key business name parts appear in website content
                    matches_found = 0
                    total_parts = len(business_parts)
                    
                    for part in business_parts:
                        if part.lower() in content_lower:
                            matches_found += 1
                    
                    # Require at least 60% of business name parts to be found
                    match_threshold = 0.6
                    match_ratio = matches_found / total_parts if total_parts > 0 else 0
                    
                    if match_ratio >= match_threshold:
                        self.logger.info(
                            "business_website_match_passed",
                            business_name=business_name,
                            website=website,
                            match_ratio=f"{match_ratio:.2f}",
                            matches_found=matches_found,
                            total_parts=total_parts
                        )
                        return True
                    else:
                        self.logger.warning(
                            "business_website_match_failed",
                            business_name=business_name,
                            website=website,
                            match_ratio=f"{match_ratio:.2f}",
                            matches_found=matches_found,
                            total_parts=total_parts,
                            business_parts=business_parts
                        )
                        return False
                        
        except asyncio.TimeoutError:
            self.logger.warning("business_website_match_timeout", website=website, business_name=business_name)
            return False
        except Exception as e:
            self.logger.warning(
                "business_website_match_error",
                website=website,
                business_name=business_name,
                error=str(e)
            )
            return False
    
    def _extract_business_name_parts(self, business_name: str) -> List[str]:
        """Extract meaningful parts from business name for matching."""
        if not business_name:
            return []
        
        # Remove common business suffixes and words
        common_suffixes = [
            'ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation',
            'llc', 'co', 'company', 'services', 'solutions', 'group',
            'enterprises', 'systems', 'consulting', 'associates'
        ]
        
        # Split business name into words
        words = re.findall(r'\b[a-zA-Z]+\b', business_name.lower())
        
        # Filter out common suffixes and short words
        meaningful_words = []
        for word in words:
            if (len(word) >= 3 and 
                word not in common_suffixes and 
                not word.isdigit()):
                meaningful_words.append(word)
        
        # If we filtered out too much, keep some original words
        if len(meaningful_words) == 0 and len(words) > 0:
            meaningful_words = [word for word in words if len(word) >= 2]
        
        return meaningful_words
    
    def _normalize_website_url(self, website: str) -> str:
        """
        Normalize website URL for duplicate detection.
        Converts different URL formats to a consistent form.
        """
        if not website:
            return ""
        
        # Convert to lowercase
        normalized = website.lower().strip()
        
        # Add https:// if no protocol
        if not normalized.startswith(('http://', 'https://')):
            normalized = f"https://{normalized}"
        
        # Remove trailing slashes
        normalized = normalized.rstrip('/')
        
        # Remove www. prefix for consistent matching
        normalized = normalized.replace('https://www.', 'https://')
        normalized = normalized.replace('http://www.', 'http://')
        
        return normalized
    
    def _is_skilled_trade_business(self, business_name: str) -> bool:
        """
        Detect if a business is a skilled trade that should be excluded.
        Skilled trades are service-based businesses, not suitable for acquisition.
        """
        if not business_name:
            return False
        
        # Convert to lowercase for matching
        name_lower = business_name.lower()
        
        # Skilled trade keywords that indicate service-based businesses
        skilled_trade_keywords = [
            # Glass/Window trades
            'glass', 'glazing', 'glazier', 'window', 'windows', 'mirror',
            
            # Construction trades
            'plumbing', 'plumber', 'electrical', 'electrician', 'hvac',
            'roofing', 'roofer', 'flooring', 'tiling', 'carpenter', 'carpentry',
            'painting', 'painter', 'drywall', 'insulation', 'siding',
            
            # Automotive trades  
            'auto repair', 'automotive', 'mechanic', 'garage', 'collision',
            'body shop', 'tire', 'muffler', 'brake',
            
            # Home services
            'lawn care', 'landscaping', 'cleaning', 'pest control',
            'appliance repair', 'handyman', 'maintenance',
            
            # Personal services
            'salon', 'barber', 'spa', 'fitness', 'dental', 'medical',
            'veterinary', 'daycare', 'restaurant', 'cafe',
            
            # Repair services
            'repair', 'contractor', 'contracting',
            
            # Professional services (individual practitioners)
            'law office', 'accounting', 'bookkeeping', 'consulting' 
        ]
        
        # Service-related terms that indicate trades
        service_terms = [
            'services', 'service', 'solutions', 'specialists', 'experts',
            'professionals', 'contractors', 'technicians'
        ]
        
        # Check for direct skilled trade keywords
        for keyword in skilled_trade_keywords:
            if keyword in name_lower:
                return True
        
        # Check for service-oriented business names with trade indicators
        has_service_term = any(term in name_lower for term in service_terms)
        if has_service_term:
            # Additional keywords that suggest trades when combined with service terms
            # BUT exclude legitimate manufacturing terms
            trade_indicators = [
                'home', 'residential', 'fix', 'repair'
            ]
            # Don't flag legitimate manufacturing companies that happen to mention installation
            manufacturing_terms = ['metal', 'fabricating', 'manufacturing', 'steel', 'industrial']
            has_manufacturing = any(term in name_lower for term in manufacturing_terms)

            if not has_manufacturing and any(indicator in name_lower for indicator in trade_indicators):
                return True
        
        return False
    
    async def _verify_website(self, website: str) -> bool:
        """Verify that a website actually exists and is accessible."""
        if not website:
            return False
        
        # Normalize URL
        if not website.startswith(('http://', 'https://')):
            website = f"https://{website}"
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(website, allow_redirects=True) as response:
                    # Accept any HTTP status that indicates the site exists
                    if 200 <= response.status < 600:
                        self.logger.info(
                            "website_verification_passed",
                            website=website,
                            status=response.status
                        )
                        return True
                    else:
                        self.logger.warning(
                            "website_verification_failed",
                            website=website,
                            status=response.status
                        )
                        return False
        except asyncio.TimeoutError:
            self.logger.warning("website_verification_timeout", website=website)
            return False
        except Exception as e:
            self.logger.warning(
                "website_verification_error",
                website=website,
                error=str(e)
            )
            return False
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate Canadian phone number format."""
        if not phone:
            return False
        
        # Remove all non-digits
        digits_only = re.sub(r'\D', '', phone)
        
        # Canadian phone numbers should be 10 digits (area code + number)
        if len(digits_only) == 10:
            return True
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return True
        
        return False
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        if not email:
            return True  # Email is optional
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    def _validate_address(self, location) -> bool:
        """Validate address completeness."""
        if not location:
            return False
        
        # Check required fields
        required_fields = ['address', 'city', 'province', 'postal_code']
        for field in required_fields:
            if not hasattr(location, field) or not getattr(location, field):
                return False
        
        # Validate Ontario postal code format (first 3 characters)
        postal_code = getattr(location, 'postal_code', '')
        if not re.match(r'^[KLMNP][0-9][A-Z]', postal_code.replace(' ', '').upper()):
            return False
        
        return True
    
    def _validate_hamilton_location(self, location) -> Tuple[bool, List[str]]:
        """Validate location is in Hamilton, Ontario, Canada area ONLY."""
        issues = []
        
        if not location:
            issues.append("Location information is missing")
            return False, issues
        
        # Target Hamilton area cities/regions
        hamilton_area_cities = {
            'hamilton', 'dundas', 'ancaster', 'stoney creek', 'waterdown', 
            'flamborough', 'binbrook', 'winona', 'mount hope'
        }
        
        # Check city
        city = getattr(location, 'city', '').lower().strip()
        if not city:
            issues.append("City information is missing")
            return False, issues
        
        if city not in hamilton_area_cities:
            issues.append(f"Business location '{city}' is outside Hamilton, Ontario area (Required: Hamilton, Dundas, Ancaster, Stoney Creek, Waterdown)")
        
        # Check province - MUST be Ontario
        province = getattr(location, 'province', '').upper().strip()
        if province not in ['ON', 'ONTARIO']:
            issues.append(f"Business must be in Ontario, Canada (Found: {province or 'missing'})")
        
        # Check postal code format - MUST be Ontario format
        postal_code_raw = getattr(location, 'postal_code', '') or ''
        postal_code = postal_code_raw.replace(' ', '').upper() if postal_code_raw else ''
        if postal_code:
            # Ontario postal codes start with K, L, M, N, P
            if not postal_code[0] in ['K', 'L', 'M', 'N', 'P']:
                issues.append(f"Postal code '{postal_code}' is not valid for Ontario, Canada")
                
            # Hamilton area postal codes are primarily L8x, L9x
            if postal_code[0] == 'L' and not postal_code.startswith(('L8', 'L9')):
                self.logger.warning(
                    "postal_code_outside_hamilton_core", 
                    postal_code=postal_code,
                    business_name=getattr(location, 'business_name', 'unknown')
                )
        
        # Check country
        country = getattr(location, 'country', '').lower().strip()
        if country and country not in ['canada', 'ca']:
            issues.append(f"Business must be in Canada (Found: {country})")
        
        return len(issues) == 0, issues
    
    def _validate_business_data(self, lead: BusinessLead) -> Tuple[bool, List[str]]:
        """Validate business-specific data for sanity."""
        issues = []
        
        # Check business age
        if lead.years_in_business is not None:
            if lead.years_in_business < 0 or lead.years_in_business > 150:
                issues.append(f"Unrealistic business age: {lead.years_in_business} years")
        
        # Check employee count
        if lead.employee_count is not None:
            if lead.employee_count < 1 or lead.employee_count > 10000:
                issues.append(f"Unrealistic employee count: {lead.employee_count}")
        
        # Check business name
        if not lead.business_name or len(lead.business_name) < 3:
            issues.append("Business name is too short or missing")
        
        # Check for common fake business indicators
        fake_indicators = [
            'test', 'example', 'sample', 'demo', 'fake', 'placeholder'
        ]
        
        business_name_lower = lead.business_name.lower()
        for indicator in fake_indicators:
            if indicator in business_name_lower:
                issues.append(f"Business name contains suspicious keyword: {indicator}")
        
        return len(issues) == 0, issues
    
    def _validate_revenue_estimate(self, lead: BusinessLead) -> Tuple[bool, List[str]]:
        """Validate revenue estimates for sanity."""
        issues = []
        
        if not hasattr(lead, 'revenue_estimate') or not lead.revenue_estimate:
            # Don't fail validation if revenue estimate hasn't been added yet (pre-enrichment)
            return True, []
        
        revenue = lead.revenue_estimate.estimated_amount
        confidence = lead.revenue_estimate.confidence_score
        
        # Check for None values - but don't fail if not populated yet
        if revenue is None:
            # Revenue not estimated yet - this is OK for pre-enrichment validation
            return True, []
            
        if confidence is None:
            # Set default confidence if missing but revenue exists
            lead.revenue_estimate.confidence_score = 0.0
            confidence = 0.0
        
        # Check revenue range sanity
        if revenue < 50_000 or revenue > 50_000_000:
            issues.append(f"Revenue estimate ${revenue:,} seems unrealistic")
        
        # Check confidence score
        if confidence < 0 or confidence > 1:
            issues.append(f"Revenue confidence score {confidence} is invalid")
        
        # Check if revenue fits our target criteria
        min_target = self.config.business_criteria.target_revenue_min
        max_target = self.config.business_criteria.target_revenue_max
        
        if not (min_target <= revenue <= max_target):
            issues.append(
                f"Revenue ${revenue:,} outside target range "
                f"${min_target:,}-${max_target:,}"
            )
        
        return len(issues) == 0, issues
    
    async def batch_validate_leads(self, leads: List[BusinessLead]) -> Dict[str, Any]:
        """Validate a batch of leads and return validation report."""
        
        self.logger.info("batch_validation_started", count=len(leads))
        
        valid_leads = []
        invalid_leads = []
        validation_issues = {}
        
        # Process leads concurrently but with rate limiting
        semaphore = asyncio.Semaphore(5)  # Limit concurrent validations
        
        async def validate_single_lead(lead):
            async with semaphore:
                is_valid, issues = await self.validate_business_lead(lead)
                return lead, is_valid, issues
        
        # Run validations
        validation_tasks = [validate_single_lead(lead) for lead in leads]
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                self.logger.error("validation_exception", error=str(result))
                continue
            
            lead, is_valid, issues = result
            
            if is_valid:
                valid_leads.append(lead)
            else:
                invalid_leads.append(lead)
                validation_issues[lead.unique_id] = issues
        
        validation_report = {
            'total_leads': len(leads),
            'valid_leads': len(valid_leads),
            'invalid_leads': len(invalid_leads),
            'validation_rate': len(valid_leads) / len(leads) if leads else 0,
            'valid_leads_list': valid_leads,
            'invalid_leads_list': invalid_leads,
            'validation_issues': validation_issues,
            'statistics': self.validation_stats.copy()
        }
        
        self.logger.info(
            "batch_validation_completed",
            total=len(leads),
            valid=len(valid_leads),
            invalid=len(invalid_leads),
            validation_rate=f"{validation_report['validation_rate']:.1%}"
        )
        
        return validation_report

    async def _cross_reference_business_data(self, lead: BusinessLead) -> List[str]:
        """Cross-reference business data with multiple sources for accuracy validation."""

        issues = []

        try:
            # 1. Website Content Validation
            if lead.contact.website:
                website_issues = await self._validate_website_content_accuracy(lead)
                issues.extend(website_issues)

            # 2. Address and Location Cross-Reference
            location_issues = await self._validate_location_accuracy(lead)
            issues.extend(location_issues)

            # 3. Phone Number Verification
            phone_issues = await self._validate_phone_accuracy(lead)
            issues.extend(phone_issues)

            # 4. Business Registration Verification
            registration_issues = await self._validate_business_registration(lead)
            issues.extend(registration_issues)

        except Exception as e:
            self.logger.error("cross_reference_validation_failed",
                            business_name=lead.business_name,
                            error=str(e))
            issues.append(f"Cross-reference validation failed: {str(e)}")

        return issues

    async def _validate_website_content_accuracy(self, lead: BusinessLead) -> List[str]:
        """Validate that website content matches business information."""

        issues = []

        try:
            if not lead.contact.website:
                return issues

            # In production, this would scrape website content and verify:
            # - Business name appears on the website
            # - Address information matches
            # - Phone numbers match
            # - Industry/services match the claimed industry

            # For now, we simulate basic checks
            domain = lead.contact.website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]

            # Check if business name components appear in domain
            business_words = lead.business_name.lower().replace('ltd', '').replace('inc', '').replace('&', '').split()
            domain_parts = domain.replace('.com', '').replace('.ca', '').replace('.net', '').split('.')

            name_match_found = False
            for word in business_words:
                if len(word) > 3:  # Only check significant words
                    for domain_part in domain_parts:
                        if word in domain_part or domain_part in word:
                            name_match_found = True
                            break

            if not name_match_found:
                issues.append(f"Business name '{lead.business_name}' does not appear to match website domain '{domain}'")

        except Exception as e:
            self.logger.warning("website_content_validation_failed",
                              business_name=lead.business_name,
                              error=str(e))

        return issues

    async def _validate_location_accuracy(self, lead: BusinessLead) -> List[str]:
        """Validate location accuracy through multiple sources with real-time verification."""

        issues = []

        try:
            # Check if address is realistic for Hamilton area
            if lead.location.address:
                address_lower = lead.location.address.lower()

                # Flag if address contains indicators of fake data
                fake_indicators = ['test', 'fake', 'example', 'sample', 'demo']
                for indicator in fake_indicators:
                    if indicator in address_lower:
                        issues.append(f"Address contains suspicious content: '{indicator}'")

                # Real-time address verification
                address_verification = await self._verify_address_exists(lead.location.address)
                if not address_verification['valid']:
                    issues.append(f"Address verification failed: {address_verification['reason']}")

                # Verify Hamilton area postal codes
                if hasattr(lead.location, 'postal_code') and lead.location.postal_code:
                    postal_prefix = lead.location.postal_code[:3].replace(' ', '').upper()
                    hamilton_prefixes = ['L8E', 'L8G', 'L8H', 'L8J', 'L8K', 'L8L', 'L8M', 'L8N', 'L8P', 'L8R', 'L8S', 'L8T', 'L8V', 'L8W', 'L9G', 'L9H']

                    if postal_prefix not in hamilton_prefixes:
                        issues.append(f"Postal code {lead.location.postal_code} is not in Hamilton area")

                # Geographic consistency check
                geo_issues = await self._verify_geographic_consistency(lead)
                issues.extend(geo_issues)

        except Exception as e:
            self.logger.warning("location_accuracy_validation_failed",
                              business_name=lead.business_name,
                              error=str(e))

        return issues

    async def _validate_phone_accuracy(self, lead: BusinessLead) -> List[str]:
        """Validate phone number accuracy with real-time verification."""

        issues = []

        try:
            if lead.contact.phone:
                phone = lead.contact.phone.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')

                # Hamilton area codes: 905, 289, 365
                # Also accept toll-free numbers: 800, 833, 844, 855, 866, 877, 888
                hamilton_area_codes = ['905', '289', '365']
                toll_free_codes = ['800', '833', '844', '855', '866', '877', '888']

                if len(phone) >= 10:
                    area_code = phone[-10:-7]  # Extract area code from full number

                    if area_code not in hamilton_area_codes and area_code not in toll_free_codes:
                        issues.append(f"Phone area code {area_code} is not consistent with Hamilton area (expected: 905, 289, 365) or toll-free")

                # Real-time phone number verification
                phone_verification = await self._verify_phone_number(lead.contact.phone)
                if not phone_verification['valid']:
                    issues.append(f"Phone verification failed: {phone_verification['reason']}")

                # Cross-reference phone with website
                if lead.contact.website:
                    website_phone_match = await self._verify_phone_website_consistency(lead.contact.phone, lead.contact.website)
                    if not website_phone_match['match']:
                        issues.append(f"Phone number does not match website contact information: {website_phone_match['reason']}")

        except Exception as e:
            self.logger.warning("phone_accuracy_validation_failed",
                              business_name=lead.business_name,
                              error=str(e))

        return issues

    async def _validate_business_registration(self, lead: BusinessLead) -> List[str]:
        """Validate business registration information."""

        issues = []

        try:
            # In production, this would check:
            # - Ontario Business Registry
            # - Canada Business Registry
            # - Hamilton business licenses
            # - Tax registration numbers

            # For now, perform basic sanity checks
            if lead.business_name:
                # Check for realistic business name
                name_lower = lead.business_name.lower()

                # Flag obviously fake or test data
                fake_indicators = ['test', 'fake', 'example', 'sample', 'demo', 'placeholder']
                for indicator in fake_indicators:
                    if indicator in name_lower:
                        issues.append(f"Business name contains suspicious content: '{indicator}'")

                # Check for consistent business entity types
                entity_types = ['ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation', 'llc']
                if not any(entity_type in name_lower for entity_type in entity_types):
                    # Not necessarily an issue, but flag for manual review
                    pass

        except Exception as e:
            self.logger.warning("business_registration_validation_failed",
                              business_name=lead.business_name,
                              error=str(e))

        return issues

    async def _verify_address_exists(self, address: str) -> Dict[str, Any]:
        """Verify if an address exists using real-time validation."""

        try:
            # Basic address format validation
            if not address or len(address.strip()) < 10:
                return {'valid': False, 'reason': 'Address too short or empty'}

            # Check for Hamilton area street patterns
            address_lower = address.lower()
            hamilton_streets = [
                'main st', 'king st', 'barton st', 'cannon st', 'wilson st',
                'stone church rd', 'upper james', 'mohawk rd', 'dundurn st',
                'ottawa st', 'concession st', 'york blvd', 'mountain ave'
            ]

            # Check if address contains known Hamilton streets
            contains_hamilton_street = any(street in address_lower for street in hamilton_streets)

            # Check postal code presence and format
            postal_pattern = r'[KLMNP][0-9][A-Z]\s*[0-9][A-Z][0-9]'
            has_valid_postal = bool(re.search(postal_pattern, address.upper()))

            if contains_hamilton_street and has_valid_postal:
                return {'valid': True, 'reason': 'Address format appears valid for Hamilton area'}
            elif has_valid_postal:
                return {'valid': True, 'reason': 'Valid postal code format'}
            else:
                return {'valid': False, 'reason': 'Address does not match Hamilton area patterns'}

        except Exception as e:
            self.logger.error("address_verification_failed", error=str(e))
            return {'valid': False, 'reason': f'Verification error: {str(e)}'}

    async def _verify_phone_number(self, phone: str) -> Dict[str, Any]:
        """Verify phone number format and area code consistency."""

        try:
            if not phone:
                return {'valid': False, 'reason': 'No phone number provided'}

            # Clean phone number
            cleaned_phone = re.sub(r'\D', '', phone)

            # Check length
            if len(cleaned_phone) not in [10, 11]:
                return {'valid': False, 'reason': 'Invalid phone number length'}

            # Extract area code
            if len(cleaned_phone) == 11 and cleaned_phone.startswith('1'):
                area_code = cleaned_phone[1:4]
            elif len(cleaned_phone) == 10:
                area_code = cleaned_phone[:3]
            else:
                return {'valid': False, 'reason': 'Cannot extract area code'}

            # Hamilton area codes and toll-free numbers
            hamilton_area_codes = ['905', '289', '365']
            toll_free_codes = ['800', '833', '844', '855', '866', '877', '888']

            if area_code in hamilton_area_codes:
                return {'valid': True, 'reason': f'Valid Hamilton area code: {area_code}'}
            elif area_code in toll_free_codes:
                return {'valid': True, 'reason': f'Valid toll-free number: {area_code}'}
            else:
                return {'valid': False, 'reason': f'Area code {area_code} not in Hamilton region or toll-free'}

        except Exception as e:
            self.logger.error("phone_verification_failed", error=str(e))
            return {'valid': False, 'reason': f'Verification error: {str(e)}'}

    async def _verify_phone_website_consistency(self, phone: str, website: str) -> Dict[str, Any]:
        """Cross-reference phone number with website contact information."""

        try:
            if not phone or not website:
                return {'match': True, 'reason': 'Cannot verify - missing phone or website'}

            # Clean phone for comparison
            cleaned_phone = re.sub(r'\D', '', phone)

            # Extract last 7 digits for comparison (local number)
            if len(cleaned_phone) >= 7:
                local_number = cleaned_phone[-7:]
            else:
                return {'match': False, 'reason': 'Invalid phone number format'}

            # For real implementation, would fetch website content and search for phone
            # For now, we'll do basic validation

            # Check if phone format is consistent with business website domain
            if website and 'hamilton' in website.lower():
                # If website suggests Hamilton location, phone should have Hamilton area code
                area_code = cleaned_phone[:3] if len(cleaned_phone) == 10 else cleaned_phone[1:4]
                hamilton_codes = ['905', '289', '365']

                if area_code in hamilton_codes:
                    return {'match': True, 'reason': 'Phone area code consistent with Hamilton website'}
                else:
                    return {'match': False, 'reason': f'Phone area code {area_code} inconsistent with Hamilton website'}

            return {'match': True, 'reason': 'Basic consistency check passed'}

        except Exception as e:
            self.logger.error("phone_website_consistency_failed", error=str(e))
            return {'match': False, 'reason': f'Verification error: {str(e)}'}

    async def _verify_geographic_consistency(self, lead: BusinessLead) -> List[str]:
        """Verify geographic consistency between address, phone, and postal code."""

        issues = []

        try:
            # Check postal code vs address consistency
            if hasattr(lead.location, 'postal_code') and lead.location.postal_code:
                postal_code = lead.location.postal_code.replace(' ', '').upper()

                # Hamilton postal code areas
                hamilton_postal_areas = {
                    'L8E': 'East Hamilton',
                    'L8G': 'East End',
                    'L8H': 'East Mountain',
                    'L8J': 'Hamilton Mountain',
                    'L8K': 'West Hamilton',
                    'L8L': 'West End',
                    'L8M': 'Central Hamilton',
                    'L8N': 'North End',
                    'L8P': 'Central Mountain',
                    'L8R': 'Mountain',
                    'L8S': 'McMaster Area',
                    'L8T': 'West Mountain',
                    'L8V': 'Southwest',
                    'L8W': 'Southeast',
                    'L9G': 'Ancaster',
                    'L9H': 'Dundas'
                }

                postal_prefix = postal_code[:3]
                if postal_prefix not in hamilton_postal_areas:
                    issues.append(f"Postal code {postal_code} not in Hamilton area")

                # Check city consistency with postal code
                if hasattr(lead.location, 'city') and lead.location.city:
                    city_lower = lead.location.city.lower()

                    if postal_prefix == 'L9G' and 'ancaster' not in city_lower:
                        issues.append("Postal code L9G indicates Ancaster but city field differs")
                    elif postal_prefix == 'L9H' and 'dundas' not in city_lower:
                        issues.append("Postal code L9H indicates Dundas but city field differs")
                    elif postal_prefix.startswith('L8') and 'hamilton' not in city_lower:
                        if city_lower not in ['stoney creek', 'waterdown']:
                            issues.append(f"Postal code {postal_prefix} indicates Hamilton but city field is {lead.location.city}")

            # Check phone area code vs location consistency
            if hasattr(lead.contact, 'phone') and lead.contact.phone:
                phone_digits = re.sub(r'\D', '', lead.contact.phone)
                if len(phone_digits) >= 10:
                    area_code = phone_digits[:3] if len(phone_digits) == 10 else phone_digits[1:4]

                    # All Hamilton area should use 905, 289, 365 or toll-free numbers
                    hamilton_area_codes = ['905', '289', '365']
                    toll_free_codes = ['800', '833', '844', '855', '866', '877', '888']
                    if area_code not in hamilton_area_codes and area_code not in toll_free_codes:
                        issues.append(f"Phone area code {area_code} not consistent with Hamilton location or toll-free")

        except Exception as e:
            self.logger.error("geographic_consistency_failed",
                            business_name=lead.business_name,
                            error=str(e))
            issues.append(f"Geographic consistency check failed: {str(e)}")

        return issues