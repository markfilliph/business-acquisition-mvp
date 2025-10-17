"""
Website Scraper Enrichment - Extract Employee Count from Company Websites

Scrapes company websites (About Us, Team pages) to extract:
- Employee count or ranges
- Years in business / founded year
- Revenue indicators

FREE - no API required, just web scraping.
"""
import asyncio
import re
from typing import Optional, Dict, Tuple
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


class WebsiteScraperEnricher:
    """
    Extract employee count and firmographic data from company websites.

    Strategy:
    1. Fetch website homepage
    2. Find About Us / Team / Company pages
    3. Extract employee count patterns
    4. Extract year founded patterns
    5. Calculate years in business
    """

    def __init__(self):
        self.logger = logger
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page HTML with timeout and error handling."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        self.logger.debug("page_fetch_failed", url=url, status=response.status)
                        return None
        except Exception as e:
            self.logger.debug("page_fetch_error", url=url, error=str(e)[:100])
            return None

    def extract_employee_count(self, text: str) -> Optional[Dict]:
        """
        Extract employee count or range from text.

        Patterns:
        - "50 employees" → 50
        - "team of 25" → 25
        - "10-30 employees" → range 10-30
        - "over 100 staff" → >100
        """
        patterns = [
            # Exact count
            r'(?:we have|team of|company of|staff of|with)\s+([\d,]+)\s+(?:employees|staff|people|team members)',
            r'([\d,]+)\s+(?:employees|staff|people|team members)',
            # Range
            r'([\d,]+)\s*(?:-|to)\s*([\d,]+)\s+(?:employees|staff|people)',
            # "Over X" pattern
            r'(?:over|more than)\s+([\d,]+)\s+(?:employees|staff|people)',
            # Company size
            r'company size[:\s]*([\d,]+)\s*(?:-\s*([\d,]+))?',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if match.group(2):  # Range match
                        min_emp = int(match.group(1).replace(',', ''))
                        max_emp = int(match.group(2).replace(',', ''))
                        return {
                            'employee_range': f"{min_emp}-{max_emp}",
                            'employee_min': min_emp,
                            'employee_max': max_emp,
                            'confidence': 0.75
                        }
                    else:  # Exact count
                        count = int(match.group(1).replace(',', ''))
                        # Sanity check: 1-10000 employees
                        if 1 <= count <= 10000:
                            return {
                                'employee_count': count,
                                'confidence': 0.80
                            }
                except:
                    continue

        return None

    def extract_year_founded(self, text: str) -> Optional[int]:
        """
        Extract year founded from text.

        Patterns:
        - "Founded in 1995"
        - "Established 2005"
        - "Since 1980"
        - "Est. 1999"
        """
        patterns = [
            r'(?:founded|established|est\.|since)[:\s]*(\d{4})',
            r'serving (?:customers|clients) since (\d{4})',
            r'in business since (\d{4})',
            r'©\s*(\d{4})',  # Copyright year (less reliable)
        ]

        current_year = datetime.now().year
        found_years = []

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    year = int(match.group(1))
                    # Sanity check: 1900-current year
                    if 1900 <= year <= current_year:
                        found_years.append(year)
                except:
                    continue

        if found_years:
            # Return earliest year (most likely the founding year)
            return min(found_years)

        return None

    async def find_about_pages(self, base_url: str, homepage_html: str) -> list:
        """
        Find About Us, Team, Company Info pages.

        Args:
            base_url: Website base URL
            homepage_html: Homepage HTML content

        Returns:
            List of candidate URLs to scrape
        """
        soup = BeautifulSoup(homepage_html, 'html.parser')
        candidate_urls = []

        # Common About page patterns
        about_keywords = [
            'about', 'about-us', 'about_us', 'aboutus',
            'company', 'our-company', 'our-story',
            'team', 'our-team', 'meet-the-team',
            'who-we-are', 'contact', 'contact-us'
        ]

        # Find links matching about patterns
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            link_text = link.get_text().lower().strip()

            # Check if link or text matches about keywords
            if any(keyword in href for keyword in about_keywords) or \
               any(keyword in link_text for keyword in ['about', 'team', 'company', 'our story']):
                # Build full URL
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = base_url.rstrip('/') + href
                else:
                    full_url = base_url.rstrip('/') + '/' + href

                if full_url not in candidate_urls:
                    candidate_urls.append(full_url)

        # Limit to top 5 most relevant pages
        return candidate_urls[:5]

    async def scrape_website(self, website: str) -> Optional[Dict]:
        """
        Scrape website for employee count and founding year.

        Args:
            website: Company website URL

        Returns:
            Dict with employee_count/range, year_founded, years_in_business
        """
        try:
            # Normalize URL
            if not website.startswith('http'):
                website = f"https://{website}"

            # Fetch homepage
            homepage_html = await self.fetch_page(website)
            if not homepage_html:
                return None

            # Extract from homepage first
            result = {
                'employee_count': None,
                'employee_range': None,
                'year_founded': None,
                'years_in_business': None,
                'source': 'website_scrape'
            }

            # Try homepage
            employee_data = self.extract_employee_count(homepage_html)
            if employee_data:
                result.update(employee_data)

            year_founded = self.extract_year_founded(homepage_html)
            if year_founded:
                result['year_founded'] = year_founded
                result['years_in_business'] = datetime.now().year - year_founded

            # If employee count not found, try About pages
            if not result.get('employee_count') and not result.get('employee_range'):
                about_pages = await self.find_about_pages(website, homepage_html)

                for about_url in about_pages:
                    about_html = await self.fetch_page(about_url)
                    if about_html:
                        employee_data = self.extract_employee_count(about_html)
                        if employee_data:
                            result.update(employee_data)
                            break  # Found it, stop searching

                        # Also check for year founded
                        if not result['year_founded']:
                            year_founded = self.extract_year_founded(about_html)
                            if year_founded:
                                result['year_founded'] = year_founded
                                result['years_in_business'] = datetime.now().year - year_founded

                    # Rate limit
                    await asyncio.sleep(0.5)

            self.logger.info(
                "website_scrape_complete",
                website=website,
                employee_count=result.get('employee_count'),
                employee_range=result.get('employee_range'),
                year_founded=result.get('year_founded')
            )

            return result

        except Exception as e:
            self.logger.error("website_scrape_error", website=website, error=str(e))
            return None

    async def enrich_from_csv(self, csv_path: str, output_path: str):
        """
        Enrich businesses from CSV with website-scraped data.

        Args:
            csv_path: Input CSV path with Website column
            output_path: Output CSV path with enriched data
        """
        import csv

        with open(csv_path, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            rows = list(reader)

        enriched_rows = []

        for i, row in enumerate(rows, 1):
            website = row.get('Website', '').strip()
            company_name = row.get('Business Name', '')

            # Skip if no website or marked as UNKNOWN
            if not website or 'UNKNOWN' in website:
                row['Employee Count (Scraped)'] = 'UNKNOWN - no website'
                row['Employee Range (Scraped)'] = 'UNKNOWN - no website'
                row['Year Founded (Scraped)'] = 'UNKNOWN - no website'
                row['Years in Business'] = 'UNKNOWN - no website'
                enriched_rows.append(row)
                continue

            self.logger.info(
                "enriching_business",
                index=i,
                total=len(rows),
                company=company_name,
                website=website
            )

            # Scrape website
            enrichment = await self.scrape_website(website)

            if enrichment:
                row['Employee Count (Scraped)'] = enrichment.get('employee_count') or ''
                row['Employee Range (Scraped)'] = enrichment.get('employee_range') or ''
                row['Year Founded (Scraped)'] = enrichment.get('year_founded') or ''
                row['Years in Business'] = enrichment.get('years_in_business') or ''

                # If no employee data found
                if not enrichment.get('employee_count') and not enrichment.get('employee_range'):
                    row['Employee Count (Scraped)'] = 'UNKNOWN - not found on website'
                    row['Employee Range (Scraped)'] = 'UNKNOWN - not found on website'
            else:
                row['Employee Count (Scraped)'] = 'UNKNOWN - scrape failed'
                row['Employee Range (Scraped)'] = 'UNKNOWN - scrape failed'
                row['Year Founded (Scraped)'] = 'UNKNOWN - scrape failed'
                row['Years in Business'] = 'UNKNOWN - scrape failed'

            enriched_rows.append(row)

            # Rate limiting
            await asyncio.sleep(1)

        # Write output
        if enriched_rows:
            fieldnames = list(enriched_rows[0].keys())
            with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(enriched_rows)

            self.logger.info("enrichment_complete", output_path=output_path, total=len(enriched_rows))


async def enrich_google_places_leads():
    """Enrich Google Places leads with website-scraped employee/founding data."""
    enricher = WebsiteScraperEnricher()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    await enricher.enrich_from_csv(
        csv_path='data/google_places_leads_20251016_194208.csv',
        output_path=f'data/google_places_leads_enriched_{timestamp}.csv'
    )


if __name__ == '__main__':
    asyncio.run(enrich_google_places_leads())
