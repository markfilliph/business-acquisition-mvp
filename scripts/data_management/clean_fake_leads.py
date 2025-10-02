#!/usr/bin/env python3
"""
Clean fake/invalid leads from the database.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.database.connection import DatabaseManager
from src.core.config import config
import structlog

# Setup basic logging
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(colors=True)
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def clean_fake_leads():
    """Remove fake/invalid leads from database."""
    
    print("🧹 CLEANING FAKE LEADS FROM DATABASE")
    print("=" * 50)
    
    # Known fake business names and websites
    fake_businesses = [
        'Hamilton Office Solutions',
        'Stoney Creek Business Services',
        'Dundas Supply Co Ltd',
        'Ancaster Equipment Rentals'
    ]
    
    fake_websites = [
        'hamiltonoffice.ca',
        'stoneyservices.ca', 
        'dundassupply.com',
        'ancasteequipment.com'
    ]
    
    try:
        db = DatabaseManager(config.database)
        await db.initialize()
        
        # Get all leads
        async with db.get_connection() as db_conn:
            # Find fake business names
            for business_name in fake_businesses:
                result = await db_conn.execute(
                    "SELECT COUNT(*) FROM leads WHERE business_name = ?",
                    (business_name,)
                )
                count = (await result.fetchone())[0]
                
                if count > 0:
                    logger.warning(
                        "removing_fake_business",
                        business_name=business_name,
                        count=count
                    )
                    await db_conn.execute(
                        "DELETE FROM leads WHERE business_name = ?",
                        (business_name,)
                    )
                    print(f"❌ Removed {count} entries for fake business: {business_name}")
            
            # Find fake websites
            for website in fake_websites:
                result = await db_conn.execute(
                    "SELECT COUNT(*) FROM leads WHERE website LIKE ?",
                    (f"%{website}%",)
                )
                count = (await result.fetchone())[0]
                
                if count > 0:
                    logger.warning(
                        "removing_fake_website",
                        website=website,
                        count=count
                    )
                    await db_conn.execute(
                        "DELETE FROM leads WHERE website LIKE ?",
                        (f"%{website}%",)
                    )
                    print(f"❌ Removed {count} entries with fake website: {website}")
            
            # Clean related activities
            await db_conn.execute("""
                DELETE FROM lead_activities 
                WHERE lead_unique_id NOT IN (SELECT unique_id FROM leads)
            """)
            
            await db_conn.commit()
            
            # Get remaining count
            result = await db_conn.execute("SELECT COUNT(*) FROM leads")
            remaining_count = (await result.fetchone())[0]
            
            print(f"\n✅ Database cleanup completed")
            print(f"📊 Remaining leads: {remaining_count}")
            
            if remaining_count > 0:
                print("\n🔍 REMAINING LEADS:")
                result = await db_conn.execute(
                    "SELECT business_name, website, status FROM leads ORDER BY business_name"
                )
                leads = await result.fetchall()
                
                for i, (name, website, status) in enumerate(leads, 1):
                    print(f"{i}. {name} - {website} ({status})")
            
    except Exception as e:
        logger.error("cleanup_failed", error=str(e))
        print(f"❌ Cleanup failed: {e}")


async def main():
    await clean_fake_leads()


if __name__ == "__main__":
    asyncio.run(main())