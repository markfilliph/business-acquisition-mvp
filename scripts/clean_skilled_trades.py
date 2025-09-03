#!/usr/bin/env python3
"""
Clean skilled trades from the database.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import config
from src.database.connection import DatabaseManager

async def clean_skilled_trades():
    """Remove all skilled trades from the database."""
    
    print("🧹 CLEANING SKILLED TRADES FROM DATABASE")
    print("=" * 50)
    
    # Initialize database
    db_manager = DatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get connection
        conn = db_manager._connection
        
        # Check current skilled trades
        cursor = await conn.execute("""
            SELECT business_name, industry 
            FROM leads 
            WHERE industry IN ('metal_fabrication', 'auto_repair', 'construction')
        """)
        skilled_trades = await cursor.fetchall()
        
        if skilled_trades:
            print(f"Found {len(skilled_trades)} skilled trade businesses to remove:")
            for name, industry in skilled_trades:
                print(f"  - {name} ({industry})")
            
            # Delete skilled trades
            await conn.execute("""
                DELETE FROM leads 
                WHERE industry IN ('metal_fabrication', 'auto_repair', 'construction')
            """)
            await conn.commit()
            
            print(f"\n✅ Successfully removed {len(skilled_trades)} skilled trade businesses")
        else:
            print("✅ No skilled trades found in database")
        
        # Show remaining qualified leads
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM leads WHERE status = 'qualified'
        """)
        qualified_count = await cursor.fetchone()
        print(f"📊 Remaining qualified leads: {qualified_count[0]}")
        
    except Exception as e:
        print(f"❌ Error cleaning database: {e}")

if __name__ == "__main__":
    asyncio.run(clean_skilled_trades())