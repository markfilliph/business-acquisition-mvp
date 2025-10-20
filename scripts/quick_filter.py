#!/usr/bin/env python3
"""
Quick Filter - Apply STRICT qualification criteria to leads
Filters: revenue_max <= $1.5M, years >= 15, employees <= 30
"""
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# Configuration
STRICT_REVENUE_MAX = 1_500_000  # $1.5M hard ceiling
MIN_YEARS_IN_BUSINESS = 15
MAX_EMPLOYEES = 30

# Industries to EXCLUDE (skilled trades that require special licensing)
EXCLUDED_INDUSTRIES = {
    'welding', 'machining', 'construction', 'electrical', 'plumbing',
    'hvac', 'roofing', 'landscaping', 'carpentry', 'masonry',
    'painting', 'drywall', 'flooring', 'concrete', 'excavation'
}

def parse_currency(value):
    """Convert currency string to float"""
    if pd.isna(value) or value == '':
        return None

    # Remove currency symbols and commas
    clean = str(value).replace('$', '').replace(',', '').strip()

    try:
        return float(clean)
    except ValueError:
        return None

def parse_employee_range(emp_range):
    """Parse employee range and return max value"""
    if pd.isna(emp_range) or emp_range == '':
        return None

    emp_str = str(emp_range).strip()

    # Handle ranges like "5-20" or "5-25"
    if '-' in emp_str:
        parts = emp_str.split('-')
        try:
            return int(parts[1])
        except (ValueError, IndexError):
            return None

    # Handle single numbers
    try:
        return int(emp_str)
    except ValueError:
        return None

def is_skilled_trade(industry, business_name):
    """Check if business is in excluded skilled trades"""
    if pd.isna(industry) and pd.isna(business_name):
        return False

    text_to_check = f"{str(industry).lower()} {str(business_name).lower()}"

    for excluded in EXCLUDED_INDUSTRIES:
        if excluded in text_to_check:
            return True

    return False

