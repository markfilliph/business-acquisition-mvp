"""
Contact Enrichment and Verification Module
Validates and enriches contact information using multiple API sources.
"""

import os
import logging
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import requests
from requests_cache import CachedSession
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class ContactValidationResult:
    email_valid: bool
    person_exists: bool
    role_confirmed: bool
    recent_activity: bool
    confidence_score: float
    enriched_data: Dict[str, Any]
    validation_sources: List[str]

class ContactEnrichment:
    """Enhanced contact validation and enrichment using multiple APIs."""

    def __init__(self):
        self.session = CachedSession(
            cache_name='contact_cache',
            expire_after=3600  # 1 hour cache
        )

        # API configurations
        self.api_keys = {
            'hunter': os.getenv('HUNTER_API_KEY'),
            'neverbounce': os.getenv('NEVERBOUNCE_API_KEY'),
            'clearbit': os.getenv('CLEARBIT_API_KEY'),
            'apollo': os.getenv('APOLLO_API_KEY')
        }

        # Rate limiting
        self.rate_limits = {
            'hunter': {'calls': 0, 'reset_time': 0, 'limit': 100},
            'neverbounce': {'calls': 0, 'reset_time': 0, 'limit': 1000},
            'clearbit': {'calls': 0, 'reset_time': 0, 'limit': 200}
        }

    def _check_rate_limit(self, service: str) -> bool:
        """Check if we can make an API call within rate limits."""
        current_time = time.time()
        rate_info = self.rate_limits.get(service, {})

        if current_time > rate_info.get('reset_time', 0):
            rate_info['calls'] = 0
            rate_info['reset_time'] = current_time + 3600  # Reset hourly

        if rate_info['calls'] >= rate_info.get('limit', 0):
            logger.warning(f"Rate limit reached for {service}")
            return False

        rate_info['calls'] += 1
        return True

    def validate_with_neverbounce(self, email: str) -> Dict[str, Any]:
        """Validate email using NeverBounce API."""
        if not self.api_keys['neverbounce'] or not self._check_rate_limit('neverbounce'):
            return {'valid': False, 'source': 'neverbounce', 'error': 'API unavailable'}

        try:
            url = "https://api.neverbounce.com/v4/single/check"
            params = {
                'key': self.api_keys['neverbounce'],
                'email': email
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = data.get('result', 'unknown')
            return {
                'valid': result == 'valid',
                'result': result,
                'flags': data.get('flags', []),
                'source': 'neverbounce',
                'confidence': 0.95 if result == 'valid' else 0.3
            }

        except Exception as e:
            logger.error(f"NeverBounce validation failed for {email}: {e}")
            return {'valid': False, 'source': 'neverbounce', 'error': str(e)}

    def validate_with_hunter(self, email: str) -> Dict[str, Any]:
        """Validate email using Hunter.io API."""
        if not self.api_keys['hunter'] or not self._check_rate_limit('hunter'):
            return {'valid': False, 'source': 'hunter', 'error': 'API unavailable'}

        try:
            url = "https://api.hunter.io/v2/email-verifier"
            params = {
                'email': email,
                'api_key': self.api_keys['hunter']
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = data.get('data', {})
            status = result.get('status', 'unknown')

            return {
                'valid': status == 'valid',
                'status': status,
                'score': result.get('score', 0),
                'regexp': result.get('regexp', False),
                'gibberish': result.get('gibberish', False),
                'disposable': result.get('disposable', False),
                'webmail': result.get('webmail', False),
                'mx_records': result.get('mx_records', False),
                'smtp_server': result.get('smtp_server', False),
                'smtp_check': result.get('smtp_check', False),
                'accept_all': result.get('accept_all', False),
                'block': result.get('block', False),
                'source': 'hunter',
                'confidence': result.get('score', 0) / 100
            }

        except Exception as e:
            logger.error(f"Hunter validation failed for {email}: {e}")
            return {'valid': False, 'source': 'hunter', 'error': str(e)}

    def verify_with_apollo(self, email: str) -> Dict[str, Any]:
        """Verify person exists using Apollo.io API."""
        if not self.api_keys['apollo']:
            return {'exists': False, 'source': 'apollo', 'error': 'API unavailable'}

        try:
            url = "https://api.apollo.io/v1/people/match"
            headers = {
                'Cache-Control': 'no-cache',
                'X-Api-Key': self.api_keys['apollo']
            }
            data = {'email': email}

            response = self.session.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            person = result.get('person')
            if person:
                return {
                    'exists': True,
                    'name': person.get('name'),
                    'title': person.get('title'),
                    'company': person.get('organization', {}).get('name'),
                    'linkedin_url': person.get('linkedin_url'),
                    'source': 'apollo',
                    'confidence': 0.9
                }
            else:
                return {'exists': False, 'source': 'apollo', 'confidence': 0.1}

        except Exception as e:
            logger.error(f"Apollo verification failed for {email}: {e}")
            return {'exists': False, 'source': 'apollo', 'error': str(e)}

    def check_linkedin_profile(self, email: str) -> Dict[str, Any]:
        """Check LinkedIn profile information (simplified implementation)."""
        try:
            # This would require LinkedIn API access or web scraping
            # For now, return a placeholder
            domain = email.split('@')[1] if '@' in email else ''

            # Basic heuristics for role confirmation
            common_executive_domains = [
                'gmail.com', 'outlook.com', 'yahoo.com'  # Personal emails
            ]

            if domain not in common_executive_domains:
                return {
                    'profile_found': True,
                    'role_confirmed': True,
                    'confidence': 0.7,
                    'source': 'linkedin_heuristic'
                }
            else:
                return {
                    'profile_found': False,
                    'role_confirmed': False,
                    'confidence': 0.3,
                    'source': 'linkedin_heuristic'
                }

        except Exception as e:
            logger.error(f"LinkedIn check failed for {email}: {e}")
            return {'profile_found': False, 'source': 'linkedin', 'error': str(e)}

    def check_engagement_signals(self, email: str) -> Dict[str, Any]:
        """Check for recent engagement signals."""
        try:
            domain = email.split('@')[1] if '@' in email else ''

            # Check domain age and activity (simplified)
            try:
                response = self.session.get(f"http://{domain}", timeout=5)
                website_active = response.status_code == 200
            except:
                website_active = False

            return {
                'website_active': website_active,
                'recent_activity': website_active,
                'confidence': 0.6 if website_active else 0.2,
                'source': 'engagement_check'
            }

        except Exception as e:
            logger.error(f"Engagement check failed for {email}: {e}")
            return {'recent_activity': False, 'source': 'engagement', 'error': str(e)}

    def enrich_contact(self, email: str) -> ContactValidationResult:
        """Main method to enrich and validate contact information."""
        logger.info(f"Enriching contact: {email}")

        # Run all validations
        validations = {}
        sources_used = []

        # Email validation
        neverbounce_result = self.validate_with_neverbounce(email)
        hunter_result = self.validate_with_hunter(email)

        # Person verification
        apollo_result = self.verify_with_apollo(email)
        linkedin_result = self.check_linkedin_profile(email)
        engagement_result = self.check_engagement_signals(email)

        # Aggregate results
        email_valid = (
            neverbounce_result.get('valid', False) or
            hunter_result.get('valid', False)
        )

        person_exists = apollo_result.get('exists', False)
        role_confirmed = linkedin_result.get('role_confirmed', False)
        recent_activity = engagement_result.get('recent_activity', False)

        # Calculate confidence score
        confidence_scores = [
            neverbounce_result.get('confidence', 0),
            hunter_result.get('confidence', 0),
            apollo_result.get('confidence', 0),
            linkedin_result.get('confidence', 0),
            engagement_result.get('confidence', 0)
        ]

        confidence_score = sum(confidence_scores) / len(confidence_scores)

        # Collect enriched data
        enriched_data = {
            'neverbounce': neverbounce_result,
            'hunter': hunter_result,
            'apollo': apollo_result,
            'linkedin': linkedin_result,
            'engagement': engagement_result,
            'validation_timestamp': time.time()
        }

        sources_used = ['neverbounce', 'hunter', 'apollo', 'linkedin', 'engagement']

        return ContactValidationResult(
            email_valid=email_valid,
            person_exists=person_exists,
            role_confirmed=role_confirmed,
            recent_activity=recent_activity,
            confidence_score=confidence_score,
            enriched_data=enriched_data,
            validation_sources=sources_used
        )

    def batch_enrich_contacts(self, emails: List[str]) -> Dict[str, ContactValidationResult]:
        """Batch process multiple contacts with rate limiting."""
        results = {}

        for i, email in enumerate(emails):
            try:
                result = self.enrich_contact(email)
                results[email] = result

                # Rate limiting between requests
                if i < len(emails) - 1:
                    time.sleep(0.5)  # 2 requests per second

            except Exception as e:
                logger.error(f"Failed to enrich {email}: {e}")
                results[email] = ContactValidationResult(
                    email_valid=False,
                    person_exists=False,
                    role_confirmed=False,
                    recent_activity=False,
                    confidence_score=0.0,
                    enriched_data={'error': str(e)},
                    validation_sources=['error']
                )

        return results

# Convenience function for backwards compatibility
def enrich_contact(email: str) -> bool:
    """Simple boolean check for contact validity."""
    enricher = ContactEnrichment()
    result = enricher.enrich_contact(email)

    # Return True if contact passes basic validation checks
    return (result.email_valid and
            result.person_exists and
            result.confidence_score > 0.5)

if __name__ == "__main__":
    # Test the enrichment system
    enricher = ContactEnrichment()
    test_email = "test@example.com"
    result = enricher.enrich_contact(test_email)

    print(f"Email: {test_email}")
    print(f"Valid: {result.email_valid}")
    print(f"Person exists: {result.person_exists}")
    print(f"Confidence: {result.confidence_score:.2f}")