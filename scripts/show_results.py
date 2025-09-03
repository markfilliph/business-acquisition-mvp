#!/usr/bin/env python3
"""
Quick script to show the qualified leads from the pipeline.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import config
from src.database.connection import DatabaseManager

async def main():
    """Show the qualified leads."""
    
    print("🎯 QUALIFIED LEADS RESULTS")
    print("=" * 50)
    
    # Initialize database
    db_manager = DatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get qualified leads
        leads_data = await db_manager.get_qualified_leads(limit=10, min_score=60)
        
        if not leads_data:
            print("❌ No qualified leads found")
            return
        
        print(f"📊 Found {len(leads_data)} qualified leads\n")
        
        for i, lead in enumerate(leads_data, 1):
            print(f"🏢 {i}. {lead['business_name']}")
            print(f"   📍 {lead['address'] or 'Address N/A'}")
            print(f"   📞 {lead['phone'] or 'Phone N/A'}")
            print(f"   🌐 {lead['website'] or 'Website N/A'}")
            print(f"   📧 {lead['email'] or 'Email N/A'}")
            print(f"   🏭 Industry: {lead['industry'] or 'N/A'}")
            print(f"   📅 Years in Business: {lead['years_in_business'] or 'N/A'}")
            print(f"   👥 Employees: {lead['employee_count'] or 'N/A'}")
            print(f"   💰 Estimated Revenue: ${lead['estimated_revenue']:,}" if lead['estimated_revenue'] else "   💰 Revenue: N/A")
            print(f"   ⭐ Lead Score: {lead['lead_score']}/100")
            print(f"   🎯 Status: {lead['status'].title()}")
            print()
        
        print("=" * 50)
        print("✅ All leads are qualified and ready for outreach!")
        
    except Exception as e:
        print(f"❌ Error retrieving leads: {e}")

if __name__ == "__main__":
    asyncio.run(main())