def apply_strict_filters(input_csv):
    """Apply strict filters and return qualified leads"""

    print(f"\n{'='*80}")
    print(f"STRICT LEAD QUALIFICATION FILTER")
    print(f"{'='*80}")
    print(f"\nCriteria:")
    print(f"  ✓ Revenue Max <= ${STRICT_REVENUE_MAX:,.0f}")
    print(f"  ✓ Years in Business >= {MIN_YEARS_IN_BUSINESS}")
    print(f"  ✓ Max Employees <= {MAX_EMPLOYEES}")
    print(f"  ✓ Exclude Skilled Trades")
    print(f"\nReading: {input_csv}")

    # Read CSV
    df = pd.read_csv(input_csv)
    initial_count = len(df)
    print(f"Initial leads: {initial_count}")

    # Track filter results
    filter_results = {
        'revenue_max': 0,
        'years_in_business': 0,
        'employee_count': 0,
        'skilled_trades': 0,
        'missing_data': 0
    }

    # Parse Revenue Max
    if 'Revenue Max' in df.columns:
        df['Revenue_Max_Parsed'] = df['Revenue Max'].apply(parse_currency)
    else:
        print("WARNING: 'Revenue Max' column not found")
        df['Revenue_Max_Parsed'] = None

    # Parse Years in Business
    if 'Years in Business' in df.columns:
        df['Years_Parsed'] = pd.to_numeric(df['Years in Business'], errors='coerce')
    else:
        print("WARNING: 'Years in Business' column not found")
        df['Years_Parsed'] = None

    # Parse Employee Range
    if 'Employee Range' in df.columns:
        df['Employees_Max_Parsed'] = df['Employee Range'].apply(parse_employee_range)
    else:
        print("WARNING: 'Employee Range' column not found")
        df['Employees_Max_Parsed'] = None

    # Apply filters
    qualified = []
    rejected = []

    for idx, row in df.iterrows():
        business_name = row.get('Business Name', 'Unknown')
        rejection_reasons = []

        # Check Revenue Max (STRICT)
        revenue_max = row['Revenue_Max_Parsed']
        if pd.isna(revenue_max):
            rejection_reasons.append("Missing revenue data")
            filter_results['missing_data'] += 1
        elif revenue_max > STRICT_REVENUE_MAX:
            rejection_reasons.append(f"Revenue max ${revenue_max:,.0f} > ${STRICT_REVENUE_MAX:,.0f}")
            filter_results['revenue_max'] += 1

        # Check Years in Business
        years = row['Years_Parsed']
        if pd.isna(years):
            rejection_reasons.append("Missing years in business")
            filter_results['missing_data'] += 1
        elif years < MIN_YEARS_IN_BUSINESS:
            rejection_reasons.append(f"Years {years:.1f} < {MIN_YEARS_IN_BUSINESS}")
            filter_results['years_in_business'] += 1

        # Check Employee Count
        employees_max = row['Employees_Max_Parsed']
        if pd.isna(employees_max):
            rejection_reasons.append("Missing employee data")
            filter_results['missing_data'] += 1
        elif employees_max > MAX_EMPLOYEES:
            rejection_reasons.append(f"Employees {employees_max} > {MAX_EMPLOYEES}")
            filter_results['employee_count'] += 1

        # Check Skilled Trades
        if is_skilled_trade(row.get('Industry'), business_name):
            rejection_reasons.append("Skilled trade (excluded)")
            filter_results['skilled_trades'] += 1

        # Classify lead
        if rejection_reasons:
            rejected.append({
                'business_name': business_name,
                'reasons': '; '.join(rejection_reasons)
            })
        else:
            qualified.append(row)

    # Create qualified DataFrame
    if qualified:
        qualified_df = pd.DataFrame(qualified)
    else:
        qualified_df = pd.DataFrame()

    # Print results
    print(f"\n{'='*80}")
    print(f"FILTER RESULTS")
    print(f"{'='*80}")
    print(f"\n✅ QUALIFIED: {len(qualified_df)} leads")
    print(f"❌ REJECTED: {len(rejected)} leads")
    print(f"\nRejection Breakdown:")
    print(f"  • Revenue too high: {filter_results['revenue_max']}")
    print(f"  • Too new (< {MIN_YEARS_IN_BUSINESS} years): {filter_results['years_in_business']}")
    print(f"  • Too many employees: {filter_results['employee_count']}")
    print(f"  • Skilled trades: {filter_results['skilled_trades']}")
    print(f"  • Missing data: {filter_results['missing_data']}")

    if len(qualified_df) > 0:
        print(f"\n{'='*80}")
        print(f"TOP QUALIFIED LEADS")
        print(f"{'='*80}")

        for idx, row in qualified_df.head(10).iterrows():
            print(f"\n{idx+1}. {row.get('Business Name', 'Unknown')}")
            print(f"   Industry: {row.get('Industry', 'N/A')}")
            print(f"   Revenue: ${row['Revenue_Max_Parsed']:,.0f} (max)")
            print(f"   Years: {row['Years_Parsed']:.1f}")
            print(f"   Employees: {row.get('Employee Range', 'N/A')}")
            print(f"   Website: {row.get('Website', 'N/A')}")

    return qualified_df, rejected

def main():
    """Main execution"""

    # Find the most recent qualified leads file
    data_dir = Path(__file__).parent.parent / 'data'

    # Check for specific files first
    candidate_files = [
        'FINAL_15_QUALIFIED_LEADS_FILTERED_20251016_223230.csv',
        'FINAL_15_QUALIFIED_LEADS_IMPROVED_REVENUE.csv',
        'FINAL_20_QUALIFIED_LEADS_20251016_220131.csv',
        'google_places_FULLY_ENRICHED.csv'
    ]

    input_file = None
    for filename in candidate_files:
        candidate = data_dir / filename
        if candidate.exists():
            input_file = candidate
            break

    if not input_file:
        print("ERROR: No qualified leads CSV found in data/ directory")
        sys.exit(1)

    # Apply filters
    qualified_df, rejected = apply_strict_filters(input_file)

    # Save results
    if len(qualified_df) > 0:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = data_dir / f'STRICT_QUALIFIED_LEADS_{timestamp}.csv'

        # Drop the temporary parsed columns
        cols_to_drop = ['Revenue_Max_Parsed', 'Years_Parsed', 'Employees_Max_Parsed']
        output_df = qualified_df.drop(columns=[col for col in cols_to_drop if col in qualified_df.columns])

        output_df.to_csv(output_file, index=False)
        print(f"\n✅ Saved {len(qualified_df)} qualified leads to:")
        print(f"   {output_file}")

        # Save rejection log
        rejection_file = data_dir / f'REJECTED_LEADS_{timestamp}.csv'
        if rejected:
            rejected_df = pd.DataFrame(rejected)
            rejected_df.to_csv(rejection_file, index=False)
            print(f"\n📋 Saved rejection log to:")
            print(f"   {rejection_file}")
    else:
        print(f"\n⚠️  NO LEADS QUALIFIED - Try relaxing criteria")

    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    main()
