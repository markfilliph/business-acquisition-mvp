"""
LinkedIn Company Enrichment - Free Employee Count Scraping

Scrapes LinkedIn company pages to extract:
- Employee count (exact or range)
- Company size
- Year founded
- Industry

Uses public LinkedIn pages - no API required.
"""
import asyncio
import re
from typing import Optional, Dict
import aiohttp
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


class LinkedInEnricher:
    """
    Scrape LinkedIn company pages for employee count and firmographic data.

    Strategy:
    1. Search for company on LinkedIn via Google
    2. Extract LinkedIn company URL
    3. Scrape company page for employee count
    4. Parse structured data from page
    """

    def __init__(self):
        self.logger = logger
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    async def find_linkedin_url(self, company_name: str, website: Optional[str] = None) -> Optional[str]:
        """
        Find LinkedIn company page URL via Google search.

        Args:
            company_name: Company name
            website: Company website (helps with disambiguation)

        Returns:
            LinkedIn company URL or None
        """
        try:
            # Build search query
            query = f"{company_name} LinkedIn company"
            if website:
                # Extract domain for better matching
                domain = website.replace('https://', '').replace('http://', '').split('/')[0]
                query = f"{company_name} {domain} LinkedIn company"

            # Google search for LinkedIn URL
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        self.logger.warning("google_search_failed", status=response.status, company=company_name)
                        return None

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find LinkedIn URL in search results
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if 'linkedin.com/company/' in href:
                            # Extract clean LinkedIn URL
                            match = re.search(r'(https?://[^/]*linkedin\.com/company/[^/&?]+)', href)
                            if match:
                                linkedin_url = match.group(1)
                                self.logger.info("linkedin_url_found", company=company_name, url=linkedin_url)
                                return linkedin_url

            self.logger.warning("linkedin_url_not_found", company=company_name)
            return None

        except Exception as e:
            self.logger.error("linkedin_url_search_failed", error=str(e), company=company_name)
            return None

    async def scrape_company_page(self, linkedin_url: str) -> Optional[Dict]:
        """
        Scrape LinkedIn company page for employee count and firmographics.

        Args:
            linkedin_url: LinkedIn company page URL

        Returns:
            Dict with employee_count, year_founded, industry, etc.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(linkedin_url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status != 200:
                        self.logger.warning("linkedin_scrape_failed", status=response.status, url=linkedin_url)
                        return None

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    result = {
                        'employee_count': None,
                        'employee_range': None,
                        'year_founded': None,
                        'industry': None,
                        'source': 'linkedin_scrape'
                    }

                    # Try multiple methods to extract employee count

                    # Method 1: Look for structured data (JSON-LD)
                    scripts = soup.find_all('script', type='application/ld+json')
                    for script in scripts:
                        try:
                            import json
                            data = json.loads(script.string)
                            if 'numberOfEmployees' in data:
                                result['employee_count'] = data['numberOfEmployees']
                                break
                        except:
                            pass

                    # Method 2: Look for employee count in meta tags
                    if not result['employee_count']:
                        meta_employees = soup.find('meta', {'name': 'twitter:data1'})
                        if meta_employees and 'employees' in meta_employees.get('content', '').lower():
                            employee_text = meta_employees['content']
                            # Parse "X employees" or "X-Y employees"
                            match = re.search(r'([\d,]+)\s*(?:-\s*([\d,]+))?\s*employees', employee_text, re.IGNORECASE)
                            if match:
                                if match.group(2):  # Range
                                    result['employee_range'] = f"{match.group(1).replace(',', '')}-{match.group(2).replace(',', '')}"
                                else:  # Exact count
                                    result['employee_count'] = int(match.group(1).replace(',', ''))

                    # Method 3: Look for "About" section text
                    if not result['employee_count'] and not result['employee_range']:
                        about_section = soup.find('section', {'class': re.compile(r'.*about.*', re.I)})
                        if about_section:
                            text = about_section.get_text()
                            # Look for employee count patterns
                            patterns = [
                                r'([\d,]+)\s*(?:-\s*([\d,]+))?\s*employees',
                                r'Company size[:\s]*([\d,]+)\s*(?:-\s*([\d,]+))?',
                                r'([\d,]+)\s*(?:-\s*([\d,]+))?\s*associates'
                            ]
                            for pattern in patterns:
                                match = re.search(pattern, text, re.IGNORECASE)
                                if match:
                                    if match.group(2):
                                        result['employee_range'] = f"{match.group(1).replace(',', '')}-{match.group(2).replace(',', '')}"
                                    else:
                                        result['employee_count'] = int(match.group(1).replace(',', ''))
                                    break

                    # Extract year founded
                    founded_match = re.search(r'Founded[:\s]*(\d{4})', html, re.IGNORECASE)
                    if founded_match:
                        result['year_founded'] = int(founded_match.group(1))

                    # Extract industry
                    industry_meta = soup.find('meta', {'property': 'og:description'})
                    if industry_meta:
                        description = industry_meta.get('content', '')
                        # Industry usually mentioned in first sentence
                        if '|' in description:
                            result['industry'] = description.split('|')[0].strip()

                    self.logger.info(
                        "linkedin_scrape_complete",
                        url=linkedin_url,
                        employee_count=result['employee_count'],
                        employee_range=result['employee_range'],
                        year_founded=result['year_founded']
                    )

                    return result

        except Exception as e:
            self.logger.error("linkedin_scrape_error", error=str(e), url=linkedin_url)
            return None

    async def enrich_business(
        self,
        company_name: str,
        website: Optional[str] = None,
        existing_linkedin_url: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Enrich a business with LinkedIn data.

        Args:
            company_name: Company name
            website: Company website (helps find LinkedIn page)
            existing_linkedin_url: Known LinkedIn URL (skip search)

        Returns:
            Dict with employee_count, year_founded, industry or None
        """
        try:
            # Find LinkedIn URL if not provided
            linkedin_url = existing_linkedin_url
            if not linkedin_url:
                linkedin_url = await self.find_linkedin_url(company_name, website)

            if not linkedin_url:
                return None

            # Scrape company page
            return await self.scrape_company_page(linkedin_url)

        except Exception as e:
            self.logger.error("linkedin_enrichment_failed", error=str(e), company=company_name)
            return None

    async def enrich_from_csv(self, csv_path: str, output_path: str):
        """
        Enrich businesses from CSV file with LinkedIn data.

        Args:
            csv_path: Path to input CSV with Business Name, Website columns
            output_path: Path to output CSV with enriched data
        """
        import csv

        with open(csv_path, 'r') as infile:
            reader = csv.DictReader(infile)
            rows = list(reader)

        enriched_rows = []

        for i, row in enumerate(rows, 1):
            company_name = row.get('Business Name', '')
            website = row.get('Website', '')

            self.logger.info(f"enriching_business", index=i, total=len(rows), company=company_name)

            # Enrich with LinkedIn
            enrichment = await self.enrich_business(company_name, website)

            if enrichment:
                row['Employee Count (LinkedIn)'] = enrichment.get('employee_count') or 'UNKNOWN'
                row['Employee Range (LinkedIn)'] = enrichment.get('employee_range') or 'UNKNOWN'
                row['Year Founded (LinkedIn)'] = enrichment.get('year_founded') or 'UNKNOWN'
                row['Industry (LinkedIn)'] = enrichment.get('industry') or 'UNKNOWN'
            else:
                row['Employee Count (LinkedIn)'] = 'UNKNOWN - LinkedIn not found'
                row['Employee Range (LinkedIn)'] = 'UNKNOWN - LinkedIn not found'
                row['Year Founded (LinkedIn)'] = 'UNKNOWN - LinkedIn not found'
                row['Industry (LinkedIn)'] = 'UNKNOWN - LinkedIn not found'

            enriched_rows.append(row)

            # Rate limiting (be respectful to LinkedIn)
            await asyncio.sleep(2)

        # Write output CSV
        fieldnames = list(enriched_rows[0].keys())
        with open(output_path, 'w', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched_rows)

        self.logger.info("enrichment_complete", output_path=output_path, total=len(enriched_rows))


async def enrich_google_places_leads():
    """Enrich the Google Places leads CSV with LinkedIn data."""
    enricher = LinkedInEnricher()
    await enricher.enrich_from_csv(
        csv_path='data/google_places_leads_20251016_194208.csv',
        output_path='data/google_places_leads_enriched_linkedin.csv'
    )


if __name__ == '__main__':
    asyncio.run(enrich_google_places_leads())
