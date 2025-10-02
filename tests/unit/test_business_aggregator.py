#!/usr/bin/env python3
"""
Test Business Data Aggregator integration.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.integrations.business_data_aggregator import BusinessDataAggregator


async def test_business_aggregator():
    """Test the Business Data Aggregator with real data sources."""
    
    print("🧪 TESTING BUSINESS DATA AGGREGATOR")
    print("=" * 50)
    
    try:
        async with BusinessDataAggregator() as aggregator:
            print("✅ Business Data Aggregator initialized")
            
            # Test business data collection
            print("\n🔍 Fetching Hamilton businesses from multiple sources...")
            businesses = await aggregator.fetch_hamilton_businesses(
                industry_types=["manufacturing", "professional_services", "printing"],
                max_results=8
            )
            
            print(f"📊 Found {len(businesses)} businesses:")
            print()
            
            for i, business in enumerate(businesses, 1):
                print(f"🏢 {i}. {business.get('business_name', 'N/A')}")
                print(f"   📍 Address: {business.get('address', 'N/A')}")
                print(f"   📞 Phone: {business.get('phone', 'N/A')}")
                print(f"   🌐 Website: {business.get('website', 'N/A')}")
                print(f"   🏭 Industry: {business.get('industry', 'N/A')}")
                print(f"   📅 Years in Business: {business.get('years_in_business', 'N/A')}")
                print(f"   👥 Employees: {business.get('employee_count', 'N/A')}")
                print(f"   📊 Data Source: {business.get('data_source', 'N/A')}")
                print()
            
            if businesses:
                print(f"✅ SUCCESS: Found {len(businesses)} real businesses!")
                print("🚀 Business Data Aggregator is working!")
                
                # Analyze data sources
                sources = {}
                for business in businesses:
                    source = business.get('data_source', 'unknown')
                    sources[source] = sources.get(source, 0) + 1
                
                print(f"\n📈 Data Source Breakdown:")
                for source, count in sources.items():
                    print(f"   {source}: {count} businesses")
                
            else:
                print("⚠️  WARNING: No businesses found")
                
    except Exception as e:
        print(f"❌ ERROR: Business Data Aggregator failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_business_aggregator())