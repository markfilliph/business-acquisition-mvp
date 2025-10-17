"""
Domain Age Checker - Get website age via WHOIS

Fetches domain registration date to determine years in business.
Uses python-whois library for WHOIS lookups.
"""
import asyncio
import whois
from datetime import datetime
from typing import Optional, Dict
import structlog
from urllib.parse import urlparse

logger = structlog.get_logger(__name__)


class DomainAgeChecker:
    """
    Check domain age using WHOIS lookups.
    """

    def __init__(self):
        self.logger = logger

    def extract_domain(self, url: str) -> Optional[str]:
        """Extract clean domain from URL."""
        try:
            if not url or 'UNKNOWN' in url:
                return None

            # Add https if missing
            if not url.startswith('http'):
                url = f"https://{url}"

            parsed = urlparse(url)
            domain = parsed.netloc

            # Remove www.
            if domain.startswith('www.'):
                domain = domain[4:]

            return domain if domain else None
        except:
            return None

    async def get_domain_age(self, website: str) -> Optional[Dict]:
        """
        Get domain age from WHOIS.

        Args:
            website: Website URL

        Returns:
            Dict with creation_date, years_old, confidence
        """
        try:
            domain = self.extract_domain(website)
            if not domain:
                return None

            # WHOIS lookup (blocking, run in executor)
            loop = asyncio.get_event_loop()
            whois_data = await loop.run_in_executor(None, whois.whois, domain)

            if not whois_data:
                return None

            # Extract creation date
            creation_date = whois_data.creation_date

            if not creation_date:
                return None

            # Handle list of dates (sometimes WHOIS returns multiple)
            if isinstance(creation_date, list):
                creation_date = creation_date[0]

            # Calculate years (handle timezone-aware dates)
            if isinstance(creation_date, datetime):
                # Remove timezone info for comparison
                if creation_date.tzinfo:
                    creation_date = creation_date.replace(tzinfo=None)
                years_old = (datetime.now() - creation_date).days / 365.25

                self.logger.info(
                    "domain_age_found",
                    domain=domain,
                    creation_date=creation_date.isoformat(),
                    years_old=round(years_old, 1)
                )

                return {
                    'creation_date': creation_date.isoformat(),
                    'years_old': round(years_old, 1),
                    'year_founded': creation_date.year,
                    'confidence': 0.85,  # WHOIS is reliable
                    'source': 'whois'
                }

            return None

        except Exception as e:
            self.logger.debug("domain_age_lookup_failed", website=website, error=str(e)[:100])
            return None

    async def enrich_csv_with_domain_age(self, input_csv: str, output_csv: str):
        """
        Add domain age to CSV file.

        Args:
            input_csv: Input CSV path
            output_csv: Output CSV path with domain age
        """
        import csv

        with open(input_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        enriched = []

        for i, row in enumerate(rows, 1):
            website = row.get('Website', '')
            business_name = row.get('Business Name', '')

            self.logger.info(
                "checking_domain_age",
                index=i,
                total=len(rows),
                business=business_name,
                website=website
            )

            # Get domain age
            age_data = await self.get_domain_age(website)

            if age_data:
                row['Years in Business'] = age_data['years_old']
                row['Founded Year'] = age_data['year_founded']
                row['Age Source'] = age_data['source']
                row['Age Confidence'] = f"{int(age_data['confidence'] * 100)}%"
            elif 'Years in Business' not in row or row.get('Years in Business', '').startswith('UNKNOWN'):
                # Keep existing values or mark as UNKNOWN
                if 'Years in Business' not in row:
                    row['Years in Business'] = 'UNKNOWN - WHOIS failed'
                    row['Founded Year'] = 'UNKNOWN'
                    row['Age Source'] = 'whois_failed'
                    row['Age Confidence'] = '0%'

            enriched.append(row)

            # Rate limiting
            await asyncio.sleep(0.5)

        # Write output
        if enriched:
            fieldnames = list(enriched[0].keys())
            with open(output_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(enriched)

            self.logger.info("domain_age_enrichment_complete", output=output_csv, total=len(enriched))

            # Summary
            print("\n=== DOMAIN AGE SUMMARY ===")
            successful = sum(1 for r in enriched if isinstance(r.get('Years in Business'), (int, float)) or (isinstance(r.get('Years in Business'), str) and r.get('Years in Business').replace('.', '').isdigit()))
            print(f"Successfully enriched: {successful}/{len(enriched)}")
            print(f"Failed/Unknown: {len(enriched) - successful}/{len(enriched)}")


async def add_domain_age():
    """Add domain age to smartly enriched CSV."""
    checker = DomainAgeChecker()
    await checker.enrich_csv_with_domain_age(
        input_csv='data/google_places_SMARTLY_ENRICHED.csv',
        output_csv='data/google_places_FULLY_ENRICHED.csv'
    )


if __name__ == '__main__':
    asyncio.run(add_domain_age())
