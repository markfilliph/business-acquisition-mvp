#!/usr/bin/env python3
"""
Local LLM Lead Generation System
Implements specifications from Local-model-setup-instructions.md
Uses Ollama for local lead generation without API dependencies
"""

import os
from typing import List, Dict, Any, Optional
import pandas as pd
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import time
import ollama
from dataclasses import dataclass
import traceback

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/lead_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

@dataclass
class LeadGenerationResult:
    """Container for lead generation results"""
    total_discovered: int
    total_validated: int
    total_qualified: int
    success_rate: float
    duration_seconds: float
    leads: List[Dict[str, Any]]

class LocalLLMLeadGenerator:
    """
    Local LLM-powered lead generation system
    Uses Ollama for processing without external API calls
    """

    def __init__(self, model_name: str = None):
        # Load configuration from environment
        self.model_name = model_name or os.getenv('OLLAMA_MODEL', 'mistral:latest')
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.min_effectiveness = float(os.getenv('MIN_EFFECTIVENESS_SCORE', '0.7'))
        self.lead_count_min = int(os.getenv('LEAD_COUNT_MIN', '40'))
        self.lead_count_max = int(os.getenv('LEAD_COUNT_MAX', '50'))
        self.output_dir = Path(os.getenv('OUTPUT_DIR', './output'))

        # Initialize Ollama client
        self.client = ollama.Client(host=self.ollama_host)

        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True)

        logger.info(f"Initialized Local LLM Lead Generator")
        logger.info(f"Model: {self.model_name}, Host: {self.ollama_host}")
        logger.info(f"Target leads: {self.lead_count_min}-{self.lead_count_max}")

    def health_check(self) -> Dict[str, bool]:
        """
        Check if Ollama and model are available
        """
        checks = {
            'ollama_running': False,
            'model_available': False,
            'output_dir_writable': False
        }

        try:
            # Check Ollama connection
            models = self.client.list()
            checks['ollama_running'] = True

            # Check if our model is available
            model_names = [m['name'] for m in models['models']]
            checks['model_available'] = self.model_name in model_names

            # Check output directory
            test_file = self.output_dir / 'test_write.tmp'
            test_file.write_text('test')
            test_file.unlink()
            checks['output_dir_writable'] = True

        except Exception as e:
            logger.error(f"Health check failed: {e}")

        return checks

    def generate_leads_with_retry(self, raw_data: List[Dict[str, Any]],
                                max_retries: int = 3) -> LeadGenerationResult:
        """
        Generate leads from raw data with retry logic
        Implements retry mechanism as per setup instructions
        """
        start_time = time.time()

        for attempt in range(max_retries):
            try:
                logger.info(f"Lead generation attempt {attempt + 1}/{max_retries}")

                result = self._generate_leads_batch(raw_data)

                # Validate result meets criteria
                if self._validate_generation_result(result):
                    duration = time.time() - start_time
                    result.duration_seconds = duration

                    logger.info(f"✅ Lead generation successful on attempt {attempt + 1}")
                    logger.info(f"Generated {result.total_qualified} qualified leads in {duration:.1f}s")

                    return result
                else:
                    logger.warning(f"Attempt {attempt + 1} did not meet criteria, retrying...")

            except Exception as e:
                logger.error(f"Lead generation error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        # If all retries failed
        duration = time.time() - start_time
        logger.error(f"❌ Lead generation failed after {max_retries} attempts")

        return LeadGenerationResult(
            total_discovered=len(raw_data),
            total_validated=0,
            total_qualified=0,
            success_rate=0.0,
            duration_seconds=duration,
            leads=[]
        )

    def _generate_leads_batch(self, raw_data: List[Dict[str, Any]]) -> LeadGenerationResult:
        """
        Process raw data and generate qualified leads
        """
        logger.info(f"Processing {len(raw_data)} raw business records...")

        generated_leads = []
        validated_count = 0

        # Process in batches for memory efficiency
        batch_size = 10
        total_batches = (len(raw_data) + batch_size - 1) // batch_size

        for batch_idx in range(0, len(raw_data), batch_size):
            batch = raw_data[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            for business_data in batch:
                try:
                    lead = self._process_business_data(business_data)

                    if lead:
                        # Validate the lead
                        if self._validate_lead_criteria(lead):
                            validated_count += 1
                            generated_leads.append(lead)

                except Exception as e:
                    logger.error(f"Error processing business {business_data.get('name', 'unknown')}: {e}")
                    continue

        # Calculate qualified leads (those meeting all criteria)
        qualified_leads = [lead for lead in generated_leads if lead.get('qualified', False)]

        success_rate = len(qualified_leads) / len(raw_data) if raw_data else 0

        return LeadGenerationResult(
            total_discovered=len(raw_data),
            total_validated=validated_count,
            total_qualified=len(qualified_leads),
            success_rate=success_rate,
            duration_seconds=0,  # Will be set by caller
            leads=qualified_leads
        )

    def _process_business_data(self, business_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process individual business data using local LLM
        """
        # Create structured prompt for lead analysis
        analysis_prompt = f"""
        Analyze the following business data and determine if it meets our criteria for a qualified lead.

        BUSINESS DATA:
        {json.dumps(business_data, indent=2)}

        CRITERIA:
        - Revenue between $1-2M annually
        - Operating for 15+ years
        - Single location only
        - Located in Hamilton, ON
        - Established business (not startup)

        Please respond with ONLY valid JSON in this exact format:
        {{
            "business_name": "exact business name",
            "address": "full address",
            "industry": "industry category",
            "estimated_revenue": revenue_as_number,
            "years_in_business": years_as_number,
            "employee_count": estimated_employees,
            "website": "website_url_or_null",
            "phone": "phone_number_or_null",
            "qualified": true_or_false,
            "qualification_reason": "brief explanation",
            "confidence_score": 0.0_to_1.0
        }}

        IMPORTANT:
        - Only use information explicitly provided in the business data
        - Do not invent or assume any information
        - Set qualified=false if any criteria are not met or unclear
        - Be conservative with estimates
        """

        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=analysis_prompt,
                options={
                    'temperature': 0.1,  # Low temperature for consistency
                    'num_predict': 500,  # Limit response length
                }
            )

            # Parse the response
            response_text = response['response'].strip()

            # Extract JSON from response
            if '```json' in response_text:
                json_part = response_text.split('```json')[1].split('```')[0]
            elif '{' in response_text:
                # Find the JSON object
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                json_part = response_text[start:end]
            else:
                logger.warning(f"No JSON found in response for {business_data.get('name', 'unknown')}")
                return None

            lead_data = json.loads(json_part)

            # Add metadata
            lead_data['processed_at'] = datetime.now().isoformat()
            lead_data['source_data'] = business_data
            lead_data['model_used'] = self.model_name

            return lead_data

        except Exception as e:
            logger.error(f"Error processing business data with LLM: {e}")
            return None

    def _validate_lead_criteria(self, lead: Dict[str, Any]) -> bool:
        """
        Validate that a lead meets our basic criteria
        """
        try:
            # Check required fields
            required_fields = ['business_name', 'qualified', 'confidence_score']
            if not all(field in lead for field in required_fields):
                return False

            # Check confidence threshold
            if lead.get('confidence_score', 0) < 0.5:
                return False

            # Check if marked as qualified
            if not lead.get('qualified', False):
                return False

            # Additional business logic validation
            revenue = lead.get('estimated_revenue', 0)
            years = lead.get('years_in_business', 0)

            # Revenue should be in target range
            if revenue and (revenue < 1000000 or revenue > 2000000):
                return False

            # Should be established business
            if years and years < 15:
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating lead criteria: {e}")
            return False

    def _validate_generation_result(self, result: LeadGenerationResult) -> bool:
        """
        Validate that generation result meets effectiveness criteria
        """
        # Check if we have minimum number of leads
        if result.total_qualified < self.lead_count_min:
            logger.warning(f"Only {result.total_qualified} qualified leads, need at least {self.lead_count_min}")
            return False

        # Check effectiveness rate
        if result.success_rate < self.min_effectiveness:
            logger.warning(f"Success rate {result.success_rate:.1%} below threshold {self.min_effectiveness:.1%}")
            return False

        return True

    def export_to_sheets_format(self, leads: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Export leads to Google Sheets compatible format
        """
        if not leads:
            return pd.DataFrame()

        # Normalize lead data for export
        export_data = []

        for lead in leads:
            export_row = {
                'Business Name': lead.get('business_name', ''),
                'Address': lead.get('address', ''),
                'Industry': lead.get('industry', ''),
                'Estimated Revenue': lead.get('estimated_revenue', ''),
                'Years in Business': lead.get('years_in_business', ''),
                'Employee Count': lead.get('employee_count', ''),
                'Website': lead.get('website', ''),
                'Phone': lead.get('phone', ''),
                'Qualified': lead.get('qualified', False),
                'Confidence Score': lead.get('confidence_score', 0),
                'Qualification Reason': lead.get('qualification_reason', ''),
                'Processed At': lead.get('processed_at', ''),
                'Model Used': lead.get('model_used', '')
            }
            export_data.append(export_row)

        df = pd.DataFrame(export_data)

        # Sort by confidence score descending
        df = df.sort_values('Confidence Score', ascending=False)

        return df

    def save_results(self, result: LeadGenerationResult,
                    filename_prefix: str = "local_leads") -> Path:
        """
        Save generation results to CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.csv"
        filepath = self.output_dir / filename

        # Convert to DataFrame and save
        df = self.export_to_sheets_format(result.leads)
        df.to_csv(filepath, index=False)

        # Save summary info
        summary = {
            'generation_summary': {
                'total_discovered': result.total_discovered,
                'total_validated': result.total_validated,
                'total_qualified': result.total_qualified,
                'success_rate': result.success_rate,
                'duration_seconds': result.duration_seconds,
                'generated_at': datetime.now().isoformat(),
                'model_used': self.model_name
            }
        }

        summary_file = self.output_dir / f"{filename_prefix}_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Results saved to {filepath}")
        logger.info(f"Summary saved to {summary_file}")

        return filepath

def main():
    """Example usage of Local LLM Lead Generator"""

    # Initialize generator
    generator = LocalLLMLeadGenerator()

    # Perform health check
    health = generator.health_check()
    logger.info(f"Health check: {health}")

    if not all(health.values()):
        logger.error("Health check failed. Please verify setup:")
        for check, status in health.items():
            if not status:
                logger.error(f"  ❌ {check}")
        return

    # Sample raw data (would normally come from web scraping)
    sample_raw_data = [
        {
            "name": "Hamilton Manufacturing Co",
            "address": "123 Industrial Way, Hamilton, ON",
            "industry": "Manufacturing",
            "phone": "905-555-0123",
            "website": "www.hamiltonmfg.com",
            "description": "Established steel fabrication company serving Ontario since 1995"
        },
        {
            "name": "Citywide Auto Repair",
            "address": "456 Main St, Hamilton, ON",
            "industry": "Automotive",
            "phone": "905-555-0456",
            "description": "Family-owned auto repair shop, 25 years in business"
        },
        {
            "name": "TechStart Inc",
            "address": "789 Innovation Dr, Hamilton, ON",
            "industry": "Technology",
            "website": "www.techstart.ca",
            "description": "Software development startup founded in 2020"
        }
    ]

    # Generate leads
    logger.info("Starting lead generation...")
    result = generator.generate_leads_with_retry(sample_raw_data)

    # Save results
    output_file = generator.save_results(result)

    # Print summary
    print(f"\\n{'='*50}")
    print(f"LEAD GENERATION COMPLETE")
    print(f"{'='*50}")
    print(f"📊 Discovered: {result.total_discovered} businesses")
    print(f"✅ Validated: {result.total_validated} leads")
    print(f"🎯 Qualified: {result.total_qualified} leads")
    print(f"📈 Success Rate: {result.success_rate:.1%}")
    print(f"⏱️  Duration: {result.duration_seconds:.1f} seconds")
    print(f"💾 Saved to: {output_file}")

    if result.total_qualified > 0:
        print(f"\\n🎉 Successfully generated {result.total_qualified} qualified leads!")
    else:
        print(f"\\n⚠️  No qualified leads generated. Consider:")
        print(f"  - Adjusting criteria")
        print(f"  - Improving data sources")
        print(f"  - Reviewing model prompts")

if __name__ == "__main__":
    main()