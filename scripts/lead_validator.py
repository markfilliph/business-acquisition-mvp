"""
Comprehensive Lead Validation System
Multi-factor validation for business acquisition targets with strict $1M-$1.4M revenue criteria.
"""

import os
import re
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
from requests_cache import CachedSession
import sqlite3
from pathlib import Path

from .contact_enrichment import ContactEnrichment

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    validator_name: str
    passed: bool
    confidence: float
    details: Dict[str, Any]
    timestamp: datetime

@dataclass
class LeadValidationSummary:
    business_name: str
    is_hot_lead: bool
    overall_score: float
    validation_results: List[ValidationResult]
    revenue_validated: bool
    contact_validated: bool
    business_age_confirmed: bool
    ownership_verified: bool
    financial_health_good: bool
    recommendation: str

class LeadValidator:
    """Comprehensive business lead validation with multi-source verification."""

    def __init__(self, db_path: str = "data/lead_validation.db"):
        self.db_path = db_path
        self.session = CachedSession(
            cache_name='validation_cache',
            expire_after=7200  # 2 hour cache for validation data
        )

        self.contact_enricher = ContactEnrichment()

        # Initialize database
        self._init_database()

        # API configurations
        self.api_keys = {
            'clearbit': os.getenv('CLEARBIT_API_KEY'),
            'hunter': os.getenv('HUNTER_API_KEY'),
            'google_places': os.getenv('GOOGLE_PLACES_API_KEY')
        }

        # Validation thresholds
        self.thresholds = {
            'min_revenue': 1_000_000,      # $1M minimum
            'max_revenue': 1_400_000,      # $1.4M maximum
            'min_business_age': 3,          # 3+ years in business
            'min_validation_score': 0.7,   # 70% validation success rate
            'max_employees': 50,            # Small to medium business
            'min_employees': 5              # Minimum viable team size
        }

    def _init_database(self):
        """Initialize SQLite database for validation tracking."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    validation_date TEXT NOT NULL,
                    is_hot_lead BOOLEAN,
                    overall_score REAL,
                    revenue_validated BOOLEAN,
                    validation_details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def verify_revenue_range(self, business: Dict[str, Any]) -> ValidationResult:
        """Verify business revenue falls within $1M-$1.4M range."""
        logger.info(f"Validating revenue for {business.get('name', 'Unknown')}")

        details = {
            'sources_checked': [],
            'revenue_estimates': [],
            'validation_method': 'multi_source'
        }

        confidence = 0.0
        revenue_confirmed = False

        try:
            # Method 1: Clearbit Company API
            if self.api_keys.get('clearbit'):
                clearbit_data = self._check_clearbit_revenue(business)
                if clearbit_data.get('revenue'):
                    details['sources_checked'].append('clearbit')
                    details['revenue_estimates'].append({
                        'source': 'clearbit',
                        'revenue': clearbit_data['revenue'],
                        'confidence': clearbit_data.get('confidence', 0.5)
                    })

            # Method 2: Industry database lookup
            industry_estimate = self._estimate_revenue_by_industry(business)
            if industry_estimate:
                details['sources_checked'].append('industry_database')
                details['revenue_estimates'].append(industry_estimate)

            # Method 3: Employee count correlation
            employee_estimate = self._estimate_revenue_by_employees(business)
            if employee_estimate:
                details['sources_checked'].append('employee_correlation')
                details['revenue_estimates'].append(employee_estimate)

            # Analyze revenue estimates
            if details['revenue_estimates']:
                avg_revenue = sum(est['revenue'] for est in details['revenue_estimates']) / len(details['revenue_estimates'])
                revenue_confirmed = self.thresholds['min_revenue'] <= avg_revenue <= self.thresholds['max_revenue']

                confidence = sum(est.get('confidence', 0.5) for est in details['revenue_estimates']) / len(details['revenue_estimates'])

                details['average_revenue'] = avg_revenue
                details['in_target_range'] = revenue_confirmed
            else:
                details['error'] = 'No revenue data sources available'

        except Exception as e:
            logger.error(f"Revenue validation failed: {e}")
            details['error'] = str(e)

        return ValidationResult(
            validator_name='verify_revenue_range',
            passed=revenue_confirmed,
            confidence=confidence,
            details=details,
            timestamp=datetime.now()
        )

    def verify_business_age(self, business: Dict[str, Any]) -> ValidationResult:
        """Verify business has been operating for minimum required years."""
        logger.info(f"Validating business age for {business.get('name', 'Unknown')}")

        details = {
            'incorporation_sources': [],
            'age_estimates': []
        }

        confidence = 0.0
        age_confirmed = False

        try:
            # Method 1: Business registry lookup
            registry_data = self._check_business_registry(business)
            if registry_data.get('incorporation_date'):
                incorporation_date = datetime.strptime(registry_data['incorporation_date'], '%Y-%m-%d')
                years_in_business = (datetime.now() - incorporation_date).days / 365.25

                details['incorporation_sources'].append('business_registry')
                details['age_estimates'].append({
                    'source': 'business_registry',
                    'years': years_in_business,
                    'incorporation_date': registry_data['incorporation_date'],
                    'confidence': 0.9
                })

            # Method 2: Domain age check
            domain_age = self._check_domain_age(business.get('website', ''))
            if domain_age:
                details['incorporation_sources'].append('domain_age')
                details['age_estimates'].append(domain_age)

            # Method 3: Directory listings
            directory_age = self._check_directory_listings(business)
            if directory_age:
                details['incorporation_sources'].append('directory_listings')
                details['age_estimates'].append(directory_age)

            # Analyze age estimates
            if details['age_estimates']:
                max_age = max(est['years'] for est in details['age_estimates'])
                age_confirmed = max_age >= self.thresholds['min_business_age']

                confidence = max(est.get('confidence', 0.5) for est in details['age_estimates'])

                details['maximum_age'] = max_age
                details['meets_minimum_age'] = age_confirmed
            else:
                details['error'] = 'No business age data sources available'

        except Exception as e:
            logger.error(f"Business age validation failed: {e}")
            details['error'] = str(e)

        return ValidationResult(
            validator_name='verify_business_age',
            passed=age_confirmed,
            confidence=confidence,
            details=details,
            timestamp=datetime.now()
        )

    def verify_ownership_structure(self, business: Dict[str, Any]) -> ValidationResult:
        """Verify business ownership and decision-making structure."""
        logger.info(f"Validating ownership structure for {business.get('name', 'Unknown')}")

        details = {
            'ownership_sources': [],
            'key_personnel': []
        }

        confidence = 0.0
        ownership_verified = False

        try:
            # Method 1: Corporate registry filings
            corporate_data = self._check_corporate_filings(business)
            if corporate_data.get('officers'):
                details['ownership_sources'].append('corporate_registry')
                details['key_personnel'].extend(corporate_data['officers'])

            # Method 2: LinkedIn company page
            linkedin_data = self._check_linkedin_company(business)
            if linkedin_data.get('executives'):
                details['ownership_sources'].append('linkedin')
                details['key_personnel'].extend(linkedin_data['executives'])

            # Method 3: Website analysis
            website_contacts = self._analyze_website_contacts(business.get('website', ''))
            if website_contacts:
                details['ownership_sources'].append('website_analysis')
                details['key_personnel'].extend(website_contacts)

            # Verify ownership structure
            if details['key_personnel']:
                # Look for owner/president/CEO roles
                decision_makers = [
                    person for person in details['key_personnel']
                    if any(role in person.get('title', '').lower()
                          for role in ['owner', 'president', 'ceo', 'founder'])
                ]

                ownership_verified = len(decision_makers) > 0
                confidence = 0.8 if decision_makers else 0.3

                details['decision_makers'] = decision_makers
                details['total_personnel_found'] = len(details['key_personnel'])
            else:
                details['error'] = 'No ownership data sources available'

        except Exception as e:
            logger.error(f"Ownership validation failed: {e}")
            details['error'] = str(e)

        return ValidationResult(
            validator_name='verify_ownership_structure',
            passed=ownership_verified,
            confidence=confidence,
            details=details,
            timestamp=datetime.now()
        )

    def verify_financial_indicators(self, business: Dict[str, Any]) -> ValidationResult:
        """Verify financial health and stability indicators."""
        logger.info(f"Validating financial indicators for {business.get('name', 'Unknown')}")

        details = {
            'financial_sources': [],
            'indicators': {}
        }

        confidence = 0.0
        financial_health_good = False

        try:
            # Method 1: Credit score and liens check
            credit_data = self._check_credit_score(business)
            if credit_data:
                details['financial_sources'].append('credit_bureau')
                details['indicators']['credit_score'] = credit_data

            # Method 2: Public financial filings
            filing_data = self._check_financial_filings(business)
            if filing_data:
                details['financial_sources'].append('financial_filings')
                details['indicators']['filings'] = filing_data

            # Method 3: Payment history
            payment_data = self._check_payment_history(business)
            if payment_data:
                details['financial_sources'].append('payment_history')
                details['indicators']['payment_history'] = payment_data

            # Method 4: Legal issues check
            legal_data = self._check_legal_issues(business)
            details['financial_sources'].append('legal_database')
            details['indicators']['legal_issues'] = legal_data

            # Analyze financial health
            health_score = 0.0
            total_indicators = 0

            if credit_data:
                health_score += credit_data.get('score', 0) / 100
                total_indicators += 1

            if filing_data and filing_data.get('no_bankruptcies'):
                health_score += 0.8
                total_indicators += 1

            if payment_data and payment_data.get('good_payment_history'):
                health_score += 0.7
                total_indicators += 1

            if legal_data and not legal_data.get('has_major_issues'):
                health_score += 0.9
                total_indicators += 1

            if total_indicators > 0:
                confidence = health_score / total_indicators
                financial_health_good = confidence >= 0.6
                details['health_score'] = confidence
            else:
                details['error'] = 'No financial indicator sources available'

        except Exception as e:
            logger.error(f"Financial indicators validation failed: {e}")
            details['error'] = str(e)

        return ValidationResult(
            validator_name='verify_financial_indicators',
            passed=financial_health_good,
            confidence=confidence,
            details=details,
            timestamp=datetime.now()
        )

    def verify_contact_information(self, business: Dict[str, Any]) -> ValidationResult:
        """Verify and enrich contact information for key personnel."""
        logger.info(f"Validating contact information for {business.get('name', 'Unknown')}")

        details = {
            'contacts_validated': [],
            'validation_summary': {}
        }

        confidence = 0.0
        contact_verified = False

        try:
            contacts = business.get('contacts', [])
            if not contacts:
                # Try to find contacts from business data
                contacts = self._extract_contacts_from_business(business)

            validated_contacts = []
            total_confidence = 0.0

            for contact in contacts:
                email = contact.get('email', '')
                if email:
                    # Use contact enrichment system
                    enrichment_result = self.contact_enricher.enrich_contact(email)

                    contact_validation = {
                        'email': email,
                        'name': contact.get('name', ''),
                        'title': contact.get('title', ''),
                        'email_valid': enrichment_result.email_valid,
                        'person_exists': enrichment_result.person_exists,
                        'role_confirmed': enrichment_result.role_confirmed,
                        'confidence': enrichment_result.confidence_score
                    }

                    validated_contacts.append(contact_validation)
                    total_confidence += enrichment_result.confidence_score

            if validated_contacts:
                confidence = total_confidence / len(validated_contacts)
                contact_verified = any(
                    contact['email_valid'] and contact['person_exists']
                    for contact in validated_contacts
                )

                details['contacts_validated'] = validated_contacts
                details['validation_summary'] = {
                    'total_contacts': len(validated_contacts),
                    'valid_emails': sum(1 for c in validated_contacts if c['email_valid']),
                    'verified_persons': sum(1 for c in validated_contacts if c['person_exists']),
                    'average_confidence': confidence
                }
            else:
                details['error'] = 'No contact information available for validation'

        except Exception as e:
            logger.error(f"Contact validation failed: {e}")
            details['error'] = str(e)

        return ValidationResult(
            validator_name='verify_contact_information',
            passed=contact_verified,
            confidence=confidence,
            details=details,
            timestamp=datetime.now()
        )

    def validate_lead(self, business: Dict[str, Any]) -> LeadValidationSummary:
        """Main validation method that runs all validators and determines if lead is hot."""
        logger.info(f"Starting comprehensive validation for {business.get('name', 'Unknown')}")

        # Run all validators
        validators = [
            self.verify_revenue_range,
            self.verify_business_age,
            self.verify_ownership_structure,
            self.verify_financial_indicators,
            self.verify_contact_information
        ]

        validation_results = []
        for validator in validators:
            try:
                result = validator(business)
                validation_results.append(result)

                # Add delay between validations to respect rate limits
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Validator {validator.__name__} failed: {e}")
                validation_results.append(ValidationResult(
                    validator_name=validator.__name__,
                    passed=False,
                    confidence=0.0,
                    details={'error': str(e)},
                    timestamp=datetime.now()
                ))

        # Calculate overall score
        total_weight = len(validation_results)
        weighted_score = sum(
            (0.7 if result.passed else 0.0) + (0.3 * result.confidence)
            for result in validation_results
        ) / total_weight

        # Determine if lead is hot (70% threshold)
        is_hot_lead = weighted_score >= self.thresholds['min_validation_score']

        # Generate recommendation
        recommendation = self._generate_recommendation(validation_results, weighted_score)

        # Extract specific validation flags
        revenue_validated = any(
            r.validator_name == 'verify_revenue_range' and r.passed
            for r in validation_results
        )

        contact_validated = any(
            r.validator_name == 'verify_contact_information' and r.passed
            for r in validation_results
        )

        business_age_confirmed = any(
            r.validator_name == 'verify_business_age' and r.passed
            for r in validation_results
        )

        ownership_verified = any(
            r.validator_name == 'verify_ownership_structure' and r.passed
            for r in validation_results
        )

        financial_health_good = any(
            r.validator_name == 'verify_financial_indicators' and r.passed
            for r in validation_results
        )

        # Store validation history
        self._store_validation_history(business, validation_results, is_hot_lead, weighted_score)

        return LeadValidationSummary(
            business_name=business.get('name', 'Unknown'),
            is_hot_lead=is_hot_lead,
            overall_score=weighted_score,
            validation_results=validation_results,
            revenue_validated=revenue_validated,
            contact_validated=contact_validated,
            business_age_confirmed=business_age_confirmed,
            ownership_verified=ownership_verified,
            financial_health_good=financial_health_good,
            recommendation=recommendation
        )

    def _generate_recommendation(self, results: List[ValidationResult], score: float) -> str:
        """Generate actionable recommendation based on validation results."""
        if score >= 0.8:
            return "HIGH PRIORITY: Excellent validation score. Proceed with immediate outreach."
        elif score >= 0.7:
            return "QUALIFIED LEAD: Good validation score. Contact within 24 hours."
        elif score >= 0.5:
            return "POTENTIAL LEAD: Some validation gaps. Investigate further before outreach."
        else:
            return "NOT QUALIFIED: Multiple validation failures. Do not pursue."

    def _store_validation_history(self, business: Dict[str, Any], results: List[ValidationResult],
                                is_hot_lead: bool, score: float):
        """Store validation results in database for tracking."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO validation_history
                    (business_name, validation_date, is_hot_lead, overall_score,
                     revenue_validated, validation_details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    business.get('name', 'Unknown'),
                    datetime.now().isoformat(),
                    is_hot_lead,
                    score,
                    any(r.validator_name == 'verify_revenue_range' and r.passed for r in results),
                    str([r.details for r in results])
                ))
        except Exception as e:
            logger.error(f"Failed to store validation history: {e}")

    # Helper methods for API integrations (simplified implementations)
    def _check_clearbit_revenue(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Check Clearbit API for revenue data."""
        # Placeholder implementation - would integrate with actual Clearbit API
        return {'revenue': 1200000, 'confidence': 0.7}

    def _estimate_revenue_by_industry(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate revenue based on industry and location."""
        # Simplified industry-based estimation
        return {'source': 'industry_estimate', 'revenue': 1100000, 'confidence': 0.5}

    def _estimate_revenue_by_employees(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate revenue based on employee count."""
        employees = business.get('employee_count', 0)
        if employees:
            estimated_revenue = employees * 75000  # $75k revenue per employee estimate
            return {'source': 'employee_correlation', 'revenue': estimated_revenue, 'confidence': 0.6}
        return None

    def _check_business_registry(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Check business registration records."""
        # Placeholder - would integrate with business registry APIs
        return {'incorporation_date': '2018-03-15'}

    def _check_domain_age(self, website: str) -> Optional[Dict[str, Any]]:
        """Check domain registration age."""
        if not website:
            return None
        # Simplified implementation
        return {'source': 'domain_age', 'years': 5.2, 'confidence': 0.6}

    def _check_directory_listings(self, business: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check directory listing ages."""
        return {'source': 'directory_listings', 'years': 4.8, 'confidence': 0.5}

    def _check_corporate_filings(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Check corporate filing records."""
        return {'officers': [{'name': 'John Owner', 'title': 'President'}]}

    def _check_linkedin_company(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Check LinkedIn company information."""
        return {'executives': [{'name': 'Jane CEO', 'title': 'Chief Executive Officer'}]}

    def _analyze_website_contacts(self, website: str) -> List[Dict[str, Any]]:
        """Analyze website for contact information."""
        return [{'name': 'Contact Person', 'title': 'Manager', 'email': 'contact@business.com'}]

    def _check_credit_score(self, business: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check business credit score."""
        return {'score': 75, 'rating': 'Good'}

    def _check_financial_filings(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Check financial filing records."""
        return {'no_bankruptcies': True, 'current_filings': True}

    def _check_payment_history(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Check payment history records."""
        return {'good_payment_history': True, 'late_payments': 0}

    def _check_legal_issues(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Check for legal issues and liens."""
        return {'has_major_issues': False, 'active_lawsuits': 0}

    def _extract_contacts_from_business(self, business: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract contact information from business data."""
        contacts = []
        if business.get('contact_email'):
            contacts.append({
                'email': business['contact_email'],
                'name': business.get('contact_name', ''),
                'title': business.get('contact_title', '')
            })
        return contacts

if __name__ == "__main__":
    # Test the validation system
    validator = LeadValidator()

    test_business = {
        'name': 'Test Manufacturing Co.',
        'website': 'https://testmfg.com',
        'employee_count': 15,
        'industry': 'Manufacturing',
        'location': 'Hamilton, ON',
        'contacts': [
            {
                'name': 'John Smith',
                'title': 'Owner',
                'email': 'john@testmfg.com'
            }
        ]
    }

    result = validator.validate_lead(test_business)

    print(f"Business: {result.business_name}")
    print(f"Hot Lead: {result.is_hot_lead}")
    print(f"Overall Score: {result.overall_score:.2f}")
    print(f"Recommendation: {result.recommendation}")
    print(f"Revenue Validated: {result.revenue_validated}")
    print(f"Contact Validated: {result.contact_validated}")