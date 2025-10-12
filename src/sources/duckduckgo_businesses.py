"""
DuckDuckGo-based business discovery.
Uses free ddgs library - no API key required!
"""
import asyncio
import re
from typing import List, Dict, Any
import structlog
from ddgs import DDGS

logger = structlog.get_logger(__name__)


class DuckDuckGoBusinessSearcher:
    """
    Search for businesses using DuckDuckGo.

    Free, no API key required. Uses the duckduckgo-search library.
    """

    def __init__(self):
        self.ddgs = DDGS()

    async def search_businesses(
        self,
        query: str,
        location: str = "Hamilton, Ontario",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses using DuckDuckGo.

        Args:
            query: Search term (e.g., "manufacturing company")
            location: Location to search in
            max_results: Maximum number of results

        Returns:
            List of business dictionaries
        """

        businesses = []

        # Build search query
        search_query = f"{query} {location} Canada"

        logger.info("ddg_search_started", query=search_query, max_results=max_results)

        try:
            # Use text search
            results = self.ddgs.text(
                search_query,
                max_results=max_results * 2  # Get more to filter
            )

            for result in results:
                business = self._extract_business_info(result, location)
                if business:
                    businesses.append(business)

                if len(businesses) >= max_results:
                    break

            logger.info("ddg_search_complete", businesses_found=len(businesses))

        except Exception as e:
            logger.error("ddg_search_failed", error=str(e))

        return businesses[:max_results]

    def _extract_business_info(self, result: Dict, location: str) -> Dict[str, Any]:
        """Extract business information from search result."""

        title = result.get('title', '')
        body = result.get('body', '')
        href = result.get('href', '')

        if not title or not href:
            return None

        # Skip non-business results
        skip_keywords = [
            'directory', 'list', 'database', 'wikipedia', 'reddit',
            'facebook.com/groups', 'linkedin.com/company',
            'youtube', 'twitter', 'instagram',
            'zoominfo', 'dnb.com', 'thomasnet', 'scottsdirectories',
            'yelp.com', 'indeed.com', 'glassdoor',
            'top 10', 'top 20', 'best companies',
            'search for', 'find companies'
        ]

        href_lower = href.lower()
        title_lower = title.lower()

        for keyword in skip_keywords:
            if keyword in href_lower or keyword in title_lower:
                return None

        # Extract business name from title
        # Usually format: "Business Name - City, Province" or "Business Name | Description"
        name = title.split(' - ')[0].split(' | ')[0].split('•')[0].strip()

        # Clean up name
        name = name.replace('...', '').strip()

        # Skip generic or invalid titles
        if not name or len(name) < 3:
            return None

        generic_names = [
            'home', 'about', 'contact', 'services', 'products',
            'manufacturing', 'companies', 'ontario', 'canada', 'hamilton'
        ]

        if name.lower() in generic_names:
            return None

        # Must have a real domain (not just an aggregator)
        if not any(c.isalnum() for c in name):
            return None

        business = {
            'name': name,
            'website': href,
            'description': body[:200] if body else '',
            'source_url': href
        }

        # Try to extract phone from description
        if body:
            phone_pattern = r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})'
            phone_match = re.search(phone_pattern, body)
            if phone_match:
                business['phone'] = phone_match.group(1)

            # Try to extract address from description
            # Look for patterns like "123 Main St" or "at 456 King"
            address_pattern = r'(\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd)\.?)'
            address_match = re.search(address_pattern, body)
            if address_match:
                business['street'] = address_match.group(1)

        # Set city based on location parameter
        if 'Hamilton' in location:
            business['city'] = 'Hamilton'

        return business

    async def search_hamilton_manufacturing(
        self,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Comprehensive search for Hamilton area manufacturers.

        Searches multiple terms to get diverse results.
        """

        all_businesses = []

        search_terms = [
            "manufacturing company",
            "machine shop",
            "metal fabrication",
            "industrial manufacturer",
            "wholesale distributor",
            "printing company",
            "equipment rental",
            "fabrication shop",
            "tool and die",
            "precision machining"
        ]

        for term in search_terms:
            logger.info("ddg_searching_term", term=term)

            results = await self.search_businesses(
                query=term,
                location="Hamilton, Ontario",
                max_results=max_results // len(search_terms) + 5
            )

            all_businesses.extend(results)

            # Rate limiting - be nice to DuckDuckGo
            await asyncio.sleep(2)

            if len(all_businesses) >= max_results:
                break

        # Deduplicate by website
        seen_websites = set()
        unique_businesses = []
        for biz in all_businesses:
            website = biz.get('website', '')
            if website and website not in seen_websites:
                seen_websites.add(website)
                unique_businesses.append(biz)

        logger.info("ddg_hamilton_search_complete", total_found=len(unique_businesses))

        return unique_businesses[:max_results]


async def test_ddg_search():
    """Test function."""
    searcher = DuckDuckGoBusinessSearcher()

    print("Testing DuckDuckGo search for Hamilton manufacturers...")
    print("=" * 70)

    results = await searcher.search_hamilton_manufacturing(max_results=20)

    print(f"\n✅ Found {len(results)} unique businesses\n")

    for i, biz in enumerate(results[:10], 1):
        print(f"{i}. {biz.get('name')}")
        print(f"   Website: {biz.get('website', 'N/A')}")
        print(f"   Phone: {biz.get('phone', 'N/A')}")
        print(f"   Street: {biz.get('street', 'N/A')}")
        print()


if __name__ == '__main__':
    asyncio.run(test_ddg_search())
