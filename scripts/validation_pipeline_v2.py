#!/usr/bin/env python3
"""
Validation Pipeline v2
Processes multiple data sources and produces qualified acquisition leads
"""
import pandas as pd
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import subprocess
import json

class ValidationPipeline:
    """Multi-stage lead validation pipeline"""

    def __init__(self):
        self.config = {
            'min_years': 15,
            'max_employees': 30,
            'revenue_min': 1_000_000,
            'revenue_max': 1_500_000,
            'revenue_strategy': 'midpoint',  # strict | midpoint | min
            'min_score': 60,
        }

        # Non-profit indicators
        self.non_profit_keywords = [
            'bia', 'business improvement', 'chamber', 'association',
            'foundation', 'charity', 'non-profit', 'nonprofit',
            'society', 'club', 'organization', 'institute'
        ]

        # Unsuitable business types
        self.excluded_types = {
            'restaurant': ['restaurant', 'bar', 'pub', 'grill', 'cafe', 'bistro', 'eatery'],
            'retail': ['store', 'shop', 'boutique', 'outlet', 'mall'],
            'skilled_trades': ['welding', 'machining', 'construction', 'electrical', 'plumbing', 'hvac', 'roofing'],
        }

        # Target industries (GOOD)
        self.target_industries = [
            'wholesale', 'distribution', 'manufacturing', 'manufacturer',
            'industrial', 'b2b', 'supply', 'equipment', 'printing'
        ]

    def load_data(self, file_paths: List[Path]) -> pd.DataFrame:
        """Load and combine data from multiple sources"""
        print(f"\n{'='*80}")
        print(f"STAGE 1: DATA LOADING")
        print(f"{'='*80}\n")

        all_data = []

        for file_path in file_paths:
            if not file_path.exists():
                print(f"⚠️  File not found: {file_path}")
                continue

            print(f"Loading: {file_path.name}...", end=' ')
            df = pd.read_csv(file_path)
            df['source_file'] = file_path.stem
            all_data.append(df)
            print(f"✅ {len(df)} records")

        if not all_data:
            raise ValueError("No data loaded!")

        combined = pd.concat(all_data, ignore_index=True)
        print(f"\n✅ Total records loaded: {len(combined)}")

        return combined

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names across different sources"""
        print(f"\n{'='*80}")
        print(f"STAGE 2: COLUMN STANDARDIZATION")
        print(f"{'='*80}\n")

        # Map common column variations to standard names
        column_mappings = {
            'business_name': ['name', 'company', 'company_name', 'business', 'business name'],
            'street': ['address', 'street_address', 'street address'],
            'city': ['city', 'municipality'],
            'province': ['province', 'state', 'region'],
            'phone': ['phone', 'telephone', 'phone_number', 'phone number'],
            'website': ['website', 'url', 'web', 'site'],
            'industry': ['industry', 'category', 'type', 'sector', 'business_type'],
            'employees': ['employees', 'employee_count', 'employee range', 'employee_range', 'size'],
            'year_founded': ['year_founded', 'founded', 'established', 'year established', 'year_established'],
        }

        for standard_name, variations in column_mappings.items():
            for col in df.columns:
                if col.lower() in variations:
                    df = df.rename(columns={col: standard_name})
                    print(f"✓ Mapped '{col}' → '{standard_name}'")
                    break

        # Ensure required columns exist
        required = ['business_name']
        for col in required:
            if col not in df.columns:
                print(f"⚠️  Missing required column: {col}")

        print(f"\n✅ Columns standardized")
        return df

    def deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate businesses across sources"""
        print(f"\n{'='*80}")
        print(f"STAGE 3: DEDUPLICATION")
        print(f"{'='*80}\n")

        initial_count = len(df)

        # Create deduplication key (business name + city/address)
        df['dedup_key'] = (
            df['business_name'].str.lower().str.strip() + '_' +
            df.get('city', '').fillna('').str.lower().str.strip()
        )

        # Remove exact duplicates
        df = df.drop_duplicates(subset='dedup_key', keep='first')

        duplicates_removed = initial_count - len(df)
        print(f"✅ Removed {duplicates_removed} duplicates")
        print(f"✅ Unique businesses: {len(df)}")

        return df

    def filter_non_profits(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove non-profits, associations, clubs"""
        print(f"\n{'='*80}")
        print(f"STAGE 4: NON-PROFIT FILTERING")
        print(f"{'='*80}\n")

        initial_count = len(df)

        def is_non_profit(row):
            name = str(row.get('business_name', '')).lower()
            industry = str(row.get('industry', '')).lower()

            text = f"{name} {industry}"

            for keyword in self.non_profit_keywords:
                if keyword in text:
                    return True
            return False

        df['is_non_profit'] = df.apply(is_non_profit, axis=1)
        non_profits = df[df['is_non_profit']]

        if len(non_profits) > 0:
            print(f"❌ Removed {len(non_profits)} non-profits/associations:")
            for _, row in non_profits.head(5).iterrows():
                print(f"   • {row['business_name']}")
            if len(non_profits) > 5:
                print(f"   ... and {len(non_profits) - 5} more")

        df = df[~df['is_non_profit']]
        print(f"\n✅ Remaining: {len(df)} businesses")

        return df

    def filter_unsuitable_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove restaurants, retail, skilled trades"""
        print(f"\n{'='*80}")
        print(f"STAGE 5: BUSINESS TYPE FILTERING")
        print(f"{'='*80}\n")

        initial_count = len(df)

        def is_unsuitable(row):
            name = str(row.get('business_name', '')).lower()
            industry = str(row.get('industry', '')).lower()
            website = str(row.get('website', '')).lower()

            text = f"{name} {industry} {website}"

            for category, keywords in self.excluded_types.items():
                for keyword in keywords:
                    if keyword in text:
                        return True, category
            return False, None

        results = df.apply(lambda row: is_unsuitable(row), axis=1)
        df['is_unsuitable'] = results.apply(lambda x: x[0])
        df['unsuitable_reason'] = results.apply(lambda x: x[1])

        unsuitable = df[df['is_unsuitable']]

        if len(unsuitable) > 0:
            print(f"❌ Removed {len(unsuitable)} unsuitable business types:")

            by_category = unsuitable.groupby('unsuitable_reason').size()
            for category, count in by_category.items():
                print(f"   • {category}: {count}")

        df = df[~df['is_unsuitable']]
        print(f"\n✅ Remaining: {len(df)} businesses")

        return df

    def check_target_industries(self, df: pd.DataFrame) -> pd.DataFrame:
        """Boost score for target industries"""
        print(f"\n{'='*80}")
        print(f"STAGE 6: INDUSTRY CLASSIFICATION")
        print(f"{'='*80}\n")

        def classify_industry(row):
            name = str(row.get('business_name', '')).lower()
            industry = str(row.get('industry', '')).lower()

            text = f"{name} {industry}"

            for target in self.target_industries:
                if target in text:
                    return target

            return 'general_business'

        df['industry_classification'] = df.apply(classify_industry, axis=1)

        target_count = len(df[df['industry_classification'] != 'general_business'])
        print(f"✅ Target industries found: {target_count}/{len(df)}")

        classification_counts = df['industry_classification'].value_counts()
        for industry, count in classification_counts.head(10).items():
            print(f"   • {industry}: {count}")

        return df

    def score_leads(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score leads 0-100 based on criteria"""
        print(f"\n{'='*80}")
        print(f"STAGE 7: LEAD SCORING")
        print(f"{'='*80}\n")

        def calculate_score(row):
            score = 0

            # Industry fit (0-30 points)
            industry = row.get('industry_classification', 'general_business')
            if industry == 'wholesale' or industry == 'distribution':
                score += 30
            elif industry == 'manufacturing' or industry == 'manufacturer':
                score += 25
            elif industry == 'industrial' or industry == 'supply':
                score += 20
            elif industry != 'general_business':
                score += 15
            else:
                score += 10

            # Years in business (0-20 points)
            year_founded = row.get('year_founded', None)
            if pd.notna(year_founded):
                try:
                    year_founded = int(float(year_founded))
                    years = 2025 - year_founded
                    if years >= 25:
                        score += 20
                    elif years >= 20:
                        score += 15
                    elif years >= 15:
                        score += 10
                    elif years >= 10:
                        score += 5
                except:
                    pass

            # Has website (0-15 points)
            website = row.get('website', '')
            if pd.notna(website) and website != '' and 'facebook' not in str(website).lower():
                score += 15
            elif pd.notna(website) and website != '':
                score += 5

            # Has phone (0-5 points)
            phone = row.get('phone', '')
            if pd.notna(phone) and phone != '':
                score += 5

            # Has address (0-5 points)
            street = row.get('street', '')
            if pd.notna(street) and street != '':
                score += 5

            # Multi-source bonus (0-10 points)
            # If we had multiple sources, this would check
            score += 5  # Base points for being in our curated sources

            # Location (Hamilton area) (0-15 points)
            city = str(row.get('city', '')).lower()
            if 'hamilton' in city or 'dundas' in city or 'ancaster' in city:
                score += 15
            elif 'burlington' in city or 'stoney creek' in city:
                score += 10

            return min(100, score)

        df['score'] = df.apply(calculate_score, axis=1)

        print(f"✅ Scoring complete")
        print(f"   Average score: {df['score'].mean():.1f}")
        print(f"   Median score: {df['score'].median():.1f}")
        print(f"   Max score: {df['score'].max():.0f}")

        return df

    def rank_and_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rank by score and filter minimum threshold"""
        print(f"\n{'='*80}")
        print(f"STAGE 8: RANKING & FILTERING")
        print(f"{'='*80}\n")

        initial_count = len(df)

        # Sort by score
        df = df.sort_values('score', ascending=False).reset_index(drop=True)

        # Filter by minimum score
        df = df[df['score'] >= self.config['min_score']]

        # Add rank
        df['rank'] = range(1, len(df) + 1)

        filtered_count = initial_count - len(df)
        print(f"❌ Filtered out {filtered_count} leads below score threshold ({self.config['min_score']})")
        print(f"✅ Qualified leads: {len(df)}")

        # Show score distribution
        if len(df) > 0:
            score_bins = pd.cut(df['score'], bins=[0, 60, 70, 80, 90, 100], labels=['D', 'C', 'B', 'A', 'A+'])
            print(f"\n   Score distribution:")
            for grade, count in score_bins.value_counts().sort_index().items():
                print(f"     {grade}: {count}")

        return df

    async def run_franchise_detection(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run franchise detector on all leads"""
        print(f"\n{'='*80}")
        print(f"STAGE 9: FRANCHISE DETECTION")
        print(f"{'='*80}\n")

        # Save temp file
        temp_file = Path('data/temp_for_franchise_check.csv')
        df.to_csv(temp_file, index=False)

        # Run franchise detector
        print(f"Running franchise detector on {len(df)} businesses...")
        print(f"(This may take a few minutes)\n")

        result = subprocess.run(
            [sys.executable, 'scripts/franchise_detector.py', str(temp_file)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"⚠️  Franchise detector encountered issues:")
            print(result.stderr)
            return df

        # Load franchise detection results
        results_file = temp_file.parent / f"FRANCHISE_DETECTION_{temp_file.stem}.csv"
        if results_file.exists():
            franchise_results = pd.read_csv(results_file)

            # Merge results
            df['is_franchise'] = franchise_results['is_franchise']
            df['franchise_confidence'] = franchise_results['confidence']

            # Filter out franchises
            initial_count = len(df)
            franchises = df[df['is_franchise'] == True]

            if len(franchises) > 0:
                print(f"❌ Detected {len(franchises)} franchises/chains:")
                for _, row in franchises.head(5).iterrows():
                    print(f"   • {row['business_name']} (confidence: {row['franchise_confidence']*100:.0f}%)")
                if len(franchises) > 5:
                    print(f"   ... and {len(franchises) - 5} more")

            df = df[df['is_franchise'] == False]
            print(f"\n✅ Remaining: {len(df)} single-location businesses")

            # Cleanup
            temp_file.unlink()
            results_file.unlink()

        return df

    def generate_summary(self, df: pd.DataFrame, initial_count: int) -> str:
        """Generate pipeline summary"""
        summary = f"""
{'='*80}
VALIDATION PIPELINE SUMMARY
{'='*80}

INPUT:
  • Initial records: {initial_count}

OUTPUT:
  • Qualified leads: {len(df)}
  • Acceptance rate: {len(df)/initial_count*100:.1f}%

TOP 10 LEADS:
"""

        for _, row in df.head(10).iterrows():
            summary += f"\n{row['rank']}. {row['business_name']}"
            summary += f"\n   Industry: {row.get('industry_classification', 'N/A')}"
            summary += f"\n   Score: {row['score']:.0f}/100"
            summary += f"\n   City: {row.get('city', 'N/A')}"
            summary += f"\n   Website: {row.get('website', 'N/A')}"

        summary += f"\n\n{'='*80}\n"

        return summary

    async def run(self, input_files: List[Path], output_file: Path):
        """Execute full pipeline"""
        print(f"\n{'='*80}")
        print(f"VALIDATION PIPELINE V2")
        print(f"{'='*80}\n")

        # Load data
        df = self.load_data(input_files)
        initial_count = len(df)

        # Standardize
        df = self.standardize_columns(df)

        # Deduplicate
        df = self.deduplicate(df)

        # Filter non-profits
        df = self.filter_non_profits(df)

        # Filter unsuitable types
        df = self.filter_unsuitable_types(df)

        # Classify industries
        df = self.check_target_industries(df)

        # Score leads
        df = self.score_leads(df)

        # Rank and filter
        df = self.rank_and_filter(df)

        # Franchise detection
        df = await self.run_franchise_detection(df)

        # Re-rank after franchise removal
        df = df.sort_values('score', ascending=False).reset_index(drop=True)
        df['rank'] = range(1, len(df) + 1)

        # Save output
        df.to_csv(output_file, index=False)

        # Generate summary
        summary = self.generate_summary(df, initial_count)
        print(summary)

        print(f"✅ Saved {len(df)} qualified leads to: {output_file}")

        return df


async def main():
    """Main execution"""

    if len(sys.argv) < 2:
        print("Usage: python validation_pipeline_v2.py <input1.csv> <input2.csv> ...")
        print("   or: python validation_pipeline_v2.py --sources <input1.csv> <input2.csv> --output <output.csv>")
        return

    # Parse arguments
    input_files = []
    output_file = None

    if '--sources' in sys.argv:
        sources_idx = sys.argv.index('--sources')
        output_idx = sys.argv.index('--output') if '--output' in sys.argv else None

        # Get all files between --sources and --output (or end)
        end_idx = output_idx if output_idx else len(sys.argv)
        for i in range(sources_idx + 1, end_idx):
            if not sys.argv[i].startswith('--'):
                input_files.append(Path(sys.argv[i]))

        if output_idx:
            output_file = Path(sys.argv[output_idx + 1])

    else:
        # Simple mode: all args are input files
        input_files = [Path(arg) for arg in sys.argv[1:]]

    if not input_files:
        print("ERROR: No input files specified")
        return

    # Default output file
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = Path(f'data/QUALIFIED_LEADS_BATCH_{timestamp}.csv')

    # Run pipeline
    pipeline = ValidationPipeline()
    await pipeline.run(input_files, output_file)


if __name__ == '__main__':
    asyncio.run(main())
