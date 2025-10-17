"""
Import Enriched CSV into Database

Imports the fully enriched Google Places CSV into the validation database.
Creates observations for all enriched fields.
"""
import asyncio
import aiosqlite
import csv
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


async def import_enriched_csv(csv_path: str, db_path: str = 'data/leads_v3.db'):
    """
    Import enriched CSV into database.

    Args:
        csv_path: Path to enriched CSV
        db_path: Path to SQLite database
    """
    db = await aiosqlite.connect(db_path)

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            businesses = list(reader)

        logger.info("import_started", csv_path=csv_path, count=len(businesses))

        imported_count = 0
        skipped_count = 0

        for biz in businesses:
            business_name = biz.get('Business Name', '').strip()
            street = biz.get('Street Address', '').strip()
            city = biz.get('City', '').strip()

            if not business_name:
                continue

            # Create fingerprint for deduplication
            fingerprint = f"{business_name.lower()}_{street.lower()}_{city.lower()}".replace(' ', '')

            # Check if exists
            cursor = await db.execute(
                "SELECT id FROM businesses WHERE fingerprint = ?",
                (fingerprint,)
            )
            existing = await cursor.fetchone()

            if existing:
                business_id = existing[0]
                logger.debug("business_exists", business_name=business_name, business_id=business_id)
                skipped_count += 1
                continue

            # Insert business
            cursor = await db.execute("""
                INSERT INTO businesses (
                    original_name, normalized_name, fingerprint,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                business_name,
                business_name.lower(),
                fingerprint,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))

            business_id = cursor.lastrowid
            imported_count += 1

            # Create observations for all fields
            observations = []
            source_url = f"google_places:{business_name}"
            confidence = float(biz.get('Confidence', '90').rstrip('%')) / 100.0

            # Basic info
            observations.append(('name', business_name, confidence, source_url))
            observations.append(('street', street, confidence, source_url))
            observations.append(('city', city, confidence, source_url))
            observations.append(('province', biz.get('Province', ''), confidence, source_url))

            if biz.get('Phone') and not biz['Phone'].startswith('UNKNOWN'):
                observations.append(('phone', biz['Phone'], confidence, source_url))

            if biz.get('Website') and not biz['Website'].startswith('UNKNOWN'):
                observations.append(('website', biz['Website'], confidence, source_url))

            if biz.get('Industry'):
                observations.append(('industry', biz['Industry'], confidence, source_url))

            # Employee data
            emp_range = biz.get('Employee Range', '')
            if emp_range and '-' in emp_range:
                parts = emp_range.split('-')
                if len(parts) == 2:
                    emp_confidence = float(biz.get('Employee Confidence', '30').rstrip('%')) / 100.0
                    emp_source_url = f"{biz.get('Employee Count Source', 'industry_estimate')}:{business_name}"
                    observations.append(('employee_range_min', parts[0], emp_confidence, emp_source_url))
                    observations.append(('employee_range_max', parts[1], emp_confidence, emp_source_url))

            # Revenue data
            revenue_range = biz.get('Revenue Range', '')
            if revenue_range and not revenue_range.startswith('UNKNOWN'):
                rev_confidence = float(biz.get('Revenue Confidence', '35').rstrip('%')) / 100.0
                rev_source_url = f"{biz.get('Revenue Source', 'employee_based_estimate')}:{business_name}"
                observations.append(('revenue_range', revenue_range, rev_confidence, rev_source_url))

            # Years in business / website age
            years_in_business = biz.get('Years in Business', '')
            if years_in_business and not years_in_business.startswith('UNKNOWN'):
                try:
                    age_confidence = float(biz.get('Age Confidence', '0').rstrip('%')) / 100.0
                    age_source_url = f"{biz.get('Age Source', 'unknown')}:{business_name}"
                    observations.append(('website_age_years', str(float(years_in_business)), age_confidence, age_source_url))

                    # Also store founded year if available
                    if biz.get('Founded Year') and biz['Founded Year'].isdigit():
                        observations.append(('year_founded', biz['Founded Year'], age_confidence, age_source_url))
                except:
                    pass

            # Insert all observations
            for field, value, conf, src_url in observations:
                await db.execute("""
                    INSERT INTO observations (
                        business_id, field, value, confidence, source_url, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    business_id,
                    field,
                    value,
                    conf,
                    src_url,
                    datetime.utcnow().isoformat()
                ))

            logger.debug(
                "business_imported",
                business_name=business_name,
                business_id=business_id,
                observations=len(observations)
            )

        await db.commit()

        logger.info(
            "import_complete",
            imported=imported_count,
            skipped=skipped_count,
            total=len(businesses)
        )

        print(f"\n=== IMPORT SUMMARY ===")
        print(f"Imported: {imported_count}")
        print(f"Skipped (duplicates): {skipped_count}")
        print(f"Total in CSV: {len(businesses)}")

    finally:
        await db.close()


async def main():
    """Import enriched Google Places data."""
    await import_enriched_csv('data/google_places_FULLY_ENRICHED.csv')


if __name__ == '__main__':
    asyncio.run(main())
