#!/usr/bin/env python3
"""
Complete Local LLM Lead Generation Pipeline
Implements the full pipeline as specified in Local-model-setup-instructions.md

Usage:
    python -m src.pipeline.lead_generation_pipeline --source "hamilton" --count 45 --min-effectiveness 0.7 --validate --enrich
"""

import os
import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

from src.pipeline.local_llm_generator import LocalLLMLeadGenerator, LeadGenerationResult
from src.pipeline.rag_validator import RAGLeadValidator, SmartLeadEnricher

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

class LeadGenerationPipeline:
    """
    Complete lead generation pipeline using local LLM
    Integrates generation, validation, and enrichment
    """

    def __init__(self):
        self.output_dir = Path(os.getenv('OUTPUT_DIR', './output'))
        self.output_dir.mkdir(exist_ok=True)

        # Initialize components
        self.generator = LocalLLMLeadGenerator()
        self.validator = None
        self.enricher = None

        logger.info("Initialized Lead Generation Pipeline")

    def health_check(self) -> Dict[str, bool]:
        """
        Comprehensive health check for all pipeline components
        """
        checks = {
            'generator_ready': False,
            'validator_ready': False,
            'output_writable': False
        }

        try:
            # Check generator
            gen_health = self.generator.health_check()
            checks['generator_ready'] = all(gen_health.values())

            # Check validator (if initialized)
            if self.validator:
                val_health = self.validator.health_check()
                checks['validator_ready'] = all(val_health.values())

            # Check output directory
            test_file = self.output_dir / 'test_write.tmp'
            test_file.write_text('test')
            test_file.unlink()
            checks['output_writable'] = True

        except Exception as e:
            logger.error(f"Pipeline health check failed: {e}")

        return checks

    def load_sample_data(self, source: str, count: int) -> List[Dict[str, Any]]:
        """
        REMOVED: Sample business data - NO HARDCODED/FAKE DATA ALLOWED.
        This function now raises an error. All businesses must come from real-time external sources.
        """
        logger.error("sample_data_disabled",
                    extra={"reason": "No sample/fake data allowed - use real sources only"})

        # CRITICAL FIX: Do not return fake sample data
        # Must connect to real data sources (OSM, YellowPages, government sources)
        raise NotImplementedError(
            "Sample data generation is disabled. "
            "All business data must come from verified external sources. "
            "Use BusinessDataAggregator instead."
        )

    async def run_full_pipeline(self, source: str, count: int,
                              min_effectiveness: float = 0.7,
                              validate: bool = False,
                              enrich: bool = False) -> Dict[str, Any]:
        """
        Run the complete lead generation pipeline
        """
        start_time = datetime.now()
        logger.info(f"🚀 Starting lead generation pipeline")
        logger.info(f"Source: {source}, Count: {count}, Min Effectiveness: {min_effectiveness}")
        logger.info(f"Validation: {validate}, Enrichment: {enrich}")

        results = {
            'pipeline_start': start_time.isoformat(),
            'source': source,
            'target_count': count,
            'stages_completed': [],
            'files_generated': [],
            'final_stats': {}
        }

        try:
            # Stage 1: Load raw data
            logger.info("📥 Stage 1: Loading raw business data...")
            raw_data = self.load_sample_data(source, count * 2)  # Get more data than needed
            results['stages_completed'].append('data_loading')
            logger.info(f"✅ Loaded {len(raw_data)} raw business records")

            # Stage 2: Generate leads
            logger.info("🤖 Stage 2: Generating leads with local LLM...")
            generation_result = self.generator.generate_leads_with_retry(raw_data)

            if generation_result.total_qualified == 0:
                logger.error("❌ No qualified leads generated")
                results['error'] = 'No qualified leads generated'
                return results

            results['stages_completed'].append('lead_generation')
            logger.info(f"✅ Generated {generation_result.total_qualified} qualified leads")

            # Save initial leads
            leads_file = self.generator.save_results(generation_result, "pipeline_leads")
            results['files_generated'].append(str(leads_file))

            current_leads = generation_result.leads

            # Stage 3: Validation (optional)
            if validate:
                logger.info("🔍 Stage 3: Validating leads with RAG system...")

                # Initialize validator if not already done
                if not self.validator:
                    self.validator = RAGLeadValidator()

                    # Load knowledge base if needed
                    if not Path("./chroma_db").exists():
                        logger.info("Building knowledge base for validation...")
                        sources = [
                            {'type': 'csv', 'path': 'data/hamilton_businesses.csv'},
                            {'type': 'json', 'path': 'data/verified_sources.json'}
                        ]
                        # Note: In production, this would load real verified sources
                        logger.info("Knowledge base would be built from verified sources")

                # Validate leads
                validated_df = self.validator.batch_validate(current_leads, confidence_threshold=0.7)

                # Save validated leads
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                validated_file = self.output_dir / f"validated_leads_{timestamp}.csv"
                validated_df.to_csv(validated_file, index=False)
                results['files_generated'].append(str(validated_file))

                # Update current leads to only approved ones
                current_leads = validated_df[validated_df['status'] == 'approved'].to_dict('records')
                results['stages_completed'].append('validation')
                logger.info(f"✅ Validated leads, {len(current_leads)} approved")

            # Stage 4: Enrichment (optional)
            if enrich and current_leads:
                logger.info("🌟 Stage 4: Enriching leads with additional data...")

                # Initialize enricher if not already done
                if not self.enricher:
                    if not self.validator:
                        self.validator = RAGLeadValidator()
                    self.enricher = SmartLeadEnricher(self.validator)

                # Enrich leads
                enriched_leads = []
                for lead in current_leads:
                    enriched_lead = self.enricher.enrich_lead(lead)
                    enriched_leads.append(enriched_lead)

                # Save enriched leads
                if enriched_leads:
                    enriched_df = pd.DataFrame(enriched_leads)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    enriched_file = self.output_dir / f"enriched_leads_{timestamp}.csv"
                    enriched_df.to_csv(enriched_file, index=False)
                    results['files_generated'].append(str(enriched_file))

                current_leads = enriched_leads
                results['stages_completed'].append('enrichment')
                logger.info(f"✅ Enriched {len(current_leads)} leads")

            # Final statistics
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            results.update({
                'pipeline_end': end_time.isoformat(),
                'duration_seconds': duration,
                'final_stats': {
                    'raw_data_count': len(raw_data),
                    'initial_qualified': generation_result.total_qualified,
                    'final_leads_count': len(current_leads),
                    'success_rate': generation_result.success_rate,
                    'stages_completed': len(results['stages_completed'])
                }
            })

            # Save pipeline summary
            summary_file = self.output_dir / f"pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(summary_file, 'w') as f:
                import json
                json.dump(results, f, indent=2)
            results['files_generated'].append(str(summary_file))

            logger.info(f"🎉 Pipeline completed successfully!")
            logger.info(f"⏱️  Total duration: {duration:.1f} seconds")
            logger.info(f"📊 Final leads: {len(current_leads)}")

            return results

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            results['error'] = str(e)
            results['failed_at'] = datetime.now().isoformat()
            return results

