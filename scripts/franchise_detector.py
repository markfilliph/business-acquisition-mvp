#!/usr/bin/env python3
"""
Franchise/Corporate Detector
Identifies multi-location businesses and corporate chains that are NOT acquisition targets
"""
import re
import sys
import asyncio
import aiohttp
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

class FranchiseDetector:
    """Detects franchises and multi-location businesses"""

    # URL patterns indicating multi-location business
    MULTI_LOCATION_PATTERNS = [
        r'/locations?/',
        r'/find-?(?:a-?)?(?:store|location|us)/',
        r'/stores?/',
        r'/branches?/',
        r'/our-?locations?/',
        r'/where-?to-?(?:find|buy)/',
        r'/dealers?/',
        r'/distributors?/',
    ]

    # Keywords in website content suggesting franchise/chain
    FRANCHISE_KEYWORDS = [
        'franchise opportunities',
        'become a franchisee',
        'franchise information',
        'multiple locations',
        'locations across',
        'national chain',
        'nationwide',
        'corporate headquarters',
        'head office',
        'franchising',
    ]

    # Corporate indicators in business name
    CORPORATE_NAME_PATTERNS = [
        r'\b(?:inc\.?|incorporated)\b',
        r'\b(?:ltd\.?|limited)\b',
        r'\b(?:llc|l\.l\.c\.)\b',
        r'\bcorp\.?(?:oration)?\b',
        r'\bgroup\b',
        r'\benterprises?\b',
        r'\binternational\b',
        r'\bcanada\b.*\b(?:inc|ltd|corp)\b',
    ]

    # Phone number patterns (1-800 suggests national operations)
    NATIONAL_PHONE_PATTERN = r'1-?800-?\d{3}-?\d{4}'

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
                return None
        except Exception:
            return None

    def check_url_pattern(self, url: str) -> Dict:
        """Check if URL suggests multi-location business"""
        if pd.isna(url) or url == '':
            return {'is_franchise': False, 'confidence': 0, 'reasons': []}

        url_lower = url.lower()
        reasons = []

        for pattern in self.MULTI_LOCATION_PATTERNS:
            if re.search(pattern, url_lower):
                reasons.append(f"URL contains '{pattern}'")

        if reasons:
            return {
                'is_franchise': True,
                'confidence': 0.7,
                'reasons': reasons
            }

        return {'is_franchise': False, 'confidence': 0, 'reasons': []}

    def check_business_name(self, name: str) -> Dict:
        """Check if business name suggests corporate/chain"""
        if pd.isna(name) or name == '':
            return {'is_franchise': False, 'confidence': 0, 'reasons': []}

        name_lower = name.lower()
        reasons = []

        for pattern in self.CORPORATE_NAME_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                reasons.append(f"Corporate name pattern: '{pattern}'")

        # Multiple words that are all capitalized = likely corporate
        words = name.split()
        if len(words) >= 3 and all(w[0].isupper() for w in words if len(w) > 2):
            reasons.append("Formal corporate naming convention")

        if reasons:
            # Lower confidence for name alone
            return {
                'is_franchise': True,
                'confidence': 0.4,
                'reasons': reasons
            }

        return {'is_franchise': False, 'confidence': 0, 'reasons': []}

    def check_phone_number(self, phone: str) -> Dict:
        """Check if phone number suggests national operations"""
        if pd.isna(phone) or phone == '':
            return {'is_franchise': False, 'confidence': 0, 'reasons': []}

        if re.search(self.NATIONAL_PHONE_PATTERN, phone):
            return {
                'is_franchise': True,
                'confidence': 0.6,
                'reasons': ['1-800 number suggests national operations']
            }

        return {'is_franchise': False, 'confidence': 0, 'reasons': []}

    async def scrape_website(self, url: str) -> Dict:
        """Scrape website for franchise indicators"""
        if pd.isna(url) or url == '':
            return {'is_franchise': False, 'confidence': 0, 'reasons': []}

        reasons = []

        # Fetch homepage
        html = await self.fetch_page(url)
        if not html:
            return {'is_franchise': False, 'confidence': 0, 'reasons': ['Could not fetch website']}

        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator=' ', strip=True).lower()

        # Check for franchise keywords
        for keyword in self.FRANCHISE_KEYWORDS:
            if keyword in text:
                reasons.append(f"Found keyword: '{keyword}'")

        # Check for "locations" link in navigation
        locations_links = soup.find_all('a', href=re.compile(r'/locations?|/stores?|/find-?us', re.I))
        if locations_links:
            reasons.append(f"Found {len(locations_links)} 'locations' navigation links")

        # Check for multiple addresses on homepage
        address_pattern = r'\d+\s+\w+\s+(?:street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd)'
        addresses = re.findall(address_pattern, text, re.IGNORECASE)
        if len(addresses) > 2:
            reasons.append(f"Found {len(addresses)} different addresses on homepage")

        if reasons:
            # High confidence if multiple indicators
            confidence = min(0.95, 0.5 + (len(reasons) * 0.15))
            return {
                'is_franchise': True,
                'confidence': confidence,
                'reasons': reasons
            }

        return {'is_franchise': False, 'confidence': 0, 'reasons': []}

    async def detect(self, business_name: str, website: str, phone: str = '') -> Dict:
        """Main detection function - combines all checks"""

        # Run all checks
        url_check = self.check_url_pattern(website)
        name_check = self.check_business_name(business_name)
        phone_check = self.check_phone_number(phone)
        web_scrape = await self.scrape_website(website)

        # Combine results
        all_reasons = []
        all_reasons.extend(url_check['reasons'])
        all_reasons.extend(name_check['reasons'])
        all_reasons.extend(phone_check['reasons'])
        all_reasons.extend(web_scrape['reasons'])

        # Calculate overall confidence
        confidences = [
            url_check['confidence'],
            name_check['confidence'],
            phone_check['confidence'],
            web_scrape['confidence']
        ]

        # Weight web scraping higher
        if web_scrape['confidence'] > 0:
            max_confidence = web_scrape['confidence']
        elif url_check['confidence'] > 0:
            max_confidence = url_check['confidence']
        else:
            max_confidence = max(confidences)

        # Boost confidence if multiple checks agree
        positive_checks = sum(1 for c in confidences if c > 0)
        if positive_checks >= 2:
            max_confidence = min(0.95, max_confidence + 0.2)

        is_franchise = max_confidence >= 0.5

        return {
            'business_name': business_name,
            'website': website,
            'is_franchise': is_franchise,
            'confidence': round(max_confidence, 2),
            'reason_count': len(all_reasons),
            'reasons': all_reasons,
            'verdict': 'REJECT' if is_franchise else 'ACCEPT'
        }


