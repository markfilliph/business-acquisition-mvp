#!/usr/bin/env python3
"""
Main pipeline runner for the lead generation system.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import config
from src.utils.logging_config import configure_logging
from src.agents.orchestrator import LeadGenerationOrchestrator


async def main():
    """Main pipeline execution function."""
    
    # Configure logging
    configure_logging(config)
    
    print("🚀 Starting Lead Generation Pipeline")
    print("=" * 50)
    print(f"Environment: {config.environment}")
    print(f"Target Revenue: ${config.business_criteria.target_revenue_min:,} - ${config.business_criteria.target_revenue_max:,}")
    print(f"Target Industries: {', '.join(config.business_criteria.target_industries)}")
    print(f"Minimum Business Age: {config.business_criteria.min_years_in_business} years")
    print("")
    
    # Initialize orchestrator
    orchestrator = LeadGenerationOrchestrator(config)
    
    try:
        # Run the pipeline
        results = await orchestrator.run_full_pipeline(target_leads=50)
        
        # Display results
        print("\n📊 PIPELINE RESULTS")
        print("=" * 50)
        print(f"Businesses Discovered: {results.total_discovered}")
        print(f"Successfully Enriched: {results.total_enriched}")
        print(f"Qualified Leads: {results.total_qualified}")
        print(f"Processing Errors: {results.total_errors}")
        print(f"Success Rate: {results.success_rate:.1%}")
        print(f"Average Score: {results.average_score:.1f}/100")
        print(f"Duration: {results.duration_seconds:.1f} seconds")
        
        if results.industry_breakdown:
            print(f"\n🏭 INDUSTRY BREAKDOWN")
            for industry, count in results.industry_breakdown.items():
                print(f"  {industry.replace('_', ' ').title()}: {count}")
        
        if results.top_performers:
            print(f"\n⭐ TOP PERFORMERS")
            for i, lead in enumerate(results.top_performers[:5], 1):
                print(f"  {i}. {lead.business_name} - Score: {lead.lead_score.total_score}")
        
        if results.recommendations:
            print(f"\n💡 RECOMMENDATIONS")
            for rec in results.recommendations:
                print(f"  • {rec}")
        
        print(f"\n✅ Pipeline completed successfully!")
        print(f"Check the database for detailed lead information.")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)