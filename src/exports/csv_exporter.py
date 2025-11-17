#!/usr/bin/env python3
"""
CSV export functionality with STANDARDIZED output format.

This module enforces the StandardLeadOutput schema for ALL exports.
"""
import csv
from datetime import datetime
from collections import defaultdict
from typing import List
import aiosqlite

from ..core.output_schema import (
    STANDARD_CSV_HEADERS,
    StandardLeadOutput,
    calculate_employee_range,
    calculate_sde_from_revenue,
    format_currency_cad
)


class CSVExporter:
    """Export leads to CSV with STANDARDIZED format - fields never change."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_business_details(self, cursor, business_id: int) -> dict:
        """Get validation details and observations for a business."""
        # Get exclusion reasons
        await cursor.execute(
            "SELECT rule_id, reason FROM exclusions WHERE business_id = ? ORDER BY excluded_at",
            (business_id,)
        )
        exclusions = await cursor.fetchall()

        # Get observations
        await cursor.execute(
            "SELECT field, value FROM observations WHERE business_id = ?",
            (business_id,)
        )
        observations = await cursor.fetchall()

        obs_dict = defaultdict(list)
        for row in observations:
            obs_dict[row[0]].append(row[1])

        return {
            'exclusions': exclusions,
            'industry': obs_dict.get('industry', [''])[0],
            'emails': obs_dict.get('email', []),
            'phones': obs_dict.get('phone', [])
        }

    async def export(self, output_path: str, status_filter: str = None) -> dict:
        """
        Export businesses to CSV using STANDARDIZED format.

        This method ALWAYS produces the same output format regardless of
        which pipeline generated the leads.

        Args:
            output_path: Path to output CSV file
            status_filter: Optional status filter (e.g., 'QUALIFIED')

        Returns:
            dict with export statistics
        """
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row

        try:
            # Get all businesses (optionally filtered by status)
            if status_filter:
                cursor = await db.execute("""
                    SELECT * FROM businesses
                    WHERE status = ?
                    ORDER BY original_name
                """, (status_filter,))
            else:
                cursor = await db.execute("""
                    SELECT * FROM businesses
                    ORDER BY status, original_name
                """)

            businesses = await cursor.fetchall()

            # Write CSV using STANDARDIZED headers (NEVER change these)
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=STANDARD_CSV_HEADERS)
                writer.writeheader()

                for biz in businesses:
                    details = await self.get_business_details(cursor, biz['id'])

                    # Calculate revenue from employee count
                    revenue = 0
                    if biz['employee_count']:
                        # Use industry-specific revenue per employee or default $75K
                        revenue_per_employee = 75_000
                        revenue = biz['employee_count'] * revenue_per_employee

                    # Calculate employee range
                    employee_range = calculate_employee_range(
                        employee_count=biz['employee_count'],
                        industry=details['industry'],
                        revenue=revenue
                    )

                    # Calculate SDE and format revenue
                    if revenue > 0:
                        sde_amount, sde_formatted = calculate_sde_from_revenue(
                            revenue=revenue,
                            employee_count=biz['employee_count'],
                            industry=details['industry']
                        )
                        revenue_formatted = format_currency_cad(revenue)
                    else:
                        sde_formatted = "Unknown"
                        revenue_formatted = "Unknown"

                    # Format full address
                    full_address = biz['street'] or "Unknown"

                    # Calculate confidence score (based on data completeness)
                    has_data = [
                        biz['phone'],
                        biz['website'],
                        biz['street'],
                        biz['postal_code'],
                        biz['employee_count'],
                        details['industry']
                    ]
                    confidence = sum(1 for x in has_data if x) / len(has_data)
                    confidence_formatted = f"{confidence:.0%}"

                    # Get data sources (simplified from observations)
                    # For now, default to "Google Business" - can be enhanced later
                    data_sources = "Google Business, Web Scraping"

                    # Create standardized output using LOCKED schema
                    standard_output = StandardLeadOutput(
                        business_name=biz['original_name'],
                        address=full_address,
                        city=biz['city'] or "Hamilton",
                        province="ON",
                        postal_code=biz['postal_code'] or "Unknown",
                        phone_number=biz['phone'] or "Unknown",
                        website=biz['website'] or "Unknown",
                        industry=details['industry'] or "Unknown",
                        estimated_employees_range=employee_range,
                        estimated_sde_cad=sde_formatted,
                        estimated_revenue_cad=revenue_formatted,
                        confidence_score=confidence_formatted,
                        status=biz['status'],
                        data_sources=data_sources
                    )

                    writer.writerow(standard_output.to_dict())

            # Calculate statistics
            status_counts = defaultdict(int)
            for biz in businesses:
                status_counts[biz['status']] += 1

            return {
                'total': len(businesses),
                'qualified': status_counts.get('QUALIFIED', 0),
                'excluded': status_counts.get('EXCLUDED', 0),
                'review_required': status_counts.get('REVIEW_REQUIRED', 0),
                'output_path': output_path
            }

        finally:
            await db.close()
