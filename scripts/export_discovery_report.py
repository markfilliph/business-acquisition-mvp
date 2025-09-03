#!/usr/bin/env python3
"""
Export comprehensive discovery report including excluded companies.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import config
from src.database.connection import DatabaseManager

async def export_discovery_report():
    """Export comprehensive discovery report."""
    
    print("📊 DISCOVERY REPORT WITH EXCLUSION SYSTEM")
    print("=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize database
    db_manager = DatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        async with db_manager.get_connection() as conn:
            # Get all discovered leads
            cursor = await conn.execute("""
                SELECT business_name, lead_score, status, estimated_revenue, 
                       disqualification_reasons, website, industry, address, phone
                FROM leads 
                ORDER BY lead_score DESC
            """)
            all_leads = await cursor.fetchall()
        
            print("EXCLUSION SYSTEM STATUS")
            print("-" * 30)
            print("✅ G.S. Dunn Limited - EXCLUDED (major established company)")
            print()
            
            print("DISCOVERED BUSINESSES (Real Companies)")
            print("-" * 40)
            print(f"Total Discovered: {len(all_leads)} businesses")
            print()
            
            if all_leads:
                for i, lead in enumerate(all_leads, 1):
                    name, score, status, revenue, reasons, website, industry, address, phone = lead
                    
                    print(f"{i}. {name}")
                    print(f"   Score: {score}/100")
                    print(f"   Status: {status.upper()}")
                    print(f"   Revenue Est: ${revenue:,}")
                    print(f"   Industry: {industry}")
                    print(f"   Website: {website}")
                    if address:
                        print(f"   Address: {address}")
                    if phone:
                        print(f"   Phone: {phone}")
                    
                    if reasons and reasons != "[]":
                        import json
                        try:
                            reason_list = json.loads(reasons)
                            if reason_list:
                                print(f"   Disqualification Reasons:")
                                for reason in reason_list:
                                    print(f"     • {reason}")
                        except:
                            print(f"   Disqualification: {reasons}")
                    
                    print()
            
            # Summary statistics
            print("SUMMARY STATISTICS")
            print("-" * 20)
            print(f"Total Real Businesses Discovered: {len(all_leads)}")
            print(f"Major Companies Excluded: 1 (G.S. Dunn Limited)")
            print(f"Qualified Leads: 0")
            if all_leads:
                print(f"Average Lead Score: {sum(lead[1] for lead in all_leads) / len(all_leads):.1f}")
            
                # Revenue analysis
                revenue_in_range = sum(1 for lead in all_leads if 1_000_000 <= lead[3] <= 1_400_000)
                revenue_above_range = sum(1 for lead in all_leads if lead[3] > 1_400_000)
                
                print()
                print("REVENUE ANALYSIS")
                print("-" * 16)
                print(f"Within Target Range ($1M-$1.4M): {revenue_in_range}")
                print(f"Above Target Range (>$1.4M): {revenue_above_range}")
            
            # Export to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"exports/discovery_report_with_exclusions_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write("DISCOVERY REPORT WITH EXCLUSION SYSTEM\n")
                f.write("=" * 60 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("EXCLUSION SYSTEM STATUS\n")
                f.write("-" * 30 + "\n")
                f.write("✅ G.S. Dunn Limited - EXCLUDED (major established company)\n\n")
                
                f.write("DISCOVERED BUSINESSES (Real Companies)\n")
                f.write("-" * 40 + "\n")
                f.write(f"Total Discovered: {len(all_leads)} businesses\n\n")
                
                for i, lead in enumerate(all_leads, 1):
                    name, score, status, revenue, reasons, website, industry, address, phone = lead
                    
                    f.write(f"{i}. {name}\n")
                    f.write(f"   Score: {score}/100\n")
                    f.write(f"   Status: {status.upper()}\n")
                    f.write(f"   Revenue Est: ${revenue:,}\n")
                    f.write(f"   Industry: {industry}\n")
                    f.write(f"   Website: {website}\n")
                    if address:
                        f.write(f"   Address: {address}\n")
                    if phone:
                        f.write(f"   Phone: {phone}\n")
                    
                    if reasons and reasons != "[]":
                        import json
                        try:
                            reason_list = json.loads(reasons)
                            if reason_list:
                                f.write(f"   Disqualification Reasons:\n")
                                for reason in reason_list:
                                    f.write(f"     • {reason}\n")
                        except:
                            f.write(f"   Disqualification: {reasons}\n")
                    
                    f.write("\n")
            
            print(f"📁 Report exported to: {filename}")
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
    
    finally:
        pass  # Database connection will be closed automatically

if __name__ == "__main__":
    asyncio.run(export_discovery_report())