"""
Owner/Contact Name Lookup Service

Attempts to find potential owner/decision-maker names for businesses using:
1. Website scraping (About Us, Contact pages)
2. WHOIS domain lookup
3. Pattern matching for common name patterns

This is a best-effort service - not all lookups will succeed.
"""
import asyncio
import re
from typing import Optional, Dict, List, Tuple
import aiohttp
from bs4 import BeautifulSoup
import whois
from urllib.parse import urlparse
import structlog

logger = structlog.get_logger(__name__)


class OwnerLookupService:
    """
    Service to look up potential business owners/decision makers.

    Methods:
    - Website scraping (About Us, Team, Contact pages)
    - WHOIS domain registration lookup
    - Pattern matching for owner names in content
    """

    def __init__(self):
        self.logger = logger
        self.stats = {
            'attempted': 0,
            'found_via_website': 0,
            'found_via_whois': 0,
            'not_found': 0,
            'errors': 0
        }

        # Common page patterns to check
        self.page_patterns = [
            '/about',
            '/about-us',
            '/team',
            '/contact',
            '/leadership',
            '/our-team',
            '/meet-the-team',
            '/company',
            '/who-we-are'
        ]

        # Name pattern regex
        # Matches patterns like "Founded by John Smith" or "President: Jane Doe"
        self.name_patterns = [
            r'(?:founded by|owner|president|ceo|director|principal|managed by)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)[,\s]+(?:founder|owner|president|ceo|director|principal)',
            r'contact[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:mr\.|ms\.|mrs\.)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]

    async def lookup_owner(
        self,
        business_name: str,
        website: str,
        timeout: int = 10
    ) -> Dict[str, any]:
        """
        Look up potential owner/contact for a business.

        Args:
            business_name: Name of the business
            website: Business website URL
            timeout: Request timeout in seconds

        Returns:
            Dict with 'name', 'source', 'confidence' keys
        """
        self.stats['attempted'] += 1

        result = {
            'name': None,
            'source': None,
            'confidence': 'none',
            'details': []
        }

        if not website or website.lower() in ['', 'n/a', 'none', 'nan']:
            self.stats['not_found'] += 1
            return result

        try:
            # Clean website URL
            website = self._clean_url(website)

            # Method 1: Try website scraping first (higher accuracy)
            owner_info = await self._lookup_from_website(website, business_name, timeout)
            if owner_info['name']:
                result.update(owner_info)
                self.stats['found_via_website'] += 1
                return result

            # Method 2: Try WHOIS lookup (lower accuracy, often shows registrar)
            owner_info = await self._lookup_from_whois(website)
            if owner_info['name']:
                result.update(owner_info)
                self.stats['found_via_whois'] += 1
                return result

            # No owner found
            self.stats['not_found'] += 1
            return result

        except Exception as e:
            self.logger.error("owner_lookup_failed",
                            business=business_name,
                            website=website,
                            error=str(e))
            self.stats['errors'] += 1
            result['details'].append(f"Error: {str(e)}")
            return result

    def _clean_url(self, url: str) -> str:
        """Clean and normalize URL."""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url

    async def _lookup_from_website(
        self,
        website: str,
        business_name: str,
        timeout: int
    ) -> Dict[str, any]:
        """
        Scrape website for owner/contact names.
        Checks About, Team, Contact pages.
        """
        result = {
            'name': None,
            'source': None,
            'confidence': 'none',
            'details': []
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Try homepage first
                names = await self._scrape_page_for_names(session, website, timeout)
                if names:
                    result['name'] = names[0]  # Take most confident match
                    result['source'] = 'website_homepage'
                    result['confidence'] = 'medium'
                    result['details'].append(f"Found on homepage")
                    return result

                # Try common pages
                for pattern in self.page_patterns:
                    page_url = website.rstrip('/') + pattern
                    names = await self._scrape_page_for_names(session, page_url, timeout)
                    if names:
                        result['name'] = names[0]
                        result['source'] = f'website_{pattern.strip("/")}'
                        result['confidence'] = 'high'
                        result['details'].append(f"Found on {pattern} page")
                        return result

                    # Don't hammer the server
                    await asyncio.sleep(0.5)

        except Exception as e:
            self.logger.debug("website_scraping_failed",
                            website=website,
                            error=str(e))
            result['details'].append(f"Website scraping failed: {str(e)}")

        return result

    async def _scrape_page_for_names(
        self,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int
    ) -> List[str]:
        """
        Scrape a single page for potential owner names.

        Returns:
            List of potential names (prioritized by confidence)
        """
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers={'User-Agent': 'Mozilla/5.0 (compatible; LeadBot/1.0)'}
            ) as response:
                if response.status != 200:
                    return []

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Get visible text
                text = soup.get_text()

                # Search for name patterns
                names = []
                for pattern in self.name_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        name = match.group(1).strip()
                        if self._is_valid_name(name):
                            names.append(name)

                # Deduplicate and return
                return list(dict.fromkeys(names))  # Preserve order, remove dupes

        except asyncio.TimeoutError:
            self.logger.debug("page_scrape_timeout", url=url)
            return []
        except Exception as e:
            self.logger.debug("page_scrape_failed", url=url, error=str(e))
            return []

    def _is_valid_name(self, name: str) -> bool:
        """
        Validate if a string is likely a real person's name.

        Filters out common false positives.
        """
        # Basic checks
        if len(name) < 5 or len(name) > 50:
            return False

        # Must be exactly 2 words (First Last)
        parts = name.split()
        if len(parts) != 2:
            return False

        # Each part must start with capital
        if not all(part[0].isupper() for part in parts):
            return False

        # Common false positives
        false_positives = [
            'contact us', 'about us', 'our team', 'join us',
            'click here', 'read more', 'learn more', 'get started',
            'sign up', 'log in', 'terms conditions', 'privacy policy'
        ]

        if name.lower() in false_positives:
            return False

        # Reject if it contains common company words
        company_words = ['inc', 'ltd', 'llc', 'corp', 'company', 'services']
        if any(word in name.lower() for word in company_words):
            return False

        return True

    async def _lookup_from_whois(self, website: str) -> Dict[str, any]:
        """
        Look up domain owner from WHOIS records.

        Note: Often shows registrar/privacy service, not actual owner.
        Marked as 'low' confidence.
        """
        result = {
            'name': None,
            'source': None,
            'confidence': 'none',
            'details': []
        }

        try:
            # Extract domain from URL
            parsed = urlparse(website)
            domain = parsed.netloc or parsed.path
            domain = domain.replace('www.', '')

            # Async WHOIS lookup (run in executor to not block)
            loop = asyncio.get_event_loop()
            whois_data = await loop.run_in_executor(
                None,
                lambda: whois.whois(domain)
            )

            # Extract name from WHOIS
            if whois_data and hasattr(whois_data, 'name'):
                name = whois_data.name
                if isinstance(name, list):
                    name = name[0] if name else None

                if name and self._is_valid_name(name):
                    result['name'] = name
                    result['source'] = 'whois'
                    result['confidence'] = 'low'  # WHOIS often inaccurate
                    result['details'].append("Found via WHOIS (may be registrar)")
                    return result

        except Exception as e:
            self.logger.debug("whois_lookup_failed",
                            website=website,
                            error=str(e))
            result['details'].append(f"WHOIS failed: {str(e)}")

        return result

    async def lookup_batch(
        self,
        businesses: List[Dict[str, str]],
        max_concurrent: int = 5
    ) -> List[Dict[str, any]]:
        """
        Look up owners for multiple businesses in parallel.

        Args:
            businesses: List of dicts with 'business_name' and 'website'
            max_concurrent: Max concurrent lookups

        Returns:
            List of owner lookup results
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def lookup_with_semaphore(business):
            async with semaphore:
                result = await self.lookup_owner(
                    business.get('business_name', 'Unknown'),
                    business.get('website', '')
                )
                # Add business name to result
                result['business_name'] = business.get('business_name')
                return result

        tasks = [lookup_with_semaphore(biz) for biz in businesses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error("batch_lookup_exception", error=str(result))
                self.stats['errors'] += 1
            else:
                valid_results.append(result)

        return valid_results

    def print_stats(self):
        """Print lookup statistics."""
        print(f"\n{'='*60}")
        print(f"OWNER LOOKUP STATISTICS")
        print(f"{'='*60}")
        print(f"Attempted:           {self.stats['attempted']}")
        print(f"Found (website):     {self.stats['found_via_website']}")
        print(f"Found (WHOIS):       {self.stats['found_via_whois']}")
        print(f"Not found:           {self.stats['not_found']}")
        print(f"Errors:              {self.stats['errors']}")

        success_rate = 0
        if self.stats['attempted'] > 0:
            found = self.stats['found_via_website'] + self.stats['found_via_whois']
            success_rate = (found / self.stats['attempted']) * 100

        print(f"Success rate:        {success_rate:.1f}%")
        print(f"{'='*60}\n")


# Combined lookup with LinkedIn
async def lookup_owners_for_leads_combined(leads: List[Dict], use_linkedin: bool = True) -> List[Dict]:
    """
    Combined owner lookup using multiple methods.

    Methods (in order):
    1. Website scraping (About/Team pages)
    2. WHOIS domain lookup
    3. LinkedIn search (via Google) - OPTIONAL

    Args:
        leads: List of lead dicts with 'business_name' and 'website'
        use_linkedin: Whether to include LinkedIn lookup (default True)

    Returns:
        Leads with owner info from all methods
    """
    from .linkedin_lookup import lookup_owners_linkedin

    print(f"\n👤 COMPREHENSIVE OWNER LOOKUP")
    print(f"{'='*60}")
    print(f"Businesses: {len(leads)}")
    print(f"Methods: Website + WHOIS + {'LinkedIn' if use_linkedin else 'No LinkedIn'}")
    print(f"{'='*60}\n")

    # Phase 1: Website + WHOIS lookup
    print(f"📋 Phase 1: Website & WHOIS Lookup")
    enriched_leads = await lookup_owners_for_leads(leads)

    # Phase 2: LinkedIn lookup (for those without owner info)
    if use_linkedin:
        print(f"\n📋 Phase 2: LinkedIn Lookup")

        # Count how many already have owner info
        already_found = sum(1 for lead in enriched_leads if lead.get('owner_name'))
        needs_linkedin = [lead for lead in enriched_leads if not lead.get('owner_name')]

        print(f"   Already found: {already_found}/{len(leads)}")
        print(f"   Needs LinkedIn lookup: {len(needs_linkedin)}")

        if needs_linkedin:
            # LinkedIn lookup for remaining
            linkedin_enriched = await lookup_owners_linkedin(needs_linkedin)

            # Merge LinkedIn results back
            linkedin_dict = {
                lead.get('business_name'): lead
                for lead in linkedin_enriched
            }

            for lead in enriched_leads:
                if not lead.get('owner_name'):
                    biz_name = lead.get('business_name')
                    linkedin_data = linkedin_dict.get(biz_name, {})

                    # If LinkedIn found a name, use it
                    if linkedin_data.get('linkedin_name'):
                        lead['owner_name'] = linkedin_data['linkedin_name']
                        lead['owner_source'] = linkedin_data.get('linkedin_url', 'linkedin')
                        lead['owner_confidence'] = linkedin_data.get('linkedin_confidence', 'medium')

                    # Always add LinkedIn fields
                    lead['linkedin_name'] = linkedin_data.get('linkedin_name', '')
                    lead['linkedin_url'] = linkedin_data.get('linkedin_url', '')
                    lead['linkedin_title'] = linkedin_data.get('linkedin_title', '')

        else:
            print(f"   ✅ All businesses already have owner info!")

    # Final statistics
    final_found = sum(1 for lead in enriched_leads if lead.get('owner_name'))
    print(f"\n{'='*60}")
    print(f"FINAL OWNER LOOKUP RESULTS")
    print(f"{'='*60}")
    print(f"Total businesses:    {len(enriched_leads)}")
    print(f"Owners found:        {final_found} ({final_found/len(enriched_leads)*100:.1f}%)")
    print(f"Not found:           {len(enriched_leads) - final_found}")
    print(f"{'='*60}\n")

    return enriched_leads


# Convenience function
async def lookup_owners_for_leads(leads: List[Dict]) -> List[Dict]:
    """
    Convenience function to lookup owners for a list of leads.

    Args:
        leads: List of lead dicts with 'business_name' and 'website'

    Returns:
        Same leads with 'owner_name', 'owner_source', 'owner_confidence' added
    """
    service = OwnerLookupService()

    print(f"\n🔍 Starting owner lookup for {len(leads)} businesses...")
    print(f"   This may take a few minutes...\n")

    results = await service.lookup_batch(leads, max_concurrent=3)

    # Merge results back into leads
    enriched_leads = []
    for i, lead in enumerate(leads):
        owner_info = results[i] if i < len(results) else {
            'name': None,
            'source': None,
            'confidence': 'none'
        }

        lead['owner_name'] = owner_info.get('name', '')
        lead['owner_source'] = owner_info.get('source', '')
        lead['owner_confidence'] = owner_info.get('confidence', 'none')

        enriched_leads.append(lead)

    service.print_stats()

    return enriched_leads
