#!/usr/bin/env python3
"""
Smart Revenue Filter - Handle revenue uncertainty intelligently
Offers multiple filtering strategies:
1. STRICT: Revenue Max <= $1.5M (safest, zero risk)
2. MIDPOINT: Revenue Midpoint <= $1.5M (reasonable, accounts for uncertainty)
3. MIN: Revenue Min <= $1.5M (most aggressive, highest risk)
"""
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# Configuration
TARGET_REVENUE_MAX = 1_500_000  # $1.5M target
MIN_YEARS_IN_BUSINESS = 15
MAX_EMPLOYEES = 30

def parse_currency(value):
    """Convert currency string to float"""
    if pd.isna(value) or value == '':
        return None
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
    if '-' in emp_str:
        parts = emp_str.split('-')
        try:
            return int(parts[1])
        except (ValueError, IndexError):
            return None
    try:
        return int(emp_str)
    except ValueError:
        return None

def analyze_revenue_strategies(input_csv):
    """Compare different revenue filtering strategies"""

    print(f"\n{'='*80}")
    print(f"REVENUE FILTERING STRATEGY ANALYSIS")
    print(f"{'='*80}")
    print(f"Target: Businesses with ~$1M-$1.5M revenue")
    print(f"Challenge: Revenue estimates have ±25-30% uncertainty")
    print(f"\nReading: {input_csv.name}")

    df = pd.read_csv(input_csv)
    print(f"Total leads: {len(df)}")

    # Parse data
    df['Revenue_Min_Parsed'] = df['Revenue Min'].apply(parse_currency)
    df['Revenue_Max_Parsed'] = df['Revenue Max'].apply(parse_currency)
    df['Years_Parsed'] = pd.to_numeric(df['Years in Business'], errors='coerce')
    df['Employees_Max_Parsed'] = df['Employee Range'].apply(parse_employee_range)

    # Calculate midpoint
    df['Revenue_Midpoint'] = (df['Revenue_Min_Parsed'] + df['Revenue_Max_Parsed']) / 2

    # Base filters (non-revenue)
    base_qualified = df[
        (df['Years_Parsed'] >= MIN_YEARS_IN_BUSINESS) &
        (df['Employees_Max_Parsed'] <= MAX_EMPLOYEES)
    ].copy()

    print(f"\nAfter base filters (years >= {MIN_YEARS_IN_BUSINESS}, employees <= {MAX_EMPLOYEES}): {len(base_qualified)}")

    # Strategy 1: STRICT - Revenue Max <= $1.5M
    strict = base_qualified[base_qualified['Revenue_Max_Parsed'] <= TARGET_REVENUE_MAX]

    # Strategy 2: MIDPOINT - Revenue Midpoint <= $1.5M
    midpoint = base_qualified[base_qualified['Revenue_Midpoint'] <= TARGET_REVENUE_MAX]

    # Strategy 3: MIN - Revenue Min <= $1.5M (all pass this)
    min_strategy = base_qualified[base_qualified['Revenue_Min_Parsed'] <= TARGET_REVENUE_MAX]

    print(f"\n{'='*80}")
    print(f"STRATEGY COMPARISON")
    print(f"{'='*80}")
    print(f"\n1. STRICT (Revenue Max <= $1.5M):")
    print(f"   Qualified: {len(strict)} leads")
    print(f"   Risk: ZERO - Guaranteed under $1.5M")
    print(f"   Trade-off: Most conservative, may miss good targets")

    print(f"\n2. MIDPOINT (Revenue Midpoint <= $1.5M):")
    print(f"   Qualified: {len(midpoint)} leads")
    print(f"   Risk: LOW - Statistically likely under $1.5M")
    print(f"   Trade-off: Balanced approach, accounts for estimation uncertainty")

    print(f"\n3. MIN (Revenue Min <= $1.5M):")
    print(f"   Qualified: {len(min_strategy)} leads")
    print(f"   Risk: MEDIUM - Could be over $1.5M")
    print(f"   Trade-off: Most leads, but higher verification needed")

    # Show MIDPOINT qualified leads (recommended)
    if len(midpoint) > 0:
        print(f"\n{'='*80}")
        print(f"RECOMMENDED: MIDPOINT STRATEGY LEADS")
        print(f"{'='*80}")

        for idx, row in midpoint.iterrows():
            rev_min = row['Revenue_Min_Parsed']
            rev_max = row['Revenue_Max_Parsed']
            rev_mid = row['Revenue_Midpoint']

            print(f"\n{row.get('Rank', idx)}. {row['Business Name']}")
            print(f"   Industry: {row.get('Industry', 'N/A')}")
            print(f"   Revenue Range: ${rev_min:,.0f} - ${rev_max:,.0f}")
            print(f"   Revenue Midpoint: ${rev_mid:,.0f} ⭐")
            print(f"   Years: {row['Years_Parsed']:.1f}")
            print(f"   Employees: {row.get('Employee Range', 'N/A')}")
            print(f"   Website: {row.get('Website', 'N/A')}")

    return {
        'strict': strict,
        'midpoint': midpoint,
        'min_strategy': min_strategy,
        'base_qualified': base_qualified
    }

def main():
    """Main execution"""

    data_dir = Path(__file__).parent.parent / 'data'

    candidate_files = [
        'FINAL_15_QUALIFIED_LEADS_FILTERED_20251016_223230.csv',
        'FINAL_15_QUALIFIED_LEADS_IMPROVED_REVENUE.csv',
        'FINAL_20_QUALIFIED_LEADS_20251016_220131.csv',
    ]

    input_file = None
    for filename in candidate_files:
        candidate = data_dir / filename
        if candidate.exists():
            input_file = candidate
            break

    if not input_file:
        print("ERROR: No qualified leads CSV found")
        sys.exit(1)

    # Analyze strategies
    results = analyze_revenue_strategies(input_file)

    # User choice
    print(f"\n{'='*80}")
    print(f"SELECT FILTERING STRATEGY")
    print(f"{'='*80}")
    print(f"\nOptions:")
    print(f"  1 = STRICT (Revenue Max <= $1.5M) - {len(results['strict'])} leads")
    print(f"  2 = MIDPOINT (Revenue Midpoint <= $1.5M) - {len(results['midpoint'])} leads ⭐ RECOMMENDED")
    print(f"  3 = MIN (Revenue Min <= $1.5M) - {len(results['min_strategy'])} leads")
    print(f"\nDefaulting to MIDPOINT strategy (most balanced)...")

    # Save midpoint results
    if len(results['midpoint']) > 0:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = data_dir / f'QUALIFIED_LEADS_MIDPOINT_{timestamp}.csv'
        results['midpoint'].to_csv(output_file, index=False)

        print(f"\n✅ Saved {len(results['midpoint'])} qualified leads to:")
        print(f"   {output_file}")
    else:
        print(f"\n⚠️  No leads qualified with MIDPOINT strategy")

    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    main()
