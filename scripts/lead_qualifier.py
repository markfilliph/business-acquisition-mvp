#!/usr/bin/env python3
"""
Lead Qualifier and Generator
Ensures you get exactly N qualified leads by continuously fetching until quota is met
Integrates with existing Google Sheets CRM workflow

Usage:
    python scripts/lead_qualifier.py --target 30
    python scripts/lead_qualifier.py --input data/raw_leads.csv --target 30
"""

import os
import sys
import pandas as pd
import argparse
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class LeadQualificationCriteria:
    """Define target market criteria for Hamilton, ON businesses"""
    
    def __init__(self, 
                 max_employees: int = 30,
                 min_employees: int = 1,
                 min_revenue: int = 250000,
                 max_revenue: int = 2000000,
                 min_years: int = 15,
                 single_location: bool = True):
        
        self.max_employees = max_employees
        self.min_employees = min_employees
        self.min_revenue = min_revenue
        self.max_revenue = max_revenue
        self.min_years = min_years
        self.single_location = single_location
        
        # Required fields for a valid lead
        self.required_fields = ['Company Name', 'Website', 'Phone']
        
        # Industries to exclude (too capital intensive or wrong fit)
        self.excluded_industries = [
            'Steel Manufacturing',
            'Food Processing',
            'Railway Car Manufacturing'
        ]


