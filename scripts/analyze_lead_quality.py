#!/usr/bin/env python3
"""
Lead Quality Analyzer - Identifies non-acquisition targets in lead list
Detects: franchises, chains, non-profits, government orgs, unsuitable business types
"""
import pandas as pd
import re
from pathlib import Path
from typing import Dict, List

class LeadQualityAnalyzer:
    """Analyzes leads and flags non-acquisition targets"""

    # Non-profit/Government indicators
    NON_PROFIT_KEYWORDS = [
        'bia', 'business improvement', 'chamber', 'association',
        'foundation', 'charity', 'non-profit', 'nonprofit',
        'society', 'club', 'organization', 'institute'
    ]

    # Franchise/Chain indicators
    FRANCHISE_KEYWORDS = [
        'franchise', 'corporate', 'inc.', 'corporation',
        'ltd', 'limited', 'llc', 'group'
    ]

    # URL patterns suggesting multi-location/corporate
    MULTI_LOCATION_URL_PATTERNS = [
        r'/locations?/',
        r'/find-us/',
        r'/stores?/',
        r'/branches?/',
        r'\.com/[a-z]{2}/',  # Language/country codes
    ]

    # Unsuitable business types for acquisition
    UNSUITABLE_TYPES = {
        'private_club': ['club', 'lodge', 'society'],
        'restaurant_chain': ['restaurant', 'bar', 'pub', 'grill', 'cafe'],
        'retail_chain': ['store', 'shop', 'retail', 'outlet'],
        'skilled_trades': ['welding', 'machining', 'construction', 'electrical', 'plumbing', 'hvac'],
    }

    def analyze_business_name(self, name: str) -> Dict:
        """Analyze business name for red flags"""
        name_lower = name.lower()
        issues = []

        # Check for non-profit indicators
        for keyword in self.NON_PROFIT_KEYWORDS:
            if keyword in name_lower:
                issues.append(f"NON_PROFIT: Contains '{keyword}'")

        # Check for unsuitable types
        for category, keywords in self.UNSUITABLE_TYPES.items():
            for keyword in keywords:
                if keyword in name_lower:
                    issues.append(f"{category.upper()}: Contains '{keyword}'")

        return {
            'has_issues': len(issues) > 0,
            'issues': issues
        }

    def analyze_website(self, website: str) -> Dict:
        """Analyze website URL for multi-location/franchise indicators"""
        if pd.isna(website) or website == '':
            return {'has_issues': False, 'issues': []}

        website_lower = website.lower()
        issues = []

        # Check for multi-location URL patterns
        for pattern in self.MULTI_LOCATION_URL_PATTERNS:
            if re.search(pattern, website_lower):
                issues.append(f"MULTI_LOCATION: URL contains '{pattern}'")

        # Check for corporate domain patterns
        if re.search(r'\.(com|net|org)/[a-z]{2}/', website_lower):
            issues.append("CORPORATE: Multi-language/region site")

        return {
            'has_issues': len(issues) > 0,
            'issues': issues
        }

    def check_industry_suitability(self, industry: str, business_name: str) -> Dict:
        """Check if industry is suitable for acquisition"""
        if pd.isna(industry):
            return {'suitable': True, 'reason': 'Unknown industry'}

        industry_lower = industry.lower()
        name_lower = business_name.lower()

        # Wholesale/distribution = GOOD
        if 'wholesale' in industry_lower or 'distribution' in industry_lower:
            return {'suitable': True, 'reason': 'Wholesale/Distribution (target industry)'}

        # Manufacturing = GOOD
        if 'manufacturing' in industry_lower or 'manufacturer' in industry_lower:
            return {'suitable': True, 'reason': 'Manufacturing (target industry)'}

        # Professional services = GOOD
        if 'professional' in industry_lower or 'service' in industry_lower:
            # But not skilled trades
            skilled_trades = ['welding', 'machining', 'construction', 'electrical', 'plumbing']
            if any(trade in name_lower for trade in skilled_trades):
                return {'suitable': False, 'reason': 'Skilled trades (excluded)'}
            return {'suitable': True, 'reason': 'Professional services'}

        # Restaurants = RISKY (high failure rate, complex)
        if any(word in name_lower for word in ['restaurant', 'cafe', 'bar', 'pub', 'grill']):
            return {'suitable': False, 'reason': 'Restaurant (high risk, complex operations)'}

        # Retail = RISKY (changing landscape)
        if 'retail' in industry_lower or any(word in name_lower for word in ['store', 'shop', 'outlet']):
            return {'suitable': False, 'reason': 'Retail (challenging industry)'}

        return {'suitable': True, 'reason': 'General business'}

    def analyze_lead(self, row: pd.Series) -> Dict:
        """Comprehensive lead analysis"""
        business_name = row.get('Business Name', '')
        website = row.get('Website', '')
        industry = row.get('Industry', '')

        # Run all checks
        name_analysis = self.analyze_business_name(business_name)
        website_analysis = self.analyze_website(website)
        industry_analysis = self.check_industry_suitability(industry, business_name)

        all_issues = name_analysis['issues'] + website_analysis['issues']

        if not industry_analysis['suitable']:
            all_issues.append(f"INDUSTRY: {industry_analysis['reason']}")

        # Determine verdict
        if len(all_issues) > 0:
            verdict = 'REJECT'
            confidence = 'HIGH' if len(all_issues) >= 2 else 'MEDIUM'
        else:
            verdict = 'ACCEPT'
            confidence = 'MEDIUM'  # Still needs manual verification

        return {
            'business_name': business_name,
            'verdict': verdict,
            'confidence': confidence,
            'issues': all_issues,
            'issue_count': len(all_issues)
        }


