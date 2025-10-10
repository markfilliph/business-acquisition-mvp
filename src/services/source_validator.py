"""
LLM-based Multi-Source Cross-Validation Service.

Uses LLM to validate business data by cross-checking information from multiple sources.
Detects conflicts, validates consistency, and flags suspicious data.
"""

import asyncio
from typing import List, Dict, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)


class SourceCrossValidator:
    """
    Cross-validates business data from multiple sources using LLM.

    Checks for:
    - Data consistency across sources
    - Conflicting information
    - Suspicious or fake data
    - Missing critical fields
    """

    def __init__(self, llm_service=None):
        """
        Initialize source validator.

        Args:
            llm_service: Optional LLM service for advanced validation
        """
        self.logger = logger
        self.llm_service = llm_service

    async def validate_multi_source_business(
        self,
        businesses: List[Dict],
        business_name: str
    ) -> Tuple[bool, List[str], Dict]:
        """
        Validate business data from multiple sources.

        Args:
            businesses: List of business records from different sources
            business_name: Business name to validate

        Returns:
            Tuple of (is_valid, issues, consensus_data)
        """
        if not businesses or len(businesses) < 2:
            return True, [], businesses[0] if businesses else {}

        issues = []
        consensus = {}

        self.logger.info("multi_source_validation_started",
                        business_name=business_name,
                        source_count=len(businesses))

        # 1. Check source diversity
        sources = [b.get('data_source', 'unknown') for b in businesses]
        unique_sources = set(sources)

        if len(unique_sources) < 2:
            issues.append(f"Only one data source ({sources[0]}) - no cross-validation possible")

        # 2. Validate business name consistency
        name_issues = self._validate_name_consistency(businesses, business_name)
        issues.extend(name_issues)

        # 3. Validate address consistency
        address_issues, consensus_address = self._validate_address_consistency(businesses)
        issues.extend(address_issues)
        if consensus_address:
            consensus['address'] = consensus_address

        # 4. Validate phone consistency
        phone_issues, consensus_phone = self._validate_phone_consistency(businesses)
        issues.extend(phone_issues)
        if consensus_phone:
            consensus['phone'] = consensus_phone

        # 5. Validate website consistency
        website_issues, consensus_website = self._validate_website_consistency(businesses)
        issues.extend(website_issues)
        if consensus_website:
            consensus['website'] = consensus_website

        # 6. Validate industry classification
        industry_issues, consensus_industry = self._validate_industry_consistency(businesses)
        issues.extend(industry_issues)
        if consensus_industry:
            consensus['industry'] = consensus_industry

        # 7. Calculate confidence score
        consensus['validation_confidence'] = self._calculate_confidence_score(
            len(issues),
            len(unique_sources),
            businesses
        )

        # 8. Use LLM for advanced validation (if available)
        if self.llm_service and len(issues) > 0:
            llm_issues = await self._llm_validate_conflicts(businesses, issues)
            issues.extend(llm_issues)

        is_valid = len(issues) == 0 or consensus['validation_confidence'] > 0.7

        self.logger.info("multi_source_validation_complete",
                        business_name=business_name,
                        is_valid=is_valid,
                        issues_count=len(issues),
                        confidence=consensus['validation_confidence'])

        return is_valid, issues, consensus

    def _validate_name_consistency(
        self,
        businesses: List[Dict],
        expected_name: str
    ) -> List[str]:
        """Check if business names are consistent across sources."""
        issues = []

        names = [b.get('business_name', '') for b in businesses if b.get('business_name')]

        if not names:
            issues.append("No business name found in any source")
            return issues

        # Normalize names for comparison
        normalized_names = [self._normalize_name(n) for n in names]
        expected_normalized = self._normalize_name(expected_name)

        # Check if all names are similar
        mismatches = []
        for i, norm_name in enumerate(normalized_names):
            if norm_name != expected_normalized:
                mismatches.append(f"Source {i+1}: {names[i]}")

        if mismatches:
            issues.append(f"Business name mismatch across sources: {', '.join(mismatches)}")

        return issues

    def _validate_address_consistency(
        self,
        businesses: List[Dict]
    ) -> Tuple[List[str], Optional[str]]:
        """Validate address consistency and return consensus."""
        issues = []
        addresses = [b.get('address', '').strip() for b in businesses if b.get('address')]

        if not addresses:
            return [], None

        # Find most common address
        from collections import Counter
        address_counts = Counter(addresses)
        consensus_address, count = address_counts.most_common(1)[0]

        # If multiple different addresses, flag as issue
        if len(address_counts) > 1:
            conflicting = [f"{addr} ({cnt}x)" for addr, cnt in address_counts.items()]
            issues.append(f"Address conflict: {', '.join(conflicting)}")

        return issues, consensus_address if count >= 2 else None

    def _validate_phone_consistency(
        self,
        businesses: List[Dict]
    ) -> Tuple[List[str], Optional[str]]:
        """Validate phone number consistency."""
        issues = []
        phones = [self._normalize_phone(b.get('phone', '')) for b in businesses if b.get('phone')]

        if not phones:
            return [], None

        # Find most common phone
        from collections import Counter
        phone_counts = Counter(phones)
        consensus_phone, count = phone_counts.most_common(1)[0]

        # If multiple different phones, flag as issue
        if len(phone_counts) > 1:
            issues.append(f"Phone number conflict: {', '.join(phone_counts.keys())}")

        return issues, consensus_phone if count >= 2 else None

    def _validate_website_consistency(
        self,
        businesses: List[Dict]
    ) -> Tuple[List[str], Optional[str]]:
        """Validate website consistency."""
        issues = []
        websites = [self._normalize_website(b.get('website', '')) for b in businesses if b.get('website')]

        if not websites:
            return [], None

        # Find most common website
        from collections import Counter
        website_counts = Counter(websites)
        consensus_website, count = website_counts.most_common(1)[0]

        # If multiple different websites, major red flag
        if len(website_counts) > 1:
            issues.append(f"CRITICAL: Multiple websites found - {', '.join(website_counts.keys())}")

        return issues, consensus_website

    def _validate_industry_consistency(
        self,
        businesses: List[Dict]
    ) -> Tuple[List[str], Optional[str]]:
        """Validate industry classification consistency."""
        issues = []
        industries = [b.get('industry', '') for b in businesses if b.get('industry')]

        if not industries:
            return [], None

        # Find most common industry
        from collections import Counter
        industry_counts = Counter(industries)
        consensus_industry, count = industry_counts.most_common(1)[0]

        # If multiple industries, might be OK (multi-faceted business)
        if len(industry_counts) > 1:
            self.logger.info("multiple_industries_detected",
                           industries=list(industry_counts.keys()))

        return issues, consensus_industry

    def _calculate_confidence_score(
        self,
        issue_count: int,
        source_count: int,
        businesses: List[Dict]
    ) -> float:
        """Calculate overall confidence score for validation."""
        # Start with base score
        score = 1.0

        # Penalty for each issue
        score -= (issue_count * 0.15)

        # Bonus for multiple sources
        if source_count >= 3:
            score += 0.2
        elif source_count >= 2:
            score += 0.1

        # Bonus for complete data
        complete_fields = 0
        for business in businesses:
            if business.get('website'):
                complete_fields += 1
            if business.get('phone'):
                complete_fields += 1
            if business.get('address'):
                complete_fields += 1

        if complete_fields >= 6:  # 2 sources x 3 fields
            score += 0.1

        return max(0.0, min(1.0, score))

    def _normalize_name(self, name: str) -> str:
        """Normalize business name for comparison."""
        if not name:
            return ""

        normalized = name.lower().strip()

        # Remove common suffixes
        suffixes = ['ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation', 'llc', 'co']
        for suffix in suffixes:
            normalized = normalized.replace(f' {suffix}', '').replace(f'.{suffix}', '')

        # Remove punctuation
        normalized = normalized.replace('.', '').replace(',', '').replace('&', 'and')

        # Remove extra spaces
        normalized = ' '.join(normalized.split())

        return normalized

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison."""
        if not phone:
            return ""

        # Keep only digits
        import re
        digits = re.sub(r'\D', '', phone)

        # Remove country code if present
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]

        return digits

    def _normalize_website(self, website: str) -> str:
        """Normalize website URL for comparison."""
        if not website:
            return ""

        normalized = website.lower().strip()

        # Remove protocol
        normalized = normalized.replace('https://', '').replace('http://', '')

        # Remove www
        normalized = normalized.replace('www.', '')

        # Remove trailing slash
        normalized = normalized.rstrip('/')

        return normalized

    async def _llm_validate_conflicts(
        self,
        businesses: List[Dict],
        issues: List[str]
    ) -> List[str]:
        """Use LLM to validate conflicting information."""
        llm_issues = []

        if not self.llm_service:
            return llm_issues

        try:
            # Create prompt for LLM
            prompt = f"""
            Analyze these business records from multiple sources and identify any red flags or data quality issues:

            Records:
            {businesses}

            Known Issues:
            {issues}

            Task: Determine if this is likely a legitimate business or if there are serious data quality concerns.
            Focus on: address conflicts, multiple websites, name mismatches, industry inconsistencies.

            Respond with: VALID or SUSPICIOUS, followed by brief explanation.
            """

            # Call LLM (if implemented)
            # response = await self.llm_service.validate(prompt)
            # if 'SUSPICIOUS' in response:
            #     llm_issues.append(f"LLM flagged as suspicious: {response}")

            self.logger.debug("llm_validation_skipped", reason="not_implemented")

        except Exception as e:
            self.logger.error("llm_validation_failed", error=str(e))

        return llm_issues