class LeadQualifier:
    """
    Qualify and enrich leads based on acquisition criteria
    Integrates with your existing Google Sheets CRM workflow
    """
    
    def __init__(self, criteria: LeadQualificationCriteria):
        self.criteria = criteria
        
        # Track statistics
        self.stats = {
            'total_processed': 0,
            'qualified': 0,
            'excluded_employee_count': 0,
            'excluded_revenue': 0,
            'excluded_missing_data': 0,
            'excluded_website': 0,
            'excluded_industry': 0,
            'enriched': 0
        }
    
    def qualify_lead(self, lead: Dict) -> Tuple[bool, str, Dict]:
        """
        Qualify a single lead and enrich if needed
        
        Returns:
            (is_qualified, exclusion_reason, enriched_lead)
        """
        
        self.stats['total_processed'] += 1
        
        # Stage 1: Check required fields
        for field in self.criteria.required_fields:
            field_value = lead.get(field, '').strip()
            if not field_value or field_value == '':
                self.stats['excluded_missing_data'] += 1
                return False, f"Missing required field: {field}", lead
        
        # Stage 2: Validate website
        website = lead.get('Website', '')
        if not self._is_valid_website(website):
            self.stats['excluded_website'] += 1
            return False, "Invalid or parked website", lead
        
        # Stage 3: Check industry exclusions
        industry = lead.get('Industry', '')
        if self._is_excluded_industry(industry):
            self.stats['excluded_industry'] += 1
            return False, f"Excluded industry: {industry}", lead
        
        # Stage 4: Get or estimate employee count
        employee_count = lead.get('Employee Count')
        
        if not employee_count or employee_count == '':
            # Try to estimate from revenue
            employee_count = self._estimate_from_revenue(lead)
            
            if employee_count:
                lead['Employee Count'] = employee_count
                lead['Employee Count Source'] = 'estimated_from_revenue'
                self.stats['enriched'] += 1
            else:
                # Try industry-based estimation
                employee_count = self._estimate_from_industry(lead)
                if employee_count:
                    lead['Employee Count'] = employee_count
                    lead['Employee Count Source'] = 'estimated_from_industry'
                    self.stats['enriched'] += 1
        
        # Validate employee count
        if not employee_count:
            self.stats['excluded_missing_data'] += 1
            return False, "Cannot determine employee count", lead
        
        try:
            emp_count = int(str(employee_count).replace(',', ''))
            
            if emp_count > self.criteria.max_employees:
                self.stats['excluded_employee_count'] += 1
                return False, f"Too many employees ({emp_count} > {self.criteria.max_employees})", lead
            
            if emp_count < self.criteria.min_employees:
                self.stats['excluded_employee_count'] += 1
                return False, f"Too few employees ({emp_count} < {self.criteria.min_employees})", lead
            
            lead['Employee Count'] = emp_count
        
        except (ValueError, TypeError):
            self.stats['excluded_missing_data'] += 1
            return False, "Invalid employee count format", lead
        
        # Stage 5: Calculate or validate revenue
        revenue = lead.get('Revenue Estimate (Employees × $50k)')
        
        if not revenue or revenue == '':
            # Calculate revenue estimate
            revenue = emp_count * 50000
            lead['Revenue Estimate (Employees × $50k)'] = f"${revenue:,}"
            lead['Revenue Source'] = 'calculated'
        else:
            # Parse existing revenue
            try:
                revenue_value = int(str(revenue).replace('$', '').replace(',', ''))
                lead['Revenue Estimate (Employees × $50k)'] = f"${revenue_value:,}"
                revenue = revenue_value
            except:
                revenue = emp_count * 50000
                lead['Revenue Estimate (Employees × $50k)'] = f"${revenue:,}"
                lead['Revenue Source'] = 'calculated'
        
        # Validate revenue range
        if self.criteria.min_revenue and revenue < self.criteria.min_revenue:
            self.stats['excluded_revenue'] += 1
            return False, f"Revenue too low (${revenue:,} < ${self.criteria.min_revenue:,})", lead
        
        if self.criteria.max_revenue and revenue > self.criteria.max_revenue:
            self.stats['excluded_revenue'] += 1
            return False, f"Revenue too high (${revenue:,} > ${self.criteria.max_revenue:,})", lead
        
        # Stage 6: Set status and timestamp
        lead['Status'] = 'QUALIFIED'
        lead['Qualified Date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lead['Exclusion Reason'] = ''
        
        self.stats['qualified'] += 1
        return True, '', lead
    
    def _is_valid_website(self, website: str) -> bool:
        """Check if website is valid and not parked"""
        
        if not website:
            return False
        
        # Must have proper URL format
        if not re.match(r'https?://', website):
            return False
        
        # Check for parked domain indicators
        parked_domains = [
            'godaddy.com',
            'parkingcrew.net',
            'sedoparking.com',
            'bodis.com',
            'parked-content.godaddy.com'
        ]
        
        website_lower = website.lower()
        for parked in parked_domains:
            if parked in website_lower:
                return False
        
        return True
    
    def _is_excluded_industry(self, industry: str) -> bool:
        """Check if industry is in exclusion list"""
        
        if not industry:
            return False
        
        industry_lower = industry.lower()
        for excluded in self.criteria.excluded_industries:
            if excluded.lower() in industry_lower:
                return True
        
        return False
    
    def _estimate_from_revenue(self, lead: Dict) -> Optional[int]:
        """Estimate employees from revenue"""
        
        revenue_str = lead.get('Revenue Estimate (Employees × $50k)', '')
        
        if not revenue_str:
            return None
        
        try:
            revenue = int(str(revenue_str).replace('$', '').replace(',', ''))
            estimated_employees = revenue // 50000
            
            # Sanity check
            if 1 <= estimated_employees <= 100:
                return estimated_employees
        except:
            pass
        
        return None
    
    def _estimate_from_industry(self, lead: Dict) -> Optional[int]:
        """Estimate employees based on industry averages"""
        
        industry = lead.get('Industry', '').lower()
        
        # Industry-specific average employee counts for small businesses
        industry_averages = {
            'manufacturing': 18,
            'machining': 15,
            'fabrication': 20,
            'metal': 18,
            'automotive': 15,
            'tool': 12,
            'die': 12,
            'steel': 25,
            'consulting': 8,
            'engineering': 12,
            'services': 10,
            'wholesale': 14,
            'distribution': 16,
            'retail': 12,
            'restaurant': 10
        }
        
        for keyword, avg in industry_averages.items():
            if keyword in industry:
                return avg
        
        # Default conservative estimate
        return 15
    
    def print_statistics(self):
        """Print qualification statistics"""
        
        print(f"\n{'='*70}")
        print(f"📊 QUALIFICATION STATISTICS")
        print(f"{'='*70}")
        print(f"Total Processed:        {self.stats['total_processed']}")
        print(f"✅ Qualified:           {self.stats['qualified']} "
              f"({self.stats['qualified']/max(self.stats['total_processed'],1)*100:.1f}%)")
        print(f"\n❌ Exclusion Breakdown:")
        print(f"   Employee count:      {self.stats['excluded_employee_count']}")
        print(f"   Revenue range:       {self.stats['excluded_revenue']}")
        print(f"   Missing data:        {self.stats['excluded_missing_data']}")
        print(f"   Invalid website:     {self.stats['excluded_website']}")
        print(f"   Excluded industry:   {self.stats['excluded_industry']}")
        print(f"\n🔧 Enriched:            {self.stats['enriched']}")
        print(f"{'='*70}\n")


class LeadGenerator:
    """
    Main orchestrator for lead generation
    Fetches until target quota is met
    """
    
    def __init__(self, criteria: LeadQualificationCriteria):
        self.criteria = criteria
        self.qualifier = LeadQualifier(criteria)
    
    def generate_from_csv(self, 
                         input_file: str,
                         target_count: int,
                         output_file: str = None) -> pd.DataFrame:
        """
        Process existing CSV and generate qualified leads
        
        Args:
            input_file: Path to input CSV with raw leads
            target_count: Number of qualified leads needed
            output_file: Optional output CSV path
        
        Returns:
            DataFrame with qualified leads
        """
        
        print(f"\n{'='*70}")
        print(f"🎯 LEAD QUALIFICATION PROCESS")
        print(f"{'='*70}")
        print(f"📂 Input:       {input_file}")
        print(f"🎯 Target:      {target_count} qualified leads")
        print(f"👥 Max employees: {self.criteria.max_employees}")
        print(f"💰 Revenue:     ${self.criteria.min_revenue:,} - ${self.criteria.max_revenue:,}")
        print(f"{'='*70}\n")
        
        # Load raw leads
        try:
            df = pd.read_csv(input_file)
            print(f"📦 Loaded {len(df)} raw leads from CSV\n")
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            return pd.DataFrame()
        
        # Process leads
        qualified_leads = []
        excluded_leads = []
        
        print(f"Processing leads...\n")
        
        for idx, row in df.iterrows():
            lead = row.to_dict()
            
            # Qualify lead
            is_qualified, reason, enriched_lead = self.qualifier.qualify_lead(lead)
            
            if is_qualified:
                qualified_leads.append(enriched_lead)
                company = enriched_lead.get('Company Name', 'Unknown')
                emp_count = enriched_lead.get('Employee Count', '?')
                print(f"✅ {len(qualified_leads):3d}. {company:<45} ({emp_count} employees)")
                
                # Stop if we reached target
                if len(qualified_leads) >= target_count:
                    print(f"\n🎯 Target reached! ({len(qualified_leads)}/{target_count})")
                    break
            else:
                enriched_lead['Status'] = 'EXCLUDED'
                enriched_lead['Exclusion Reason'] = reason
                excluded_leads.append(enriched_lead)
                
                company = lead.get('Company Name', 'Unknown')
                print(f"❌ {company:<45} - {reason}")
        
        # Print statistics
        self.qualifier.print_statistics()
        
        # Create DataFrames
        qualified_df = pd.DataFrame(qualified_leads)
        excluded_df = pd.DataFrame(excluded_leads)
        
        # Save results
        if output_file:
            qualified_df.to_csv(output_file, index=False)
            print(f"💾 Saved {len(qualified_df)} qualified leads to: {output_file}")
            
            # Save excluded leads for review
            excluded_file = output_file.replace('.csv', '_excluded.csv')
            excluded_df.to_csv(excluded_file, index=False)
            print(f"💾 Saved {len(excluded_df)} excluded leads to: {excluded_file}")
        
        # Warning if target not met
        if len(qualified_leads) < target_count:
            shortfall = target_count - len(qualified_leads)
            print(f"\n⚠️  WARNING: Only found {len(qualified_leads)}/{target_count} qualified leads")
            print(f"   Missing: {shortfall} leads")
            print(f"\n💡 Suggestions:")
            print(f"   • Expand search area beyond Hamilton, ON")
            print(f"   • Consider nearby cities (Burlington, Oakville, Mississauga)")
            print(f"   • Relax employee count to {self.criteria.max_employees + 10}")
            print(f"   • Include more industries")
        
        return qualified_df
    
    def generate_batch_until_quota(self,
                                   fetch_function,
                                   target_count: int,
                                   max_batches: int = 10) -> pd.DataFrame:
        """
        Keep fetching batches until we have enough qualified leads
        
        Args:
            fetch_function: Function that returns a batch of raw leads
            target_count: Number of qualified leads needed
            max_batches: Maximum fetch attempts
        
        Returns:
            DataFrame with qualified leads
        """
        
        qualified_leads = []
        batch_num = 0
        
        print(f"\n{'='*70}")
        print(f"🎯 GENERATING {target_count} QUALIFIED LEADS")
        print(f"{'='*70}\n")
        
        while len(qualified_leads) < target_count and batch_num < max_batches:
            batch_num += 1
            
            print(f"\n📦 BATCH #{batch_num}")
            print("-" * 70)
            
            # Fetch batch
            try:
                raw_batch = fetch_function(batch_num)
                
                if not raw_batch or len(raw_batch) == 0:
                    print("⚠️  No more leads available")
                    break
                
                print(f"Fetched {len(raw_batch)} raw leads")
            
            except Exception as e:
                print(f"❌ Error fetching batch: {e}")
                break
            
            # Qualify batch
            batch_qualified = 0
            for lead in raw_batch:
                is_qualified, reason, enriched_lead = self.qualifier.qualify_lead(lead)
                
                if is_qualified:
                    qualified_leads.append(enriched_lead)
                    batch_qualified += 1
                    
                    company = enriched_lead.get('Company Name', 'Unknown')
                    print(f"✅ {company}")
                    
                    if len(qualified_leads) >= target_count:
                        break
            
            print(f"\nBatch result: +{batch_qualified} qualified")
            print(f"Progress: {len(qualified_leads)}/{target_count}")
        
        # Print final statistics
        self.qualifier.print_statistics()
        
        return pd.DataFrame(qualified_leads)


def main():
    """Command-line interface"""
    
    parser = argparse.ArgumentParser(
        description='Qualify and filter business leads for acquisition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process existing CSV and get 30 qualified leads
  python scripts/lead_qualifier.py --input data/hamilton_leads.csv --target 30
  
  # Process with custom criteria
  python scripts/lead_qualifier.py --input data/leads.csv --target 40 --max-employees 50
  
  # Save to specific output file
  python scripts/lead_qualifier.py --input data/leads.csv --output data/qualified.csv
        """
    )
    
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input CSV file with raw leads'
    )
    
    parser.add_argument(
        '--target',
        type=int,
        default=30,
        help='Number of qualified leads needed (default: 30)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Output CSV file for qualified leads (default: data/qualified_leads.csv)'
    )
    
    parser.add_argument(
        '--max-employees',
        type=int,
        default=30,
        help='Maximum employee count (default: 30)'
    )
    
    parser.add_argument(
        '--min-employees',
        type=int,
        default=1,
        help='Minimum employee count (default: 1)'
    )
    
    parser.add_argument(
        '--min-revenue',
        type=int,
        default=250000,
        help='Minimum revenue (default: 250000)'
    )
    
    parser.add_argument(
        '--max-revenue',
        type=int,
        default=2000000,
        help='Maximum revenue (default: 2000000)'
    )
    
    args = parser.parse_args()
    
    # Set output file
    if not args.output:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = f'data/qualified_leads_{timestamp}.csv'
    
    # Create criteria
    criteria = LeadQualificationCriteria(
        max_employees=args.max_employees,
        min_employees=args.min_employees,
        min_revenue=args.min_revenue,
        max_revenue=args.max_revenue
    )
    
    # Generate qualified leads
    generator = LeadGenerator(criteria)
    qualified_df = generator.generate_from_csv(
        input_file=args.input,
        target_count=args.target,
        output_file=args.output
    )
    
    # Summary
    if not qualified_df.empty:
        print(f"\n✨ SUCCESS!")
        print(f"📊 Generated {len(qualified_df)} qualified leads")
        print(f"📂 Output: {args.output}")
        print(f"\n🚀 Next steps:")
        print(f"   1. Review qualified leads in {args.output}")
        print(f"   2. Run: python scripts/prospects_tracker.py")
        print(f"   3. Continue with email generation\n")
    else:
        print(f"\n❌ No qualified leads generated")
        print(f"   Check your input file and criteria\n")


if __name__ == "__main__":
    main()
