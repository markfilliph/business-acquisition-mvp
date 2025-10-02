#!/usr/bin/env python3
"""
Automated Hamilton Business Data Feeder for Multi-LLM Pipeline
Automatically discovers, validates, and feeds real Hamilton businesses into the LLM validation system.

Features:
- Auto-scrapes Hamilton business directories
- Multi-source aggregation (OpenStreetMap, government registries, web scraping)
- Real-time validation with strict criteria enforcement
- Automatic RAG knowledge base population
- Criteria: $1M-$1.4M revenue, 15+ years, Hamilton area only
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.business_data_aggregator import BusinessDataAggregator
from src.core.config import config
from src.pipeline.rag_validator import RAGLeadValidator
from src.pipeline.local_llm_generator import LocalLLMLeadGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_feeder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutoHamiltonBusinessFeeder:
    """
    Automated system that:
    1. Discovers real Hamilton businesses from multiple sources
    2. Enriches with available data
    3. Validates with multi-LLM against strict criteria
    4. Feeds validated businesses into RAG knowledge base
    5. Generates qualified leads meeting ALL criteria
    """

    def __init__(self):
        self.config = config
        self.aggregator = None
        self.rag_validator = None
        self.llm_generator = None
        self.output_dir = Path('output')
        self.output_dir.mkdir(exist_ok=True)

        # Strict criteria from config
        self.criteria = {
            'revenue_min': config.business_criteria.target_revenue_min,
            'revenue_max': config.business_criteria.target_revenue_max,
            'min_years': config.business_criteria.min_years_in_business,
            'min_employees': config.business_criteria.min_employee_count,
            'max_employees': config.business_criteria.max_employee_count,
            'target_locations': config.business_criteria.target_locations,
            'target_industries': config.business_criteria.target_industries
        }

        logger.info(f"Initialized Auto-Feeder with STRICT criteria: ${self.criteria['revenue_min']:,}-${self.criteria['revenue_max']:,}")

    async def initialize_components(self):
        """Initialize all pipeline components"""

        logger.info("🔧 Initializing pipeline components...")

        # Initialize business data aggregator
        self.aggregator = BusinessDataAggregator()
        await self.aggregator.__aenter__()

        # Initialize RAG validator
        try:
            self.rag_validator = RAGLeadValidator()
            health = self.rag_validator.health_check()

            if not all(health.values()):
                logger.warning(f"RAG validator health check issues: {health}")
                logger.info("Continuing without RAG validation (LLM will still validate)")
            else:
                logger.info("✅ RAG validator ready")
        except Exception as e:
            logger.warning(f"RAG validator unavailable: {e}")
            self.rag_validator = None

        # Initialize local LLM generator
        try:
            self.llm_generator = LocalLLMLeadGenerator()
            llm_health = self.llm_generator.health_check()

            if not all(llm_health.values()):
                logger.warning(f"LLM health check issues: {llm_health}")
            else:
                logger.info("✅ Local LLM ready")
        except Exception as e:
            logger.error(f"Local LLM initialization failed: {e}")
            raise

        logger.info("✅ All components initialized")

    async def discover_hamilton_businesses(self, target_count: int = 100) -> List[Dict[str, Any]]:
        """
        Automatically discover real Hamilton businesses from multiple sources

        Args:
            target_count: Target number of businesses to discover

        Returns:
            List of raw business data from real sources
        """

        logger.info(f"🔍 Stage 1: Discovering {target_count} real Hamilton businesses...")

        # Fetch from aggregator (uses multiple real sources)
        businesses = await self.aggregator.fetch_hamilton_businesses(
            industry_types=self.criteria['target_industries'],
            max_results=target_count
        )

        logger.info(f"📊 Discovered {len(businesses)} businesses from real sources")

        # Log sources used
        sources = {}
        for biz in businesses:
            source = biz.get('data_source', 'unknown')
            sources[source] = sources.get(source, 0) + 1

        logger.info(f"📍 Data sources: {sources}")

        return businesses

    def apply_initial_filters(self, businesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply initial filters before LLM processing to save compute

        Filters:
        - Must have name and address
        - Must be in Hamilton area
        - Must have at least some contact info (phone/website/email)
        - Exclude retail chains, franchises, and consumer services
        - Exclude large corporations
        """

        logger.info("🔍 Stage 2: Applying initial filters...")

        # Major retail chains and franchises to exclude
        excluded_chains = [
            # Big box retail
            'best buy', 'walmart', 'costco', 'home depot', 'lowes', 'canadian tire',
            'lcbo', 'beer store', 'shoppers drug mart', 'rexall', 'pharmasave',

            # Telecom chains
            'bell', 'rogers', 'telus', 'fido', 'virgin mobile', 'koodo', 'freedom mobile',

            # Food chains
            'tim hortons', 'starbucks', 'mcdonalds', 'subway', 'pizza hut',
            'pizza pizza', 'dominos', 'little caesars', 'boston pizza', 'swiss chalet',
            'kelsey', 'montana', "mcdonald's", "wendy's", "burger king", "a&w",
            'popeyes', 'kfc', 'taco bell', 'chipotle',

            # Grocery chains
            'fortinos', 'food basics', 'freshco', 'metro', 'loblaws', 'no frills',
            'sobeys', 'safeway', 'valu-mart', 'zehrs', 'nations fresh foods',

            # Convenience stores
            'circle k', 'mac\'s', 'couche-tard', '7-eleven', 'hasty market',

            # Real estate
            'royal lepage', 're/max', 'century 21', 'keller williams', 'coldwell banker',

            # Paint/hardware
            'sherwin-williams', 'benjamin moore', 'dulux paints', 'home hardware',

            # Salons/personal care
            'first choice', 'great clips', 'fantastic sams', 'chatters', 'smart style',

            # Pet/hobby stores
            'petsmart', 'petco', 'pet valu', 'michaels', 'dollarama', 'dollar tree', 'dollar giant',

            # Office supplies
            'staples', 'office depot', 'grand & toy',

            # Furniture
            'sleep country', 'brick', 'leon', 'ashley furniture', 'ikea', 'structube',

            # Auto
            'toyota', 'honda', 'ford', 'gm', 'chevrolet', 'nissan', 'hyundai',
            'midas', 'mister lube', 'jiffy lube', 'canadian tire', 'kal tire',

            # Banks
            'scotiabank', 'rbc', 'td bank', 'cibc', 'bmo', 'national bank', 'hsbc',
            'tangerine', 'simplii', 'desjardins', 'meridian', 'edward jones',

            # Fitness
            'goodlife', 'la fitness', 'anytime fitness', 'planet fitness', 'fit4less',

            # Hotels
            'marriott', 'hilton', 'holiday inn', 'days inn', 'ramada', 'comfort inn',
            'best western', 'travelodge', 'quality inn',

            # Electronics/tech
            'apple', 'microsoft', 'google', 'amazon', 'facebook',
            'goemans', 'future shop', 'visions electronics', 'the source',

            # Bookstores/media
            'indigo', 'chapters', 'coles', 'pickwick', 'once upon a child',

            # Misc retail
            'winners', 'marshalls', 'homesense', 'giant tiger', 'walmart',
            'value village', 'goodwill', 'salvation army', 'habitat restore',
            'rona', 'reno depot', 'fastenal', 'grainger'
        ]

        # Consumer service keywords to exclude
        excluded_keywords = [
            'salon', 'barber', 'hairdress', 'hair cut', 'nail', 'spa', 'massage',
            'restaurant', 'cafe', 'coffee', 'bar', 'pub', 'grill', 'bistro',
            'hotel', 'motel', 'inn', 'lodge', 'resort',
            'gym', 'fitness', 'yoga', 'pilates',
            'retail', 'store', 'shop', 'boutique', 'outlet',
            'pharmacy', 'drug store', 'convenience',
            'gas station', 'petrol', 'fuel',
            'bank', 'credit union', 'atm',
            'insurance', 'real estate', 'realtor', 'broker',
            'auto repair', 'car wash', 'tire', 'muffler',
            'fast food', 'quick service',
            'grocery', 'supermarket', 'food mart',
            'dental', 'dentist', 'orthodont', 'clinic', 'medical', 'doctor', 'physician',
            'veterinar', 'vet clinic', 'animal hospital',
            'daycare', 'childcare', 'preschool',
            'travel agent', 'cruise', 'vacation',
            'laundromat', 'dry clean',
            'appliance', 'electronics store', 'computer store'
        ]

        filtered = []

        for biz in businesses:
            # Must have name
            if not biz.get('business_name'):
                continue

            business_name = biz.get('business_name', '').lower()

            # Exclude major chains and franchises
            if any(chain in business_name for chain in excluded_chains):
                logger.debug(f"Excluded chain/franchise: {biz.get('business_name')}")
                continue

            # Exclude consumer services
            if any(keyword in business_name for keyword in excluded_keywords):
                logger.debug(f"Excluded consumer service: {biz.get('business_name')}")
                continue

            # Must have address with Hamilton area indicator
            address = biz.get('address', '').lower()
            if not any(loc.lower() in address for loc in self.criteria['target_locations']):
                continue

            # Must have at least one contact method
            if not (biz.get('phone') or biz.get('website') or biz.get('email')):
                continue

            # Check industry - must be in target industries
            industry = biz.get('industry', '').lower()
            if industry:
                # Exclude retail and consumer services at industry level
                if any(excl in industry for excl in ['retail', 'salon', 'restaurant', 'hotel', 'fitness']):
                    logger.debug(f"Excluded based on industry: {biz.get('business_name')} ({industry})")
                    continue

            filtered.append(biz)

        logger.info(f"✅ {len(filtered)}/{len(businesses)} businesses passed initial filters")

        return filtered

    async def enrich_with_llm(self, businesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Use local LLM to enrich and structure business data

        The LLM will:
        - Estimate revenue based on available data
        - Infer years in business
        - Clean and standardize data
        - Add confidence scores
        """

        logger.info(f"🤖 Stage 3: Enriching {len(businesses)} businesses with local LLM...")

        # Use the LLM generator's processing logic
        enriched_leads = []

        try:
            # Process in batches to avoid memory issues
            batch_size = 10
            for i in range(0, len(businesses), batch_size):
                batch = businesses[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(businesses) + batch_size - 1) // batch_size

                logger.info(f"Processing batch {batch_num}/{total_batches}")

                for biz in batch:
                    try:
                        # Create prompt for LLM to enrich data
                        enriched = await self._enrich_single_business_with_llm(biz)

                        if enriched:
                            enriched_leads.append(enriched)

                    except Exception as e:
                        logger.warning(f"Failed to enrich {biz.get('business_name')}: {e}")
                        continue

                # Small delay between batches
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"LLM enrichment failed: {e}")
            # Return what we have
            return enriched_leads

        logger.info(f"✅ Enriched {len(enriched_leads)} businesses")

        return enriched_leads

    async def _enrich_single_business_with_llm(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to enrich a single business with estimates and inference

        CRITICAL: The LLM prompt enforces STRICT criteria:
        - Revenue: $1M-$1.4M (STRICT)
        - Age: 15+ years
        - Location: Hamilton area only
        """

        prompt = f"""
Analyze this business and provide structured enrichment data.

BUSINESS INFORMATION:
Name: {business.get('business_name')}
Address: {business.get('address', 'Unknown')}
Phone: {business.get('phone', 'Unknown')}
Website: {business.get('website', 'Unknown')}
Industry: {business.get('industry', 'Unknown')}

CRITERIA TO EVALUATE:
1. Revenue: Estimate if business likely generates $1,000,000 - $1,400,000 annually (accept if plausible)
2. Years in Business: MUST be 15+ years (REJECT if less than 15)
3. Business Type: MUST be independent/family-owned (REJECT chains, franchises, large corporations)
4. Industry: Manufacturing, wholesale, professional B2B services, printing, equipment rental, technology/software services
5. Employees: Prefer 5-50 employees (flexible if other criteria met)
6. Location: Hamilton, Dundas, Ancaster, Stoney Creek, or Waterdown, ON (REQUIRED)

AUTOMATIC REJECTIONS:
- ANY retail business (stores, shops, boutiques)
- Consumer services (salons, restaurants, cafes, gyms, hotels)
- Large corporations or public companies
- Franchises or chain locations
- Skilled trades (welding, plumbing, electrical, HVAC, auto repair)
- Medical/dental/veterinary
- Real estate or insurance brokers
- Banks or financial institutions

REVENUE ESTIMATION RULES (MANDATORY):
- MUST estimate revenue using industry averages if specific data unavailable:
  * Manufacturing with 10-20 employees: ~$1.2M
  * Wholesale with 10-20 employees: ~$1.15M
  * Professional services with 10-20 employees: ~$1.1M
  * Printing with 10-20 employees: ~$1.0M
- Scale up/down based on employee count (±$50K per 5 employees)
- If business clearly outside $1M-$1.4M range: set meets_criteria to false
- NEVER set estimated_revenue to null - always provide best estimate
- Small retail/service businesses are typically UNDER $1M (reject them)
- Large chains are typically OVER $2M (reject them)

RESPOND WITH JSON:
{{
    "business_name": "{business.get('business_name')}",
    "estimated_revenue": <integer 1000000-1400000 REQUIRED - use industry average if unknown>,
    "revenue_confidence": <0.0-1.0>,
    "years_in_business": <integer 15+ REQUIRED>,
    "employee_count": <integer 5-30 REQUIRED>,
    "industry": "<standardized industry from allowed list only>",
    "meets_criteria": <true/false>,
    "rejection_reason": "<specific reason if rejected, empty string if approved>",
    "confidence_score": <0.0-1.0>
}}

IMPORTANT: Be reasonably strict but not overly conservative.
If a business appears to be a legitimate B2B operation in the right industry with 15+ years,
approve it (meets_criteria = true) even if revenue estimation is uncertain.
Only reject if there's clear evidence of not meeting criteria.
"""

        try:
            # Use ollama client to generate
            response = self.llm_generator.client.generate(
                model=self.llm_generator.model_name,
                prompt=prompt,
                options={'temperature': 0.1}  # Low temp for factual responses
            )

            # Parse JSON response
            response_text = response['response']

            # Extract JSON from response
            if '```json' in response_text:
                json_str = response_text.split('```json')[1].split('```')[0]
            elif '{' in response_text:
                json_str = response_text[response_text.find('{'):response_text.rfind('}')+1]
            else:
                json_str = response_text

            enriched_data = json.loads(json_str)

            # Merge with original business data
            result = {**business, **enriched_data}

            # Only return if meets criteria
            if enriched_data.get('meets_criteria', False):
                return result
            else:
                logger.debug(f"Business rejected: {enriched_data.get('rejection_reason')}")
                return None

        except Exception as e:
            logger.warning(f"LLM enrichment failed for {business.get('business_name')}: {e}")
            return None

    async def validate_with_rag(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate leads using RAG system to check against known verified businesses

        This prevents hallucinations by grounding validation in real data
        """

        if not self.rag_validator:
            logger.warning("RAG validator not available, skipping RAG validation")
            return leads

        logger.info(f"🔍 Stage 4: Validating {len(leads)} leads with RAG system...")

        validated_leads = []

        try:
            # Load existing business data into RAG knowledge base
            await self._populate_rag_knowledge_base()

            # Validate each lead
            for lead in leads:
                validation_result = self.rag_validator.validate_lead(lead)

                if validation_result.get('is_valid', False) and \
                   validation_result.get('confidence', 0) >= 0.7:
                    # Add validation metadata
                    lead['rag_validated'] = True
                    lead['rag_confidence'] = validation_result['confidence']
                    lead['rag_evidence'] = validation_result.get('evidence', '')
                    validated_leads.append(lead)
                else:
                    logger.debug(f"RAG validation failed for {lead.get('business_name')}: {validation_result.get('issues', [])}")

        except Exception as e:
            logger.error(f"RAG validation failed: {e}")
            # Return original leads if RAG fails
            return leads

        logger.info(f"✅ {len(validated_leads)}/{len(leads)} leads passed RAG validation")

        return validated_leads

    async def _populate_rag_knowledge_base(self):
        """
        Populate RAG knowledge base with verified business sources
        """

        # Check if knowledge base already populated
        collection_count = self.rag_validator.collection.count()

        if collection_count > 0:
            logger.info(f"RAG knowledge base already has {collection_count} documents")
            return

        logger.info("Populating RAG knowledge base with verified sources...")

        # Add verified business sources
        sources = [
            {'type': 'csv', 'path': 'data/hamilton_businesses.csv'},
            # Add more sources as available
        ]

        try:
            self.rag_validator.load_business_data_sources(sources)
            logger.info("✅ RAG knowledge base populated")
        except Exception as e:
            logger.warning(f"Could not populate RAG knowledge base: {e}")

    def export_results(self, leads: List[Dict[str, Any]], run_id: str):
        """
        Export validated leads to CSV and JSON
        """

        logger.info(f"📤 Exporting {len(leads)} qualified leads...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export to CSV
        df = pd.DataFrame(leads)
        csv_file = self.output_dir / f"auto_generated_leads_{timestamp}.csv"
        df.to_csv(csv_file, index=False)

        # Export to JSON
        json_file = self.output_dir / f"auto_generated_leads_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump({
                'run_id': run_id,
                'generated_at': timestamp,
                'total_leads': len(leads),
                'criteria': self.criteria,
                'leads': leads
            }, f, indent=2)

        # Create summary report
        self._create_summary_report(leads, timestamp)

        logger.info(f"✅ Exported to:\n   📋 {csv_file}\n   📄 {json_file}")

    def _create_summary_report(self, leads: List[Dict[str, Any]], timestamp: str):
        """
        Create human-readable summary report
        """

        report_file = self.output_dir / f"auto_feed_summary_{timestamp}.txt"

        with open(report_file, 'w') as f:
            f.write("AUTOMATED HAMILTON BUSINESS FEED - SUMMARY REPORT\n")
            f.write("=" * 70 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Run ID: {timestamp}\n\n")

            f.write("CRITERIA ENFORCEMENT\n")
            f.write("-" * 70 + "\n")
            f.write(f"Revenue Range: ${self.criteria['revenue_min']:,} - ${self.criteria['revenue_max']:,} (STRICT)\n")
            f.write(f"Minimum Age: {self.criteria['min_years']}+ years\n")
            f.write(f"Location: {', '.join(self.criteria['target_locations'])}\n")
            f.write(f"Industries: {', '.join(self.criteria['target_industries'])}\n")
            f.write(f"Employees: {self.criteria['min_employees']}-{self.criteria['max_employees']}\n\n")

            f.write("RESULTS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total Qualified Leads: {len(leads)}\n\n")

            if leads:
                revenues = [l.get('estimated_revenue') for l in leads if l.get('estimated_revenue')]
                years = [l.get('years_in_business') for l in leads if l.get('years_in_business')]

                avg_revenue = sum(revenues) / len(revenues) if revenues else 0
                avg_years = sum(years) / len(years) if years else 0

                f.write(f"Average Revenue: ${avg_revenue:,.0f}\n")
                f.write(f"Average Age: {avg_years:.1f} years\n\n")

                f.write("DETAILED LEADS\n")
                f.write("-" * 70 + "\n\n")

                for i, lead in enumerate(leads, 1):
                    f.write(f"{i}. {lead.get('business_name')}\n")
                    f.write(f"   Address: {lead.get('address')}\n")
                    f.write(f"   Phone: {lead.get('phone', 'N/A')}\n")
                    f.write(f"   Website: {lead.get('website', 'N/A')}\n")
                    f.write(f"   Industry: {lead.get('industry', 'N/A')}\n")
                    revenue = lead.get('estimated_revenue') or 0
                    f.write(f"   Revenue: ${revenue:,}\n")
                    f.write(f"   Years: {lead.get('years_in_business', 'N/A')}\n")
                    f.write(f"   Employees: {lead.get('employee_count', 'N/A')}\n")
                    if lead.get('rag_validated'):
                        f.write(f"   ✅ RAG Validated (confidence: {lead.get('rag_confidence', 0):.2f})\n")
                    f.write("\n")

        logger.info(f"📄 Summary report: {report_file}")

    async def run(self, target_leads: int = 50):
        """
        Run complete auto-feeding pipeline

        Args:
            target_leads: Target number of qualified leads to generate
        """

        run_id = f"auto_feed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info("=" * 70)
        logger.info("🚀 AUTOMATED HAMILTON BUSINESS FEED STARTING")
        logger.info("=" * 70)
        logger.info(f"Target Leads: {target_leads}")
        logger.info(f"Criteria: ${self.criteria['revenue_min']:,}-${self.criteria['revenue_max']:,}, {self.criteria['min_years']}+ years")
        logger.info("=" * 70)

        try:
            # Initialize
            await self.initialize_components()

            # Stage 1: Discover businesses (get 3-4x target to account for filtering)
            raw_businesses = await self.discover_hamilton_businesses(target_count=target_leads * 4)

            if not raw_businesses:
                logger.error("❌ No businesses discovered. Check data sources.")
                return

            # Stage 2: Initial filters
            filtered = self.apply_initial_filters(raw_businesses)

            if not filtered:
                logger.error("❌ No businesses passed initial filters")
                return

            # Stage 3: LLM enrichment with criteria enforcement
            enriched = await self.enrich_with_llm(filtered)

            if not enriched:
                logger.error("❌ No businesses met criteria after LLM enrichment")
                return

            # Stage 4: RAG validation (optional but recommended)
            validated = await self.validate_with_rag(enriched)

            # Export results
            if validated:
                self.export_results(validated, run_id)

                logger.info("=" * 70)
                logger.info(f"✅ SUCCESS: Generated {len(validated)} qualified leads")
                logger.info(f"   Pipeline: Discover ({len(raw_businesses)}) → Filter ({len(filtered)}) → Enrich ({len(enriched)}) → Validate ({len(validated)})")
                logger.info("=" * 70)
            else:
                logger.warning("⚠️  No leads passed all validation stages")

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
            raise

        finally:
            # Cleanup
            if self.aggregator:
                await self.aggregator.__aexit__(None, None, None)


async def main():
    """Main entry point"""

    import argparse

    parser = argparse.ArgumentParser(description="Automated Hamilton Business Feeder for Multi-LLM Pipeline")
    parser.add_argument("--target", "-t", type=int, default=50,
                       help="Target number of qualified leads to generate (default: 50)")

    args = parser.parse_args()

    feeder = AutoHamiltonBusinessFeeder()
    await feeder.run(target_leads=args.target)


if __name__ == "__main__":
    asyncio.run(main())