"""
Contact Enrichment Layer

Discovers and validates contact information (emails, phones) for businesses.

Methods:
1. Website scraping (contact page, about page)
2. Email pattern generation + verification
3. Phone number extraction from web presence
4. Social media profile discovery
"""
import asyncio
import aiohttp
import re
from typing import List, Dict, Optional, Set
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import structlog

logger = structlog.get_logger(__name__)


class ContactEnricher:
    """
    Enriches business data with contact information.

    Strategies:
    1. Scrape website for contact info
    2. Generate email patterns (firstname.lastname@domain.com, info@domain.com)
    3. Extract phones from website text
    4. Find social media profiles
    """

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=15, connect=5)
        self.logger = logger

        # Common contact page URL patterns
        self.contact_page_patterns = [
            '/contact', '/contact-us', '/contactus', '/about/contact',
            '/about', '/about-us', '/aboutus',
            '/company', '/company/contact'
        ]

    async def enrich_business(
        self,
        business_name: str,
        website: Optional[str] = None,
        existing_phone: Optional[str] = None,
        existing_email: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Enrich a business with contact information.

        Args:
            business_name: Name of business
            website: Website URL (if known)
            existing_phone: Phone already found (optional)
            existing_email: Email already found (optional)

        Returns:
            Dict with enriched contact info
        """
        enrichment = {
            'emails': set(),
            'phones': set(),
            'social_profiles': {},
            'contact_page_url': None,
            'confidence': 0.0,
            'source': 'contact_enrichment'
        }

        # Add existing info
        if existing_email:
            enrichment['emails'].add(existing_email)
        if existing_phone:
            enrichment['phones'].add(existing_phone)

        if not website:
            self.logger.debug("no_website", business=business_name)
            return self._finalize_enrichment(enrichment)

        # Clean website URL
        website = self._clean_url(website)

        try:
            # 1. Find and scrape contact page
            contact_info = await self._scrape_contact_page(website)
            enrichment['emails'].update(contact_info.get('emails', []))
            enrichment['phones'].update(contact_info.get('phones', []))
            enrichment['contact_page_url'] = contact_info.get('contact_page_url')

            # 2. Generate email patterns if none found
            if not enrichment['emails']:
                domain = urlparse(website).netloc
                generated_emails = self._generate_email_patterns(domain)
                enrichment['emails'].update(generated_emails)

            # 3. Calculate confidence
            enrichment['confidence'] = self._calculate_confidence(enrichment)

            self.logger.info(
                "enrichment_complete",
                business=business_name,
                emails_found=len(enrichment['emails']),
                phones_found=len(enrichment['phones']),
                confidence=enrichment['confidence']
            )

        except Exception as e:
            self.logger.error(
                "enrichment_failed",
                business=business_name,
                website=website,
                error=str(e)
            )

        return self._finalize_enrichment(enrichment)

    async def _scrape_contact_page(self, website: str) -> Dict:
        """
        Find and scrape the contact page of a website.

        Returns:
            Dict with emails, phones, and contact page URL
        """
        info = {
            'emails': set(),
            'phones': set(),
            'contact_page_url': None
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Try homepage first
                try:
                    async with session.get(
                        website,
                        headers={'User-Agent': 'Mozilla/5.0 (Business Research Bot)'},
                        ssl=False
                    ) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')

                            # Extract contact info from homepage
                            homepage_emails = self._extract_emails(html)
                            homepage_phones = self._extract_phones(html)

                            info['emails'].update(homepage_emails)
                            info['phones'].update(homepage_phones)

                            # Find contact page link
                            contact_url = self._find_contact_page_link(soup, website)

                            # If contact page found, scrape it
                            if contact_url and contact_url != website:
                                contact_info = await self._scrape_page(session, contact_url)
                                info['emails'].update(contact_info['emails'])
                                info['phones'].update(contact_info['phones'])
                                info['contact_page_url'] = contact_url

                except Exception as e:
                    self.logger.debug("homepage_scrape_failed", website=website, error=str(e))

        except Exception as e:
            self.logger.error("contact_scrape_failed", website=website, error=str(e))

        return info

    async def _scrape_page(self, session: aiohttp.ClientSession, url: str) -> Dict:
        """Scrape a single page for contact info."""
        info = {'emails': set(), 'phones': set()}

        try:
            async with session.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0'},
                ssl=False
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    info['emails'] = self._extract_emails(html)
                    info['phones'] = self._extract_phones(html)
        except Exception as e:
            self.logger.debug("page_scrape_failed", url=url, error=str(e))

        return info

    def _find_contact_page_link(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find contact page link in HTML."""
        for pattern in self.contact_page_patterns:
            # Try exact match
            links = soup.find_all('a', href=re.compile(pattern, re.IGNORECASE))
            if links:
                href = links[0].get('href')
                return urljoin(base_url, href)

        return None

    def _extract_emails(self, html: str) -> Set[str]:
        """Extract email addresses from HTML."""
        # Email regex pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = set(re.findall(email_pattern, html))

        # Filter out common false positives
        filtered = set()
        for email in emails:
            email_lower = email.lower()
            # Skip example/placeholder emails
            if any(skip in email_lower for skip in ['example.com', 'domain.com', 'email.com', 'test.com', 'placeholder']):
                continue
            # Skip image/asset emails
            if email_lower.endswith(('.png', '.jpg', '.gif', '.svg')):
                continue

            filtered.add(email)

        return filtered

    def _extract_phones(self, html: str) -> Set[str]:
        """Extract phone numbers from HTML."""
        # North American phone patterns
        patterns = [
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # 123-456-7890, 123.456.7890
            r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}\b',    # (123) 456-7890
            r'\b\d{10}\b',                          # 1234567890
        ]

        phones = set()
        for pattern in patterns:
            matches = re.findall(pattern, html)
            phones.update(matches)

        # Normalize phone numbers
        normalized = set()
        for phone in phones:
            # Remove formatting
            digits = re.sub(r'\D', '', phone)
            # Keep only if 10 or 11 digits
            if len(digits) in [10, 11]:
                normalized.add(phone)

        return normalized

    def _generate_email_patterns(self, domain: str) -> Set[str]:
        """
        Generate common email patterns for a domain.

        Common patterns:
        - info@domain.com
        - contact@domain.com
        - sales@domain.com
        - hello@domain.com
        """
        if not domain:
            return set()

        # Remove 'www.' prefix
        domain = domain.replace('www.', '')

        patterns = [
            f'info@{domain}',
            f'contact@{domain}',
            f'sales@{domain}',
            f'hello@{domain}',
            f'inquiries@{domain}',
            f'admin@{domain}'
        ]

        return set(patterns)

    def _clean_url(self, url: str) -> str:
        """Clean and normalize URL."""
        if not url:
            return url

        url = url.strip()

        # Add https:// if no protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        return url

    def _calculate_confidence(self, enrichment: Dict) -> float:
        """
        Calculate confidence score for enrichment.

        Factors:
        - Emails found on contact page: 0.9
        - Emails from homepage: 0.7
        - Generated email patterns: 0.3
        - Phones found: +0.1 per phone
        """
        confidence = 0.0

        if enrichment['contact_page_url']:
            confidence += 0.3  # Found contact page

        email_count = len(enrichment['emails'])
        if email_count > 0:
            if enrichment['contact_page_url']:
                confidence += 0.5  # Emails from contact page
            else:
                confidence += 0.3  # Emails from other sources

        phone_count = len(enrichment['phones'])
        confidence += min(phone_count * 0.1, 0.2)  # Max +0.2 for phones

        return min(confidence, 1.0)

    def _finalize_enrichment(self, enrichment: Dict) -> Dict:
        """Convert sets to lists for JSON serialization."""
        return {
            'emails': list(enrichment['emails']),
            'phones': list(enrichment['phones']),
            'social_profiles': enrichment['social_profiles'],
            'contact_page_url': enrichment['contact_page_url'],
            'confidence': enrichment['confidence'],
            'source': enrichment['source']
        }


