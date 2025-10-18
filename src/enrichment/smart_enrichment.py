"""
Smart Enrichment Strategy - Combine Multiple Sources

Uses a waterfall strategy to enrich employee count:
1. Website scraping (if found)
2. Industry-based intelligent estimation with ranges
3. Manual lookup for high-priority businesses

Provides confidence scores for each data point.

UPDATED: Now uses multi-factor revenue estimation for narrower, more accurate ranges.
"""
import asyncio
import aiosqlite
from typing import Optional, Dict
from datetime import datetime
import structlog

from ..core.config import INDUSTRY_BENCHMARKS

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

    def estimate_revenue_from_employees(
        self,
        employee_min: int,
        employee_max: int,
        industry: str,
        years_in_business: Optional[int] = None,
        has_website: bool = False,
        review_count: int = 0,
        city: str = None
    ) -> Dict:
        """
        Multi-factor revenue estimation with narrower, more accurate ranges.

        NEW APPROACH:
        1. Use industry benchmarks from config for baseline revenue-per-employee
        2. Calculate midpoint employee count (not min/max range)
        3. Apply adjustment factors based on signals:
           - Years in business (maturity factor)
           - Website presence (professionalism factor)
           - Review count (market presence factor)
           - Hamilton location (regional factor)
        4. Return midpoint ± margin instead of wide min-max range

        RESULT: Ranges like "$1.2M ± 25%" instead of "$800K - $5M"

        Args:
            employee_min: Minimum employee estimate
            employee_max: Maximum employee estimate
            industry: Business industry
            years_in_business: Years operating (optional)
            has_website: Whether business has website (optional)
            review_count: Number of online reviews (optional)
            city: City location (optional)

        Returns:
            Dict with revenue_midpoint, revenue_min, revenue_max, confidence, etc.
        """
        industry = industry.lower() if industry else ''

        # Step 1: Get industry benchmark (single point, not range!)
        benchmark_data = self._get_industry_benchmark(industry)
        revenue_per_employee = benchmark_data['revenue_per_employee']
        base_confidence = benchmark_data['confidence_multiplier']

        # Step 2: Use MIDPOINT of employee range (more accurate than min-max)
        employee_midpoint = (employee_min + employee_max) / 2

        # Step 3: Calculate base revenue
        base_revenue = employee_midpoint * revenue_per_employee

        # Step 4: Apply adjustment factors
        adjustment_factor = 1.0
        confidence_boost = 0.0
        margin_percentage = 40  # Start with ±40% margin

        # Factor 1: Years in business (mature businesses are more stable)
        if years_in_business is not None:
            if years_in_business >= 20:
                adjustment_factor *= 1.15  # Established businesses earn more
                confidence_boost += 0.15
                margin_percentage -= 10  # Tighter range for mature businesses
            elif years_in_business >= 10:
                adjustment_factor *= 1.05
                confidence_boost += 0.10
                margin_percentage -= 5
            elif years_in_business < 5:
                adjustment_factor *= 0.85  # Newer businesses earn less
                margin_percentage += 5

        # Factor 2: Website presence (indicates professionalism)
        if has_website:
            adjustment_factor *= 1.10
            confidence_boost += 0.10
            margin_percentage -= 5

        # Factor 3: Review count (market presence signal)
        if review_count >= 50:
            adjustment_factor *= 1.10  # High visibility = higher revenue
            confidence_boost += 0.15
            margin_percentage -= 10
        elif review_count >= 20:
            adjustment_factor *= 1.05
            confidence_boost += 0.10
            margin_percentage -= 5
        elif review_count >= 5:
            confidence_boost += 0.05

        # Factor 4: Hamilton location (regional adjustment)
        if city and 'hamilton' in city.lower():
            adjustment_factor *= 0.95  # Slightly lower than Toronto
            confidence_boost += 0.05  # But we know the market better

        # Step 5: Calculate adjusted revenue
        adjusted_revenue = base_revenue * adjustment_factor

        # Step 6: Calculate margin (narrower for high-confidence estimates)
        margin = adjusted_revenue * (margin_percentage / 100)
        revenue_min = adjusted_revenue - margin
        revenue_max = adjusted_revenue + margin

        # Step 7: Calculate final confidence
        final_confidence = min(base_confidence + confidence_boost, 0.85)  # Cap at 85%

        # Format helper
        def format_revenue(amount):
            if amount >= 1_000_000:
                return f"${amount / 1_000_000:.1f}M"
            else:
                return f"${amount / 1_000:.0f}K"

        return {
            'revenue_midpoint': int(adjusted_revenue),
            'revenue_min': int(revenue_min),
            'revenue_max': int(revenue_max),
            'revenue_range': f"{format_revenue(revenue_min)}-{format_revenue(revenue_max)}",
            'revenue_estimate': f"{format_revenue(adjusted_revenue)} ±{margin_percentage}%",
            'confidence': round(final_confidence, 2),
            'source': 'multi_factor_estimate',
            'factors_used': {
                'industry_benchmark': revenue_per_employee,
                'employee_midpoint': employee_midpoint,
                'adjustment_factor': round(adjustment_factor, 2),
                'margin_percentage': margin_percentage,
                'years_in_business': years_in_business,
                'has_website': has_website,
                'review_count': review_count
            }
        }

    def _get_industry_benchmark(self, industry: str) -> Dict:
        """
        Get industry benchmark from config.

        Uses single-point revenue-per-employee estimates, not ranges.
        Much more accurate than the old min-max approach.
        """
        industry = industry.lower()

        # Try to match industry to benchmark
        for key, benchmark in INDUSTRY_BENCHMARKS.items():
            if key in industry:
                return benchmark

        # Default to professional services if no match
        return {
            'revenue_per_employee': 95_000,  # Average across all industries
            'confidence_multiplier': 0.45,
            'typical_margins': 0.18,
            'employee_range': (5, 20),
            'growth_rate': 0.03
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

            # Extract additional signals for revenue estimation
            years_in_business = None
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

            # Extract website and review signals
            has_website = bool(biz.get('Website') or biz.get('website'))
            review_count = int(biz.get('Review Count', biz.get('reviews', 0)))

            # Multi-factor revenue estimation (NEW!)
            revenue = self.estimate_revenue_from_employees(
                employee_min=employee_min,
                employee_max=employee_max,
                industry=industry,
                years_in_business=years_in_business,
                has_website=has_website,
                review_count=review_count,
                city=city
            )

            # Store revenue estimate with new fields
            biz['Revenue Range'] = revenue['revenue_range']
            biz['Revenue Estimate'] = revenue['revenue_estimate']  # NEW: Midpoint ±margin
            biz['Revenue Midpoint'] = revenue['revenue_midpoint']  # NEW: Single point estimate
            biz['Revenue Source'] = revenue['source']
            biz['Revenue Confidence'] = f"{int(revenue['confidence'] * 100)}%"
            biz['Revenue Margin %'] = revenue['factors_used']['margin_percentage']  # NEW: Show margin

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
