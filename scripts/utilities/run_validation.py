"""
Run Validation on All Businesses in Database

Validates all businesses against 6-gate criteria and reports results.
"""
import asyncio
import aiosqlite
from src.services.new_validation_service import ValidationService
import structlog

logger = structlog.get_logger(__name__)


async def validate_all():
    """Validate all businesses in database."""
    db = await aiosqlite.connect('data/leads_v3.db')
    service = ValidationService()

    try:
        # Get all businesses
        cursor = await db.execute("SELECT id, original_name FROM businesses")
        businesses = await cursor.fetchall()

        logger.info("validation_started", total=len(businesses))

        qualified = []
        excluded = []
        review_required = []

        for business_id, name in businesses:
            # Get industry/place types for this business
            cursor = await db.execute("""
                SELECT value FROM observations
                WHERE business_id = ? AND field = 'industry'
                LIMIT 1
            """, (business_id,))
            industry_row = await cursor.fetchone()
            place_types = [industry_row[0]] if industry_row else ['general_business']

            status, reasons = await service.validate_business(db, business_id, place_types)
            result = {'status': status, 'reasons': reasons}

            if result['status'] == 'QUALIFIED':
                qualified.append((business_id, name))
            elif result['status'] == 'EXCLUDED':
                excluded.append((business_id, name, result.get('reasons', [])))
            else:
                review_required.append((business_id, name))

            logger.info(
                "business_validated",
                business_id=business_id,
                name=name,
                status=result['status'],
                reasons=result.get('reasons', [])
            )

        print("\n" + "="*60)
        print("VALIDATION RESULTS")
        print("="*60)

        print(f"\n✅ QUALIFIED: {len(qualified)}")
        for bid, name in qualified[:20]:
            print(f"   - {name} (ID: {bid})")

        print(f"\n❌ EXCLUDED: {len(excluded)}")
        for bid, name, reasons in excluded[:10]:
            print(f"   - {name}: {', '.join(reasons[:2])}")

        print(f"\n⚠️  REVIEW REQUIRED: {len(review_required)}")
        for bid, name in review_required[:10]:
            print(f"   - {name} (ID: {bid})")

        print("\n" + "="*60)

    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(validate_all())
