#!/usr/bin/env python3
"""CSV export functionality with all validation criteria."""
import csv
from datetime import datetime
from collections import defaultdict
from typing import List
import aiosqlite


class CSVExporter:
    """Export leads to CSV with all criteria fields."""

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

    async def export(self, output_path: str) -> dict:
        """
        Export all businesses to CSV with criteria fields.

        Returns:
            dict with statistics
        """
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row

        try:
            # Get all businesses
            cursor = await db.execute("""
                SELECT * FROM businesses
                ORDER BY status, original_name
            """)

            businesses = await cursor.fetchall()

            # CSV headers with all criteria
            fieldnames = [
                'Company Name',
                'Status',
                'Phone',
                'Website',
                'Street Address',
                'City',
                'Postal Code',
                'Industry',
                'Employee Count',
                'Revenue Estimate (Employees × $50k)',
                'Latitude',
                'Longitude',
                'Exclusion Reason',
                'Enriched Emails',
                'Enriched Phones'
            ]

            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for biz in businesses:
                    details = await self.get_business_details(cursor, biz['id'])

                    # Calculate revenue estimate from employee count
                    revenue_estimate = ''
                    if biz['employee_count']:
                        revenue_estimate = f"${biz['employee_count'] * 50_000:,}"

                    # Get exclusion reason
                    exclusion_reason = ''
                    if details['exclusions']:
                        exclusion_reason = '; '.join([f"{rule}: {reason}" for rule, reason in details['exclusions']])

                    # Format enriched contacts as semicolon-separated lists
                    enriched_emails = '; '.join(details['emails']) if details['emails'] else ''
                    enriched_phones = '; '.join(details['phones']) if details['phones'] else ''

                    writer.writerow({
                        'Company Name': biz['original_name'],
                        'Status': biz['status'],
                        'Phone': biz['phone'] or '',
                        'Website': biz['website'] or '',
                        'Street Address': biz['street'] or '',
                        'City': biz['city'] or '',
                        'Postal Code': biz['postal_code'] or '',
                        'Industry': details['industry'],
                        'Employee Count': biz['employee_count'] if biz['employee_count'] else '',
                        'Revenue Estimate (Employees × $50k)': revenue_estimate,
                        'Latitude': f"{biz['latitude']:.4f}" if biz['latitude'] else '',
                        'Longitude': f"{biz['longitude']:.4f}" if biz['longitude'] else '',
                        'Exclusion Reason': exclusion_reason,
                        'Enriched Emails': enriched_emails,
                        'Enriched Phones': enriched_phones
                    })

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
