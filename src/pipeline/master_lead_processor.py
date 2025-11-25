"""
Master Lead Processor - Final Standardization Pipeline
Applies acquisition thesis filtering, enrichment, and standardization to all generated leads.

This module is automatically run after every lead generation to ensure consistent output.
"""

import pandas as pd
import re
from typing import Dict, Tuple, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MasterLeadProcessor:
    """
    Comprehensive lead processing pipeline that applies acquisition thesis
    and standardizes all output fields.
    """

    # Exclusion keywords - corporate giants and non-thesis businesses
    EXCLUSION_KEYWORDS = [
        'stelco', 'orlick', 'g.s. dunn', 'gs dunn', 'mondelez', 'bunge',
        'daifuku', 'national steel car', 'felton', 'embree', 'mega industries',
        'coworking', 'co-working', 'creative studio', 'event venue',
        'warehouse only', 'incubator', 'accelerator'
    ]

    # Category mapping
    CATEGORY_MAP = {
        'machining & fabrication': [
            'machine shop', 'machining', 'fabrication', 'cnc', 'metal working',
            'precision machining', 'tool and die', 'sheet metal'
        ],
        'light manufacturing': [
            'manufacturing', 'assembly', 'production', 'maker', 'factory',
            'industrial manufacturing', 'contract manufacturing'
        ],
        'commercial printing': [
            'printing', 'print shop', 'commercial print', 'digital printing',
            'offset printing', 'graphics', 'signage'
        ],
        'food manufacturing': [
            'food manufacturing', 'food processing', 'bakery', 'confection',
            'beverage', 'food production', 'candy', 'chocolate', 'pasta'
        ],
        'wholesale distribution': [
            'wholesale', 'distribution', 'distributor', 'supply', 'supplier',
            'import', 'export'
        ],
        'equipment rental & industrial services': [
            'equipment rental', 'rental', 'industrial services', 'machinery rental',
            'tool rental', 'equipment leasing'
        ],
        'professional services': [
            'consulting', 'professional services', 'business services',
            'engineering services', 'technical services'
        ]
    }

    # Age range by industry (years)
    AGE_RANGES = {
        'machining & fabrication': (20, 40),
        'light manufacturing': (20, 40),
        'food manufacturing': (20, 35),
        'wholesale distribution': (10, 25),
        'commercial printing': (15, 30),
        'equipment rental & industrial services': (15, 30),
        'professional services': (5, 15),
        'default': (10, 20)
    }

    def __init__(self):
        self.stats = {
            'input_rows': 0,
            'duplicate_rows_removed': 0,
            'duplicate_columns_removed': 0,
            'out_of_thesis_removed': 0,
            'output_rows': 0
        }

    def process(self, input_file: str, output_file: str = None) -> pd.DataFrame:
        """
        Main processing pipeline - applies all master prompt steps.

        Args:
            input_file: Path to input CSV/XLSX
            output_file: Path to output CSV (auto-generated if None)

        Returns:
            Processed DataFrame
        """
        logger.info(f"🔵 Starting Master Lead Processing: {input_file}")

        # Load data
        df = self._load_data(input_file)
        self.stats['input_rows'] = len(df)

        # Step 1: Remove duplicates
        df = self._remove_duplicates(df)

        # Step 2: Normalize text fields
        df = self._normalize_text_fields(df)

        # Step 3: Filter out-of-thesis businesses
        df = self._filter_out_of_thesis(df)

        # Step 4: Convert exact numbers to ranges
        df = self._convert_to_ranges(df)

        # Step 5: Add age range estimates
        df = self._add_age_ranges(df)

        # Step 6: Standardize categories
        df = self._standardize_categories(df)

        # Step 7: Calculate acquisition fit score
        df = self._calculate_fit_score(df)

        # Step 8: Add important notes
        df = self._add_important_notes(df)

        # Step 9: Finalize output columns
        df = self._finalize_output(df)

        # Save output
        if output_file is None:
            output_file = input_file.replace('.csv', '_FULLY_STANDARDIZED.csv')

        df.to_csv(output_file, index=False)
        self.stats['output_rows'] = len(df)

        self._print_stats()
        logger.info(f"✅ Output saved: {output_file}")

        return df

    def _load_data(self, file_path: str) -> pd.DataFrame:
        """Load CSV or XLSX file and normalize column names."""
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)

        # Normalize column names: Title Case → lowercase_with_underscores
        column_mapping = {
            'Business Name': 'business_name',
            'Street Address': 'address',
            'City': 'city',
            'Province': 'province',
            'Postal Code': 'postal_code',
            'Phone': 'phone',
            'Website': 'website',
            'Industry': 'industry',
            'Owner/Contact Name': 'owner_name',
            'Owner Confidence': 'owner_confidence',
            'Owner Source': 'owner_source',
            'LinkedIn Name': 'linkedin_name',
            'LinkedIn URL': 'linkedin_url',
            'LinkedIn Title': 'linkedin_title',
            'Estimated Revenue (CAD)': 'revenue_estimate',
            'Estimated Revenue Range': 'revenue_range',
            'Estimated Employees (Range)': 'employee_range',
            'SDE Estimate': 'sde_estimate',
            'Confidence Score': 'confidence_score',
            'Data Source': 'data_source',
            'Place Types': 'place_types',
            'Review Count': 'review_count',
            'Rating': 'rating',
            'Warnings': 'warnings',
            'Priority': 'priority'
        }

        # Rename columns that exist in the mapping
        df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns}, inplace=True)

        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate rows and columns."""
        initial_rows = len(df)
        initial_cols = len(df.columns)

        # Remove duplicate columns
        df = df.loc[:, ~df.columns.duplicated()]
        cols_removed = initial_cols - len(df.columns)
        self.stats['duplicate_columns_removed'] = cols_removed

        # Remove duplicate rows (based on business name + address)
        if 'business_name' in df.columns and 'address' in df.columns:
            df = df.drop_duplicates(subset=['business_name', 'address'], keep='first')
        else:
            df = df.drop_duplicates()

        rows_removed = initial_rows - len(df)
        self.stats['duplicate_rows_removed'] = rows_removed

        logger.info(f"  Removed {rows_removed} duplicate rows, {cols_removed} duplicate columns")
        return df

    def _normalize_text_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize all text fields."""
        text_columns = df.select_dtypes(include=['object']).columns

        for col in text_columns:
            if col in df.columns:
                # Trim whitespace
                df[col] = df[col].astype(str).str.strip()

                # Address standardization
                if 'address' in col.lower():
                    df[col] = df[col].str.replace(r'\bStreet\b', 'St', regex=True)
                    df[col] = df[col].str.replace(r'\bRoad\b', 'Rd', regex=True)
                    df[col] = df[col].str.replace(r'\bAvenue\b', 'Ave', regex=True)
                    df[col] = df[col].str.replace(r'\bBoulevard\b', 'Blvd', regex=True)

        logger.info("  Normalized text fields")
        return df

    def _filter_out_of_thesis(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove businesses that don't fit acquisition thesis."""
        initial_count = len(df)

        # Create filter mask
        mask = pd.Series([True] * len(df), index=df.index)

        # Filter by business name keywords
        if 'business_name' in df.columns:
            for keyword in self.EXCLUSION_KEYWORDS:
                mask &= ~df['business_name'].str.lower().str.contains(keyword, na=False)

        # Filter by employee count (must be 5-40 for core thesis)
        if 'employee_count' in df.columns:
            df['employee_count'] = pd.to_numeric(df['employee_count'], errors='coerce')
            # Allow some flexibility but exclude obvious outliers
            mask &= (df['employee_count'].isna()) | (
                (df['employee_count'] >= 3) & (df['employee_count'] <= 50)
            )

        # Filter by revenue (1M-8M range with some flexibility)
        if 'revenue_estimate' in df.columns:
            df['revenue_estimate'] = pd.to_numeric(df['revenue_estimate'], errors='coerce')
            mask &= (df['revenue_estimate'].isna()) | (
                (df['revenue_estimate'] >= 500000) & (df['revenue_estimate'] <= 10000000)
            )

        # Apply filter
        df = df[mask].copy()

        removed = initial_count - len(df)
        self.stats['out_of_thesis_removed'] = removed
        logger.info(f"  Removed {removed} out-of-thesis businesses")

        return df

    def _convert_to_ranges(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert exact numbers to realistic ranges or use existing ranges."""

        # Employee count ranges
        if 'employee_range' in df.columns:
            # Already has ranges, just rename
            df['employee_range_estimate'] = df['employee_range']
        elif 'employee_count' in df.columns:
            def employee_range(count):
                if pd.isna(count):
                    return "5-15"
                count = int(count)
                if count <= 8:
                    return "5-10"
                elif count <= 12:
                    return "10-15"
                elif count <= 18:
                    return "15-20"
                elif count <= 30:
                    return "20-30"
                else:
                    return "30-50"

            df['employee_range_estimate'] = df['employee_count'].apply(employee_range)
        else:
            df['employee_range_estimate'] = "5-15"

        # Revenue ranges (±12% variability)
        if 'revenue_range' in df.columns:
            # Already has ranges, just rename
            df['revenue_range_estimate'] = df['revenue_range']
        elif 'revenue_estimate' in df.columns:
            def revenue_range(rev):
                if pd.isna(rev):
                    return "$1.0M-$3.0M"
                # Handle string values with $ and commas
                if isinstance(rev, str):
                    rev = float(rev.replace('$', '').replace(',', ''))
                rev_low = rev * 0.88
                rev_high = rev * 1.12
                return f"${rev_low/1e6:.1f}M-${rev_high/1e6:.1f}M"

            df['revenue_range_estimate'] = df['revenue_estimate'].apply(revenue_range)
        else:
            df['revenue_range_estimate'] = "$1.0M-$3.0M"

        # SDE ranges (±15% variability)
        if 'sde_estimate' in df.columns:
            def sde_range(sde):
                if pd.isna(sde):
                    return "$200K-$500K"
                # Handle string values with $ and commas
                if isinstance(sde, str):
                    sde = float(sde.replace('$', '').replace(',', ''))
                sde_low = sde * 0.85
                sde_high = sde * 1.15
                return f"${sde_low/1000:.0f}K-${sde_high/1000:.0f}K"

            df['sde_range_estimate'] = df['sde_estimate'].apply(sde_range)
        else:
            df['sde_range_estimate'] = "$200K-$500K"

        logger.info("  Converted exact values to ranges")
        return df

    def _add_age_ranges(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add age range estimates based on industry."""

        def get_age_range(category):
            category_lower = str(category).lower()
            for key, age_range in self.AGE_RANGES.items():
                if key in category_lower:
                    return f"{age_range[0]}-{age_range[1]} years"
            return "10-20 years"

        # Use category_standardized if exists, otherwise category or industry
        if 'category_standardized' in df.columns:
            df['age_range_estimate'] = df['category_standardized'].apply(get_age_range)
        elif 'category' in df.columns:
            df['age_range_estimate'] = df['category'].apply(get_age_range)
        elif 'industry' in df.columns:
            df['age_range_estimate'] = df['industry'].apply(get_age_range)
        else:
            df['age_range_estimate'] = "10-20 years"

        logger.info("  Added age range estimates")
        return df

    def _standardize_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize category field based on business name and industry."""

        def standardize_category(row):
            # Check business name and industry/category fields
            text = ' '.join([
                str(row.get('business_name', '')),
                str(row.get('industry', '')),
                str(row.get('category', ''))
            ]).lower()

            # Match against category keywords
            for standard_cat, keywords in self.CATEGORY_MAP.items():
                for keyword in keywords:
                    if keyword in text:
                        return standard_cat.title()

            return "General Business Services"

        df['category_standardized'] = df.apply(standardize_category, axis=1)
        logger.info("  Standardized categories")
        return df

    def _calculate_fit_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate acquisition fit score (1-100) based on internal data."""

        def calculate_score(row):
            score = 50  # Base score

            # Category scoring
            category = str(row.get('category_standardized', '')).lower()
            if 'machining' in category or 'fabrication' in category:
                score += 20
            elif 'light manufacturing' in category:
                score += 18
            elif 'equipment rental' in category or 'industrial' in category:
                score += 15
            elif 'food manufacturing' in category:
                score += 12
            elif 'commercial printing' in category:
                score += 10
            elif 'wholesale' in category:
                score += 8
            elif 'professional services' in category:
                score -= 5

            # Employee count scoring
            emp_range = str(row.get('employee_range_estimate', ''))
            if '5-10' in emp_range or '10-15' in emp_range or '15-20' in emp_range:
                score += 10
            elif '20-30' in emp_range:
                score += 5
            elif '30-50' in emp_range:
                score -= 5

            # Revenue scoring
            revenue = str(row.get('revenue_range_estimate', ''))
            if '1.0M' in revenue or '2.0M' in revenue or '3.0M' in revenue:
                score += 10
            elif '4.0M' in revenue or '5.0M' in revenue:
                score += 5

            # Data completeness
            if pd.notna(row.get('website')) and str(row.get('website')) != 'nan':
                score += 10
            else:
                score -= 15

            if pd.notna(row.get('phone')) and str(row.get('phone')) != 'nan':
                score += 5
            else:
                score -= 10

            # SDE presence
            sde = str(row.get('sde_range_estimate', ''))
            if '$' in sde and 'K' in sde:
                score += 5

            # Clamp score between 1 and 100
            return max(1, min(100, score))

        df['acquisition_fit_score'] = df.apply(calculate_score, axis=1)
        logger.info("  Calculated acquisition fit scores")
        return df

    def _add_important_notes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add important notes column with data-driven insights."""

        def generate_notes(row):
            notes = []

            # Category insights
            category = str(row.get('category_standardized', ''))
            if 'Machining' in category or 'Fabrication' in category:
                notes.append(f"Category: {category} – strong B2B margins")
            elif category and category != "General Business Services":
                notes.append(f"Category: {category}")

            # Employee size
            emp_range = str(row.get('employee_range_estimate', ''))
            if '5-10' in emp_range or '10-15' in emp_range or '15-20' in emp_range:
                notes.append("Healthy SMB team size for acquisition")

            # Revenue insights
            revenue = str(row.get('revenue_range_estimate', ''))
            if any(x in revenue for x in ['1.0M', '2.0M', '3.0M', '4.0M', '5.0M']):
                notes.append("Revenue in ideal SMB band")

            # Data quality warnings
            if pd.isna(row.get('website')) or str(row.get('website')) == 'nan':
                notes.append("Missing website – verify operational status manually")

            if pd.isna(row.get('phone')) or str(row.get('phone')) == 'nan':
                notes.append("Missing phone – lower data confidence")

            # Fit score insights
            score = row.get('acquisition_fit_score', 50)
            if score >= 80:
                notes.append("High acquisition fit – priority follow-up")
            elif score < 40:
                notes.append("Lower data confidence – treat estimates as directional")

            return " | ".join(notes) if notes else "Standard SMB lead"

        df['important_notes'] = df.apply(generate_notes, axis=1)
        logger.info("  Added important notes")
        return df

    def _finalize_output(self, df: pd.DataFrame) -> pd.DataFrame:
        """Finalize output columns in standard order."""

        # Define final column order
        final_columns = [
            'business_name',
            'address',
            'city',
            'postal_code',
            'website',
            'phone',
            'owner_name',
            'owner_confidence',
            'owner_source',
            'industry',
            'category',
            'category_standardized',
            'employee_range_estimate',
            'revenue_range_estimate',
            'sde_range_estimate',
            'age_range_estimate',
            'acquisition_fit_score',
            'important_notes'
        ]

        # Keep only columns that exist
        existing_columns = [col for col in final_columns if col in df.columns]

        # Add any missing critical columns with defaults
        if 'business_name' not in df.columns and 'name' in df.columns:
            df['business_name'] = df['name']

        for col in ['business_name', 'city', 'category_standardized']:
            if col not in df.columns:
                df[col] = "N/A"

        # Select and reorder columns
        output_cols = [col for col in final_columns if col in df.columns]
        df = df[output_cols].copy()

        logger.info(f"  Finalized output with {len(output_cols)} columns")
        return df

    def _print_stats(self):
        """Print processing statistics."""
        logger.info("\n" + "="*60)
        logger.info("MASTER PROCESSING STATISTICS")
        logger.info("="*60)
        logger.info(f"Input rows:                {self.stats['input_rows']}")
        logger.info(f"Duplicate rows removed:    {self.stats['duplicate_rows_removed']}")
        logger.info(f"Duplicate columns removed: {self.stats['duplicate_columns_removed']}")
        logger.info(f"Out-of-thesis removed:     {self.stats['out_of_thesis_removed']}")
        logger.info(f"Output rows:               {self.stats['output_rows']}")
        logger.info(f"Retention rate:            {self.stats['output_rows']/self.stats['input_rows']*100:.1f}%")
        logger.info("="*60 + "\n")


def process_leads_file(input_file: str, output_file: str = None) -> pd.DataFrame:
    """
    Convenience function to process a leads file with the master processor.

    Args:
        input_file: Path to input CSV/XLSX
        output_file: Path to output CSV (optional)

    Returns:
        Processed DataFrame
    """
    processor = MasterLeadProcessor()
    return processor.process(input_file, output_file)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python master_lead_processor.py <input_file> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    process_leads_file(input_file, output_file)