async def process_batch(input_file: Path):
    """Process a batch of businesses from CSV"""

    print(f"\n{'='*80}")
    print(f"FRANCHISE DETECTOR - BATCH MODE")
    print(f"{'='*80}")
    print(f"Input: {input_file.name}\n")

    # Read CSV
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} businesses")

    # Determine column names
    name_col = next((col for col in df.columns if 'name' in col.lower()), 'Business Name')
    website_col = next((col for col in df.columns if 'website' in col.lower() or 'url' in col.lower()), 'Website')
    phone_col = next((col for col in df.columns if 'phone' in col.lower()), 'Phone')

    if name_col not in df.columns:
        print(f"ERROR: Could not find business name column")
        return

    if website_col not in df.columns:
        print(f"WARNING: No website column found, using empty strings")
        df[website_col] = ''

    if phone_col not in df.columns:
        print(f"WARNING: No phone column found, using empty strings")
        df[phone_col] = ''

    print(f"Processing {len(df)} businesses...\n")

    results = []
    async with FranchiseDetector() as detector:
        for idx, row in df.iterrows():
            business_name = row.get(name_col, '')
            website = row.get(website_col, '')
            phone = row.get(phone_col, '')

            print(f"[{idx+1}/{len(df)}] Checking: {business_name}...", end=' ')

            result = await detector.detect(business_name, website, phone)
            results.append(result)

            if result['is_franchise']:
                print(f"❌ FRANCHISE (confidence: {result['confidence']*100:.0f}%)")
            else:
                print(f"✅ OK")

    # Print summary
    franchises = [r for r in results if r['is_franchise']]
    clean = [r for r in results if not r['is_franchise']]

    print(f"\n{'='*80}")
    print(f"DETECTION RESULTS")
    print(f"{'='*80}\n")
    print(f"✅ SINGLE-LOCATION: {len(clean)} ({len(clean)/len(results)*100:.1f}%)")
    print(f"❌ FRANCHISE/CHAIN: {len(franchises)} ({len(franchises)/len(results)*100:.1f}%)")

    if franchises:
        print(f"\n{'='*80}")
        print(f"DETECTED FRANCHISES/CHAINS")
        print(f"{'='*80}\n")

        for result in franchises:
            print(f"❌ {result['business_name']}")
            print(f"   Website: {result['website']}")
            print(f"   Confidence: {result['confidence']*100:.0f}%")
            print(f"   Reasons:")
            for reason in result['reasons'][:3]:  # Show top 3
                print(f"      • {reason}")
            print()

    # Save results
    output_dir = input_file.parent
    output_file = output_dir / f"FRANCHISE_DETECTION_{input_file.stem}.csv"

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_file, index=False)

    print(f"{'='*80}")
    print(f"✅ Saved results to: {output_file}")
    print(f"{'='*80}\n")

    return results


async def main():
    """Main execution"""

    if len(sys.argv) < 2:
        print("Usage: python franchise_detector.py <input.csv>")
        print("   or: python franchise_detector.py --url <url> --name <name>")
        return

    # Single business mode
    if '--url' in sys.argv:
        url_idx = sys.argv.index('--url')
        name_idx = sys.argv.index('--name') if '--name' in sys.argv else None

        url = sys.argv[url_idx + 1]
        name = sys.argv[name_idx + 1] if name_idx else 'Unknown Business'
        phone = ''

        async with FranchiseDetector() as detector:
            result = await detector.detect(name, url, phone)

            print(f"\n{'='*80}")
            print(f"FRANCHISE DETECTION - SINGLE BUSINESS")
            print(f"{'='*80}\n")
            print(f"Business: {result['business_name']}")
            print(f"Website: {result['website']}")
            print(f"Verdict: {result['verdict']}")
            print(f"Confidence: {result['confidence']*100:.0f}%")
            print(f"\nReasons:")
            for reason in result['reasons']:
                print(f"  • {reason}")
            print()

        return

    # Batch mode
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"ERROR: File not found: {input_file}")
        return

    await process_batch(input_file)


if __name__ == '__main__':
    asyncio.run(main())
