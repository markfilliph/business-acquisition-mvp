"""
Smart Enrichment Strategy - Combine Multiple Sources

Uses a waterfall strategy to enrich employee count:
1. Website scraping (if found)
2. Industry-based intelligent estimation with ranges
3. Manual lookup for high-priority businesses

Provides confidence scores for each data point.
"""
import asyncio
import aiosqlite
from typing import Optional, Dict
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class SmartEnricher:
    """
    Intelligent enrichment using multiple strategies and confidence scoring.
    """

    def __init__(self):
        self.logger = logger

        # Industry-based employee range estimates (based on real data)
        self.industry_employee_ranges = {
            'manufacturing': {
                'small': (10, 30),  # Small manufacturers
                'typical': (15, 50),  # Typical range
                'confidence': 0.40
            },
            'wholesale': {
                'small': (5, 20),
                'typical': (10, 40),
                'confidence': 0.35
            },
            'consulting': {
                'small': (3, 15),
                'typical': (5, 25),
                'confidence': 0.45
            },
            'professional_services': {
                'small': (5, 20),
                'typical': (8, 30),
                'confidence': 0.40
            },
            'general_business': {
                'small': (5, 25),
                'typical': (10, 40),
                'confidence': 0.30
            }
        }

    def estimate_employees_from_industry(self, industry: str, city: str = None) -> Dict:
        """
        Provide employee range estimate based on industry.

        Args:
            industry: Industry classification
            city: City (Hamilton businesses tend to be smaller)

        Returns:
            Dict with employee_range_min, employee_range_max, confidence
        """
        industry = industry.lower() if industry else 'general_business'

        # Map to known categories
        for category in self.industry_employee_ranges:
            if category in industry:
                range_data = self.industry_employee_ranges[category]

                # Hamilton businesses: use 'small' range
                if city and 'hamilton' in city.lower():
                    min_emp, max_emp = range_data['small']
                else:
                    min_emp, max_emp = range_data['typical']

                return {
                    'employee_range_min': min_emp,
                    'employee_range_max': max_emp,
                    'employee_range': f"{min_emp}-{max_emp}",
                    'confidence': range_data['confidence'],
                    'source': 'industry_estimate'
                }

        # Default fallback
        return {
            'employee_range_min': 5,
            'employee_range_max': 30,
            'employee_range': "5-30",
            'confidence': 0.25,
            'source': 'default_estimate'
        }

    def estimate_revenue_from_employees(self, employee_min: int, employee_max: int, industry: str) -> Dict:
        """
        Estimate revenue based on employee count and industry.

        B2B Services: $100K-$200K per employee
        Manufacturing: $150K-$300K per employee
        Wholesale: $200K-$400K per employee
        """
        industry = industry.lower() if industry else ''

        # Revenue per employee by industry
        if 'manufacturing' in industry:
            revenue_per_emp_min = 150_000
            revenue_per_emp_max = 300_000
        elif 'wholesale' in industry or 'distribution' in industry:
            revenue_per_emp_min = 200_000
            revenue_per_emp_max = 400_000
        else:  # Services/general
            revenue_per_emp_min = 100_000
            revenue_per_emp_max = 200_000

        # Calculate ranges
        revenue_min = employee_min * revenue_per_emp_min
        revenue_max = employee_max * revenue_per_emp_max

        # Format as readable ranges
        def format_revenue(amount):
            if amount >= 1_000_000:
                return f"${amount / 1_000_000:.1f}M"
            else:
                return f"${amount / 1_000:.0f}K"

        return {
            'revenue_min': revenue_min,
            'revenue_max': revenue_max,
            'revenue_range': f"{format_revenue(revenue_min)}-{format_revenue(revenue_max)}",
            'confidence': 0.35,
            'source': 'employee_based_estimate'
        }

    async def enrich_from_csv(
        self,
        csv_input_path: str,
        csv_output_path: str,
        scraped_csv_path: Optional[str] = None
    ):
        """
        Enrich businesses from CSV with smart estimation.

        Args:
            csv_input_path: Original Google Places CSV
            csv_output_path: Output CSV with enrichment
            scraped_csv_path: CSV with website-scraped data (if available)
        """
        import csv

        # Load original data
        with open(csv_input_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            businesses = list(reader)

        # Load scraped data if available
        scraped_data = {}
        if scraped_csv_path:
            try:
                with open(scraped_csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get('Business Name', '')
                        scraped_data[name] = row
            except:
                self.logger.warning("scraped_csv_not_found", path=scraped_csv_path)

        enriched = []

        for biz in businesses:
            name = biz.get('Business Name', '')
            industry = biz.get('Industry', '')
            city = biz.get('City', '')

            # Check if we have scraped data
            scraped = scraped_data.get(name, {})

            # Priority 1: Website-scraped employee data
            if scraped.get('Employee Range (Scraped)') and not scraped['Employee Range (Scraped)'].startswith('UNKNOWN'):
                employee_range = scraped['Employee Range (Scraped)']
                parts = employee_range.split('-')
                if len(parts) == 2:
                    employee_min = int(parts[0])
                    employee_max = int(parts[1])
                    biz['Employee Range'] = employee_range
                    biz['Employee Count Source'] = 'website_scrape'
                    biz['Employee Confidence'] = '75%'
                else:
                    # Use industry estimate
                    estimate = self.estimate_employees_from_industry(industry, city)
                    employee_min = estimate['employee_range_min']
                    employee_max = estimate['employee_range_max']
                    biz['Employee Range'] = estimate['employee_range']
                    biz['Employee Count Source'] = estimate['source']
                    biz['Employee Confidence'] = f"{int(estimate['confidence'] * 100)}%"
            else:
                # Priority 2: Industry-based estimate
                estimate = self.estimate_employees_from_industry(industry, city)
                employee_min = estimate['employee_range_min']
                employee_max = estimate['employee_range_max']
                biz['Employee Range'] = estimate['employee_range']
                biz['Employee Count Source'] = estimate['source']
                biz['Employee Confidence'] = f"{int(estimate['confidence'] * 100)}%"

            # Revenue estimation
            revenue = self.estimate_revenue_from_employees(employee_min, employee_max, industry)
            biz['Revenue Range'] = revenue['revenue_range']
            biz['Revenue Source'] = revenue['source']
            biz['Revenue Confidence'] = f"{int(revenue['confidence'] * 100)}%"

            # Years in business
            if scraped.get('Year Founded (Scraped)') and scraped['Year Founded (Scraped)'].isdigit():
                year_founded = int(scraped['Year Founded (Scraped)'])
                years_in_business = datetime.now().year - year_founded
                biz['Years in Business'] = years_in_business
                biz['Founded Year'] = year_founded
                biz['Age Source'] = 'website_scrape'
                biz['Age Confidence'] = '80%'
            else:
                # Estimate: Hamilton businesses average 20 years
                biz['Years in Business'] = 'UNKNOWN - needs WHOIS/domain age lookup'
                biz['Founded Year'] = 'UNKNOWN'
                biz['Age Source'] = 'unknown'
                biz['Age Confidence'] = '0%'

            enriched.append(biz)

        # Write output
        if enriched:
            fieldnames = list(enriched[0].keys())
            with open(csv_output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(enriched)

            self.logger.info(
                "smart_enrichment_complete",
                output_path=csv_output_path,
                total=len(enriched)
            )

            # Print summary
            print("\n=== SMART ENRICHMENT SUMMARY ===")
            print(f"Total businesses: {len(enriched)}")

            # Count by source
            sources = {}
            for biz in enriched:
                source = biz.get('Employee Count Source', 'unknown')
                sources[source] = sources.get(source, 0) + 1

            print("\nEmployee Count Sources:")
            for source, count in sources.items():
                print(f"  {source}: {count}")


async def enrich_google_places():
    """Enrich Google Places leads with smart estimation."""
    enricher = SmartEnricher()
    await enricher.enrich_from_csv(
        csv_input_path='data/google_places_leads_20251016_194208.csv',
        csv_output_path='data/google_places_SMARTLY_ENRICHED.csv',
        scraped_csv_path='data/google_places_leads_enriched_20251016_214122.csv'
    )


if __name__ == '__main__':
    asyncio.run(enrich_google_places())
