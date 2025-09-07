#!/usr/bin/env python3
"""
Simple on-demand lead generation command for quality adjustment phase.

Usage:
    python scripts/generate_leads.py [--count 10] [--show-results]

Examples:
    python scripts/generate_leads.py                    # Generate default leads
    python scripts/generate_leads.py --count 5          # Generate 5 leads
    python scripts/generate_leads.py --show-results     # Generate and show results
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.agents.orchestrator import LeadGenerationOrchestrator
from src.core.config import config
from src.database.connection import DatabaseManager


async def generate_leads_simple(count: int = 10, show_results: bool = False):
    """Generate leads with simple command."""
    
    print(f"🚀 GENERATING {count} LEADS")
    print("=" * 40)
    print(f"Target Revenue: ${config.business_criteria.target_revenue_min:,} - ${config.business_criteria.target_revenue_max:,}")
    print(f"Target Industries: {', '.join(config.business_criteria.target_industries)}")
    print(f"Minimum Age: {config.business_criteria.min_years_in_business} years")
    print()
    
    try:
        # Run pipeline
        orchestrator = LeadGenerationOrchestrator(config)
        results = await orchestrator.run_full_pipeline(target_leads=count)
        
        # Show summary
        print("✅ GENERATION COMPLETE")
        print(f"   Discovered: {results.total_discovered} businesses")
        print(f"   Validated: {results.total_validated} leads")
        print(f"   Qualified: {results.total_qualified} leads") 
        print(f"   Success Rate: {results.success_rate:.1%}")
        print(f"   Duration: {results.duration_seconds:.1f} seconds")
        
        if results.total_qualified > 0:
            print(f"\n🎯 {results.total_qualified} QUALIFIED LEADS READY FOR OUTREACH!")
        else:
            print(f"\n⚠️  No leads qualified with current criteria")
            
        # Show results if requested
        if show_results and results.total_qualified > 0:
            print("\n" + "=" * 50)
            await show_qualified_leads()
            
        return True
        
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return False


async def show_qualified_leads():
    """Show qualified leads from database."""
    try:
        db = DatabaseManager(config.database)
        await db.initialize()
        
        async with db.get_connection() as db_conn:
            result = await db_conn.execute("""
                SELECT business_name, phone, website, industry, 
                       years_in_business, employee_count, estimated_revenue,
                       lead_score, address
                FROM leads 
                WHERE status = 'qualified' 
                ORDER BY lead_score DESC
            """)
            leads = await result.fetchall()
            
            if not leads:
                print("📊 No qualified leads found")
                return
                
            print(f"📊 Found {len(leads)} qualified leads:\n")
            
            for i, (name, phone, website, industry, years, employees, revenue, score, address) in enumerate(leads, 1):
                revenue_formatted = f"${revenue:,}" if revenue else "N/A"
                print(f"🏢 {i}. {name}")
                print(f"   📍 {address}")
                print(f"   📞 {phone}")
                print(f"   🌐 {website}")
                print(f"   🏭 Industry: {industry}")
                print(f"   📅 Age: {years} years | 👥 Employees: {employees}")
                print(f"   💰 Revenue: {revenue_formatted}")
                print(f"   ⭐ Score: {score}/100")
                print()
                
    except Exception as e:
        print(f"❌ Error showing results: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate business leads on-demand")
    parser.add_argument("--count", "-c", type=int, default=10, 
                       help="Number of leads to target (default: 10)")
    parser.add_argument("--show-results", "-s", action="store_true",
                       help="Show qualified leads after generation")
    
    args = parser.parse_args()
    
    success = await generate_leads_simple(args.count, args.show_results)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())