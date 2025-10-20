#!/usr/bin/env python3
"""
Single Lead Enrichment Tool
Discovers owner name, email, LinkedIn profile, and succession signals
"""
import re
import sys
import json
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

class LeadEnricher:
    """Enriches a single lead with owner/decision maker information"""

    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch webpage content"""
        try:
            async with self.session.get(url, ssl=False) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"   ⚠️  HTTP {response.status} for {url}")
                    return None
        except asyncio.TimeoutError:
            print(f"   ⚠️  Timeout fetching {url}")
            return None
        except Exception as e:
            print(f"   ⚠️  Error fetching {url}: {e}")
            return None

    def extract_owner_from_text(self, text: str, business_name: str) -> List[Dict]:
        """Extract potential owner names from text using patterns"""
        candidates = []

        # Patterns for owner identification
        patterns = [
            r'(?:founded by|owner|proprietor|president|CEO|established by)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:,?\s+(?:founded|established|started|owner|president))',
            r'(?:contact|reach)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                # Avoid business name itself
                if name.lower() not in business_name.lower():
                    candidates.append({
                        'name': name,
                        'source': 'text_pattern',
                        'confidence': 0.6
                    })

        return candidates

    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)

        # Filter out common generic emails
        filtered = []
        generic_prefixes = {'info', 'contact', 'sales', 'support', 'admin', 'office'}

        for email in emails:
            prefix = email.split('@')[0].lower()
            if prefix not in generic_prefixes:
                filtered.insert(0, email)  # Prioritize specific emails
            else:
                filtered.append(email)

        return list(dict.fromkeys(filtered))  # Remove duplicates, preserve order

    async def scrape_about_page(self, base_url: str) -> Dict:
        """Scrape About/Team pages for owner information"""
        results = {
            'owners': [],
            'emails': [],
            'description': ''
        }

        # Common about page URLs
        about_urls = [
            urljoin(base_url, '/about'),
            urljoin(base_url, '/about-us'),
            urljoin(base_url, '/our-team'),
            urljoin(base_url, '/team'),
            urljoin(base_url, '/leadership'),
            urljoin(base_url, '/our-story'),
            base_url  # Homepage as fallback
        ]

        for url in about_urls:
            html = await self.fetch_page(url)
            if not html:
                continue

            soup = BeautifulSoup(html, 'html.parser')

            # Extract text content
            text = soup.get_text(separator=' ', strip=True)

            # Look for owner names
            business_name = urlparse(base_url).netloc.replace('www.', '').split('.')[0]
            owners = self.extract_owner_from_text(text, business_name)
            results['owners'].extend(owners)

            # Extract emails
            emails = self.extract_emails(text)
            results['emails'].extend(emails)

            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                results['description'] = meta_desc.get('content')[:300]

            # If we found something, no need to check other pages
            if results['owners'] or results['emails']:
                break

        # Deduplicate
        results['owners'] = self._deduplicate_owners(results['owners'])
        results['emails'] = list(dict.fromkeys(results['emails']))[:5]  # Top 5

        return results

    def _deduplicate_owners(self, owners: List[Dict]) -> List[Dict]:
        """Remove duplicate owner names"""
        seen = set()
        unique = []
        for owner in owners:
            name_lower = owner['name'].lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique.append(owner)
        return unique[:3]  # Top 3 candidates

    def detect_succession_signals(self, text: str, years_in_business: float) -> Dict:
        """Detect signals that owner may be ready to sell"""
        signals = {
            'age_related': False,
            'retirement_mentioned': False,
            'long_tenure': years_in_business >= 20,
            'second_generation': False,
            'score': 0
        }

        text_lower = text.lower()

        # Age-related keywords
        age_keywords = ['retirement', 'retiring', 'succession', 'next generation', 'legacy']
        for keyword in age_keywords:
            if keyword in text_lower:
                signals['retirement_mentioned'] = True
                signals['score'] += 20
                break

        # Second generation mentions
        if any(word in text_lower for word in ['family-owned', 'second generation', 'third generation']):
            signals['second_generation'] = True
            signals['score'] += 15

        # Long tenure bonus
        if signals['long_tenure']:
            signals['score'] += 25

        return signals

    async def enrich_lead(self, business_name: str, website: str, years_in_business: float) -> Dict:
        """Main enrichment function"""
        print(f"\n{'='*80}")
        print(f"ENRICHING: {business_name}")
        print(f"{'='*80}")
        print(f"Website: {website}")
        print(f"Years in Business: {years_in_business:.1f}")

        enrichment = {
            'business_name': business_name,
            'website': website,
            'years_in_business': years_in_business,
            'owner_candidates': [],
            'emails': [],
            'description': '',
            'succession_signals': {},
            'linkedin_search_query': ''
        }

        # Scrape website
        print(f"\n📄 Scraping website for owner information...")
        scrape_results = await self.scrape_about_page(website)

        enrichment['owner_candidates'] = scrape_results['owners']
        enrichment['emails'] = scrape_results['emails']
        enrichment['description'] = scrape_results['description']

        # Detect succession signals
        full_text = scrape_results['description']
        enrichment['succession_signals'] = self.detect_succession_signals(
            full_text,
            years_in_business
        )

        # Generate LinkedIn search query
        if enrichment['owner_candidates']:
            top_candidate = enrichment['owner_candidates'][0]['name']
            enrichment['linkedin_search_query'] = f"{top_candidate} {business_name}"
        else:
            enrichment['linkedin_search_query'] = f"owner {business_name}"

        # Print results
        print(f"\n{'='*80}")
        print(f"ENRICHMENT RESULTS")
        print(f"{'='*80}")

        if enrichment['owner_candidates']:
            print(f"\n👤 Owner Candidates:")
            for i, owner in enumerate(enrichment['owner_candidates'], 1):
                print(f"   {i}. {owner['name']} (confidence: {owner['confidence']*100:.0f}%)")
        else:
            print(f"\n👤 Owner Candidates: None found automatically")

        if enrichment['emails']:
            print(f"\n📧 Email Addresses:")
            for i, email in enumerate(enrichment['emails'], 1):
                print(f"   {i}. {email}")
        else:
            print(f"\n📧 Email Addresses: None found")

        if enrichment['description']:
            print(f"\n📝 Description:")
            print(f"   {enrichment['description']}")

        print(f"\n🔍 LinkedIn Search Query:")
        print(f"   {enrichment['linkedin_search_query']}")
        print(f"   https://www.linkedin.com/search/results/people/?keywords={enrichment['linkedin_search_query'].replace(' ', '%20')}")

        signals = enrichment['succession_signals']
        print(f"\n🎯 Succession Readiness Score: {signals['score']}/100")
        if signals['retirement_mentioned']:
            print(f"   ✓ Retirement/succession mentioned on website")
        if signals['second_generation']:
            print(f"   ✓ Family-owned business (potential succession)")
        if signals['long_tenure']:
            print(f"   ✓ Long tenure ({years_in_business:.0f} years)")

        return enrichment

async def main():
    """Main execution"""

    # Hardcoded leads (can be parameterized later)
    leads = [
        {
            'business_name': 'Fiddes Wholesale Produce Co',
            'website': 'https://www.facebook.com/Fiddes-Wholesale-Produce-FWP-263828676991956/',
            'years_in_business': 28.6
        },
        {
            'business_name': "Traynor's Bakery Wholesale Ltd.",
            'website': 'http://www.traynors.ca',
            'years_in_business': 24.4
        }
    ]

    # Allow command-line override
    if len(sys.argv) >= 3:
        leads = [{
            'business_name': sys.argv[1],
            'website': sys.argv[2],
            'years_in_business': float(sys.argv[3]) if len(sys.argv) >= 4 else 15.0
        }]

    enriched_leads = []

    async with LeadEnricher() as enricher:
        for lead in leads:
            enrichment = await enricher.enrich_lead(
                lead['business_name'],
                lead['website'],
                lead['years_in_business']
            )
            enriched_leads.append(enrichment)

    # Save results
    output_dir = Path(__file__).parent.parent / 'data'
    output_file = output_dir / 'enriched_hot_leads.json'

    with open(output_file, 'w') as f:
        json.dump(enriched_leads, f, indent=2)

    print(f"\n{'='*80}")
    print(f"✅ Saved enrichment data to: {output_file}")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    asyncio.run(main())