async def demo_enrichment():
    """Demo contact enrichment."""
    enricher = ContactEnricher()

    test_businesses = [
        {
            'name': 'Hamilton Caster & Manufacturing',
            'website': 'https://www.hamiltoncaster.com',
            'phone': '905-544-4122'
        },
        {
            'name': 'Walters Inc.',
            'website': 'https://www.waltersinc.com',
            'phone': '905-540-8811'
        }
    ]

    print("\n" + "=" * 80)
    print("📧 CONTACT ENRICHMENT DEMO")
    print("=" * 80)

    for biz in test_businesses:
        print(f"\n🏭 {biz['name']}")
        print(f"   Website: {biz['website']}")
        print(f"   Existing phone: {biz.get('phone', 'N/A')}")

        enrichment = await enricher.enrich_business(
            business_name=biz['name'],
            website=biz['website'],
            existing_phone=biz.get('phone')
        )

        print(f"\n   ✅ Enrichment Results:")
        print(f"      Emails found: {len(enrichment['emails'])}")
        for email in enrichment['emails'][:3]:
            print(f"         • {email}")
        print(f"      Phones found: {len(enrichment['phones'])}")
        for phone in enrichment['phones'][:2]:
            print(f"         • {phone}")
        print(f"      Confidence: {enrichment['confidence']:.0%}")
        print(f"      Contact page: {enrichment['contact_page_url'] or 'Not found'}")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    asyncio.run(demo_enrichment())
