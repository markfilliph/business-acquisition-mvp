#!/usr/bin/env python3
"""
Prospect Filter - Apply Acquisition Criteria
Filters prospects based on configurable criteria.
"""

import pandas as pd
import re

class ProspectFilter:
    def __init__(self):
        # Configurable parameters
        self.REVENUE_MIN = 1.0  # Million CAD
        self.REVENUE_MAX = 1.4  # Million CAD  
        self.YEARS_MIN = 15
        self.YEARS_MAX = 40
        self.EXCLUDE_ARTISTIC = True  # Configurable variable
        self.EXCLUDE_KEYWORDS = ['artistic', 'creative', 'art'] if self.EXCLUDE_ARTISTIC else []  # Removed 'design'
        
    def extract_revenue(self, rev_str):
        """Extract numeric revenue value from string."""
        if pd.isna(rev_str) or rev_str == 'Unknown':
            return None
        try:
            if 'M' in str(rev_str):
                return float(re.search(r'(\d+\.?\d*)', str(rev_str)).group(1))
            elif 'K' in str(rev_str):
                return float(re.search(r'(\d+\.?\d*)', str(rev_str)).group(1)) / 1000
            return None
        except:
            return None
    
    def extract_years(self, years_str):
        """Extract numeric years value from string."""
        if pd.isna(years_str) or years_str == 'Unknown':
            return None
        try:
            years_match = re.search(r'(\d+)', str(years_str))
            if years_match:
                return int(years_match.group(1))
            return None
        except:
            return None
    
    def filter_prospects(self, csv_file):
        """Apply all filtering criteria to prospects."""
        df = pd.read_csv(csv_file)
        print(f'Original prospects: {len(df)}')
        
        # Filter by revenue
        df['Revenue_Numeric'] = df['Revenue Estimate'].apply(self.extract_revenue)
        revenue_filtered = df[(df['Revenue_Numeric'] >= self.REVENUE_MIN) & (df['Revenue_Numeric'] <= self.REVENUE_MAX)]
        print(f'After revenue filter ({self.REVENUE_MIN}-{self.REVENUE_MAX}M): {len(revenue_filtered)}')
        
        # Filter by years
        revenue_filtered['Years_Numeric'] = revenue_filtered['Years in Business'].apply(self.extract_years)
        years_filtered = revenue_filtered[(revenue_filtered['Years_Numeric'] >= self.YEARS_MIN) & (revenue_filtered['Years_Numeric'] <= self.YEARS_MAX)]
        print(f'After years filter ({self.YEARS_MIN}-{self.YEARS_MAX}): {len(years_filtered)}')
        
        # Remove unknown phone/website
        contact_filtered = years_filtered[
            (years_filtered['Phone'] != 'Unknown') & 
            (years_filtered['Website'] != 'Unknown') &
            (years_filtered['Phone'].notna()) & 
            (years_filtered['Website'].notna())
        ]
        print(f'After removing unknown contacts: {len(contact_filtered)}')
        
        # Remove artistic/creative businesses if enabled
        if self.EXCLUDE_ARTISTIC:
            artistic_filtered = contact_filtered[
                ~contact_filtered['Notes'].str.lower().str.contains('|'.join(self.EXCLUDE_KEYWORDS), na=False)
            ]
            print(f'After removing artistic businesses: {len(artistic_filtered)}')
        else:
            artistic_filtered = contact_filtered
            
        # Remove businesses with multiple locations
        single_location = artistic_filtered[
            ~artistic_filtered['Notes'].str.lower().str.contains('multiple|locations|branches', na=False) &
            ~artistic_filtered['Address'].str.lower().str.contains('multiple|locations', na=False)
        ]
        print(f'After removing multi-location businesses: {len(single_location)}')
        
        # Sort by acquisition score
        final_prospects = single_location.sort_values('Acquisition Score', ascending=False)
        
        return final_prospects
    
    def print_filtered_results(self, prospects):
        """Print filtered prospect results."""
        print()
        print('🎯 FILTERED PROSPECTS:')
        print('=' * 60)
        for i, (idx, row) in enumerate(prospects.iterrows()):
            print(f'{i+1:2d}. {row["Business Name"]:25s} | Score: {row["Acquisition Score"]:2.0f} | ${row["Revenue_Numeric"]:.1f}M | {row["Years_Numeric"]:2.0f}y | {row["Industry"]}')
    
    def save_filtered_prospects(self, prospects, filename='data/filtered_prospects.csv'):
        """Save filtered prospects to CSV."""
        # Select only relevant columns
        columns_to_save = [
            'Business Name', 'Owner Name', 'Address', 'Phone', 'Website', 
            'Years in Business', 'Industry', 'Google Rating', 'Revenue Estimate', 
            'Acquisition Score', 'Notes'
        ]
        
        prospects[columns_to_save].to_csv(filename, index=False)
        print(f'✅ Saved {len(prospects)} filtered prospects to {filename}')
        return filename

def main():
    """Main function to run filtering."""
    filter_tool = ProspectFilter()
    
    print("Prospect Filtering Tool")
    print("=" * 40)
    print(f"Criteria: ${filter_tool.REVENUE_MIN}-{filter_tool.REVENUE_MAX}M revenue, {filter_tool.YEARS_MIN}-{filter_tool.YEARS_MAX} years")
    print(f"Exclude artistic: {filter_tool.EXCLUDE_ARTISTIC}")
    print()
    
    # Apply filters
    filtered = filter_tool.filter_prospects('data/phase1_prospects.csv')
    
    # Show results
    filter_tool.print_filtered_results(filtered)
    
    # Save results
    filter_tool.save_filtered_prospects(filtered)
    
    print()
    print("✅ Filtering complete!")

if __name__ == "__main__":
    main()