def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print(f"LEAD QUALITY ANALYSIS")
    print(f"{'='*80}")
    print(f"Analyzing leads for non-acquisition targets...\n")

    data_dir = Path(__file__).parent.parent / 'data'

    # Find input file
    candidate_files = [
        'FINAL_15_QUALIFIED_LEADS_IMPROVED_REVENUE.csv',
        'FINAL_15_QUALIFIED_LEADS_FILTERED_20251016_223230.csv',
    ]

    input_file = None
    for filename in candidate_files:
        candidate = data_dir / filename
        if candidate.exists():
            input_file = candidate
            break

    if not input_file:
        print("ERROR: No qualified leads CSV found")
        return

    print(f"Reading: {input_file.name}\n")
    df = pd.read_csv(input_file)

    analyzer = LeadQualityAnalyzer()

    # Analyze each lead
    results = []
    for idx, row in df.iterrows():
        analysis = analyzer.analyze_lead(row)
        analysis['rank'] = row.get('Rank', idx + 1)
        analysis['website'] = row.get('Website', '')
        analysis['industry'] = row.get('Industry', '')
        results.append(analysis)

    # Print results
    print(f"{'='*80}")
    print(f"ANALYSIS RESULTS")
    print(f"{'='*80}\n")

    rejected = [r for r in results if r['verdict'] == 'REJECT']
    accepted = [r for r in results if r['verdict'] == 'ACCEPT']

    print(f"✅ ACCEPTED: {len(accepted)} leads")
    print(f"❌ REJECTED: {len(rejected)} leads")

    print(f"\n{'='*80}")
    print(f"REJECTED LEADS (Non-Acquisition Targets)")
    print(f"{'='*80}\n")

    for result in rejected:
        print(f"❌ Rank {result['rank']}: {result['business_name']}")
        print(f"   Industry: {result['industry']}")
        print(f"   Website: {result['website']}")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Issues:")
        for issue in result['issues']:
            print(f"      • {issue}")
        print()

    print(f"{'='*80}")
    print(f"ACCEPTED LEADS (Potential Acquisition Targets)")
    print(f"{'='*80}\n")

    for result in accepted:
        print(f"✅ Rank {result['rank']}: {result['business_name']}")
        print(f"   Industry: {result['industry']}")
        print(f"   Website: {result['website']}")
        print()

    # Save results
    results_df = pd.DataFrame(results)
    output_file = data_dir / 'LEAD_QUALITY_ANALYSIS.csv'
    results_df.to_csv(output_file, index=False)

    print(f"{'='*80}")
    print(f"✅ Saved analysis to: {output_file}")
    print(f"{'='*80}\n")

    # Summary statistics
    print(f"SUMMARY:")
    print(f"  • Total leads analyzed: {len(results)}")
    print(f"  • Accepted (potential targets): {len(accepted)} ({len(accepted)/len(results)*100:.1f}%)")
    print(f"  • Rejected (non-targets): {len(rejected)} ({len(rejected)/len(results)*100:.1f}%)")
    print(f"\n⚠️  WARNING: Only {len(accepted)} out of {len(results)} leads are viable acquisition targets!")
    print(f"\nRECOMMENDATION:")
    print(f"  1. Review rejected leads manually to confirm")
    print(f"  2. Improve lead source filters to avoid non-profits, chains, restaurants")
    print(f"  3. Add new data sources focused on wholesale/manufacturing/services")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
