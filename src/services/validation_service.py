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
        
        # 5. Business data sanity checks
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
            'repair', 'service', 'installation', 'contractor', 'contracting',
            
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
            trade_indicators = [
                'home', 'residential', 'commercial', 'install', 'fix',
                'custom', 'quality', 'professional', 'expert', 'reliable'
            ]
            if any(indicator in name_lower for indicator in trade_indicators):
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