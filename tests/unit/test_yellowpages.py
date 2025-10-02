#!/usr/bin/env python3
"""
Test YellowPages API integration to verify real data collection.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.integrations.yellowpages_client import YellowPagesClient


async def test_yellowpages_integration():
    """Test the YellowPages integration with real data."""
    
    print("🧪 TESTING YELLOWPAGES INTEGRATION")
    print("=" * 50)
    
    try:
        async with YellowPagesClient() as yp_client:
            print("✅ YellowPages client initialized")
            
            # Test manufacturing search
            print("\n🔍 Searching for manufacturing businesses in Hamilton...")
            manufacturing = await yp_client.search_hamilton_businesses(
                industry_category="manufacturing", 
                max_results=3
            )
            
            print(f"📊 Found {len(manufacturing)} manufacturing businesses:")
            for i, business in enumerate(manufacturing, 1):
                print(f"  {i}. {business.get('business_name', 'N/A')}")
                print(f"     Phone: {business.get('phone', 'N/A')}")
                print(f"     Address: {business.get('address', 'N/A')}")
                print(f"     Website: {business.get('website', 'N/A')}")
                print()
            
            # Test professional services search
            print("🔍 Searching for professional services in Hamilton...")
            professional = await yp_client.search_hamilton_businesses(
                industry_category="professional_services", 
                max_results=2
            )
            
            print(f"📊 Found {len(professional)} professional services businesses:")
            for i, business in enumerate(professional, 1):
                print(f"  {i}. {business.get('business_name', 'N/A')}")
                print(f"     Phone: {business.get('phone', 'N/A')}")
                print(f"     Address: {business.get('address', 'N/A')}")
                print(f"     Website: {business.get('website', 'N/A')}")
                print()
            
            total_found = len(manufacturing) + len(professional)
            
            if total_found > 0:
                print(f"✅ SUCCESS: Found {total_found} real businesses from YellowPages")
                print("🚀 YellowPages integration is working!")
            else:
                print("⚠️  WARNING: No businesses found - may need to adjust search parameters")
                
    except Exception as e:
        print(f"❌ ERROR: YellowPages integration failed: {str(e)}")
        print("📝 This might be due to:")
        print("   - Rate limiting from YellowPages")
        print("   - Network connectivity issues")
        print("   - Changes in YellowPages HTML structure")
        print("   - Anti-bot protection")


if __name__ == "__main__":
    asyncio.run(test_yellowpages_integration())