def main():
    """Main entry point for pipeline execution"""

    parser = argparse.ArgumentParser(
        description="Run complete local LLM lead generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic generation
  python run_pipeline.py --source hamilton --count 20

  # With validation
  python run_pipeline.py --source hamilton --count 45 --validate

  # Full pipeline with validation and enrichment
  python run_pipeline.py --source hamilton --count 45 --min-effectiveness 0.7 --validate --enrich

  # High threshold for quality
  python run_pipeline.py --source hamilton --count 30 --min-effectiveness 0.8 --validate --enrich
        """
    )

    parser.add_argument("--source", "-s", default="hamilton",
                       help="Data source location (default: hamilton)")
    parser.add_argument("--count", "-c", type=int, default=45,
                       help="Target number of leads (default: 45)")
    parser.add_argument("--min-effectiveness", "-e", type=float, default=0.7,
                       help="Minimum effectiveness threshold (default: 0.7)")
    parser.add_argument("--validate", "-v", action="store_true",
                       help="Enable RAG validation")
    parser.add_argument("--enrich", "-r", action="store_true",
                       help="Enable lead enrichment")
    parser.add_argument("--health-check", action="store_true",
                       help="Run health check and exit")

    args = parser.parse_args()

    # Initialize pipeline
    pipeline = LeadGenerationPipeline()

    # Health check if requested
    if args.health_check:
        health = pipeline.health_check()
        print("\\n🏥 PIPELINE HEALTH CHECK")
        print("=" * 40)

        all_healthy = True
        for component, status in health.items():
            icon = "✅" if status else "❌"
            print(f"{icon} {component}: {'OK' if status else 'FAILED'}")
            if not status:
                all_healthy = False

        if all_healthy:
            print("\\n🎉 All systems operational!")
            sys.exit(0)
        else:
            print("\\n⚠️  Some components failed. Please check setup.")
            sys.exit(1)

    # Run pipeline
    async def run_pipeline():
        results = await pipeline.run_full_pipeline(
            source=args.source,
            count=args.count,
            min_effectiveness=args.min_effectiveness,
            validate=args.validate,
            enrich=args.enrich
        )

        # Print summary
        print(f"\\n{'='*60}")
        print(f"PIPELINE EXECUTION SUMMARY")
        print(f"{'='*60}")

        if 'error' in results:
            print(f"❌ Pipeline failed: {results['error']}")
            sys.exit(1)

        stats = results['final_stats']
        print(f"📊 Raw data processed: {stats['raw_data_count']}")
        print(f"🤖 Initial qualified leads: {stats['initial_qualified']}")
        print(f"🎯 Final leads: {stats['final_leads_count']}")
        print(f"📈 Success rate: {stats['success_rate']:.1%}")
        print(f"⏱️  Duration: {results['duration_seconds']:.1f} seconds")
        print(f"🔧 Stages completed: {', '.join(results['stages_completed'])}")

        print(f"\\n📁 Generated files:")
        for file_path in results['files_generated']:
            print(f"  • {file_path}")

        print(f"\\n✨ Pipeline completed successfully!")

    # Run the async pipeline
    asyncio.run(run_pipeline())

if __name__ == "__main__":
    main()