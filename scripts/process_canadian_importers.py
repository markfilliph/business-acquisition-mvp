#!/usr/bin/env python3
"""
Canadian Importers Database Processor
Processes downloaded Canadian government importer data for Hamilton area

USAGE:
1. Download CSV from: https://open.canada.ca/data/en/dataset/2e7c5a58-986f-402c-9dec-a45e0dadf8dd
   - Download "Major Importers by city" CSV file
2. Save to: data/canadian_importers_raw.csv
3. Run: python scripts/process_canadian_importers.py
"""
import pandas as pd
from pathlib import Path
import sys

class CanadianImportersProcessor:
    """Processes Canadian Importers Database for Hamilton area"""

    TARGET_CITIES = [
        'Hamilton',
        'Dundas',
        'Ancaster',
        'Stoney Creek',
        'Burlington',
        'Waterdown',
    ]

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / 'data'

    def load_data(self, input_file: Path) -> pd.DataFrame:
        """Load CSV with multiple encoding attempts"""
        print(f"\n📊 Loading data from: {input_file.name}")

        # Try different encodings common in Canadian government data
        encodings = ['utf-8', 'ISO-8859-1', 'latin1', 'cp1252']

        for encoding in encodings:
            try:
                df = pd.read_csv(input_file, encoding=encoding)
                print(f"✅ Loaded {len(df)} records (encoding: {encoding})")
                print(f"Columns: {df.columns.tolist()[:10]}{'...' if len(df.columns) > 10 else ''}")
                return df
            except Exception as e:
                continue

        raise ValueError(f"Could not load CSV with any encoding: {encodings}")

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize bilingual column names"""
        print(f"\n🔧 Standardizing columns...")

        # Map bilingual columns (English/French)
        mappings = {}
        for col in df.columns:
            col_lower = col.lower()

            if any(x in col_lower for x in ['company name', 'nom de la société', 'importer name', 'importateur']):
                mappings[col] = 'business_name'
            elif 'city' in col_lower or 'ville' in col_lower:
                mappings[col] = 'city'
            elif 'province' in col_lower or 'prov' in col_lower:
                mappings[col] = 'province'
            elif 'postal' in col_lower or 'code postal' in col_lower:
                mappings[col] = 'postal_code'
            elif 'product' in col_lower or 'produit' in col_lower or 'commodity' in col_lower:
                mappings[col] = 'product'
            elif 'country' in col_lower or 'pays' in col_lower:
                mappings[col] = 'country'
            elif 'value' in col_lower or 'valeur' in col_lower:
                mappings[col] = 'import_value'

        if mappings:
            df = df.rename(columns=mappings)
            print(f"✅ Renamed columns: {list(mappings.values())}")

        return df

    def filter_hamilton_area(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter for Hamilton area cities"""
        print(f"\n🔍 Filtering for Hamilton area...")

        if 'city' not in df.columns:
            print(f"⚠️  No 'city' column found. Available: {df.columns.tolist()}")
            return df

        # Filter for Ontario first (if province column exists)
        if 'province' in df.columns:
            initial_count = len(df)
            df = df[df['province'].str.upper() == 'ON'].copy()
            print(f"✅ Filtered for Ontario: {len(df)} records (from {initial_count})")

        # Filter for target cities
        initial_count = len(df)
        mask = df['city'].str.strip().str.lower().isin([city.lower() for city in self.TARGET_CITIES])
        df = df[mask].copy()

        print(f"✅ Filtered for Hamilton area: {len(df)} records (from {initial_count})")

        if len(df) > 0:
            city_counts = df['city'].value_counts()
            print(f"\nCity breakdown:")
            for city, count in city_counts.items():
                print(f"   • {city}: {count}")

        return df

    def add_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add metadata columns"""
        df['source'] = 'Canadian Importers Database'
        df['industry'] = 'Wholesale Importer'

        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and deduplicate"""
        print(f"\n🧹 Cleaning data...")

        initial_count = len(df)

        # Remove rows with missing business names
        if 'business_name' in df.columns:
            df = df[df['business_name'].notna()].copy()
            df = df[df['business_name'].str.strip() != ''].copy()

        # Remove duplicates
        if 'business_name' in df.columns and 'city' in df.columns:
            df = df.drop_duplicates(subset=['business_name', 'city'], keep='first')

        removed = initial_count - len(df)
        print(f"✅ Removed {removed} invalid/duplicate records")
        print(f"✅ Final count: {len(df)} unique importers")

        return df

    def export(self, df: pd.DataFrame, output_file: Path):
        """Export to CSV"""
        # Reorder columns
        preferred_order = [
            'business_name', 'city', 'province', 'postal_code',
            'product', 'country', 'import_value', 'industry', 'source'
        ]

        existing_cols = [col for col in preferred_order if col in df.columns]
        other_cols = [col for col in df.columns if col not in existing_cols]
        final_cols = existing_cols + other_cols

        df = df[final_cols]

        df.to_csv(output_file, index=False)
        print(f"\n✅ Exported to: {output_file}")

    def show_sample(self, df: pd.DataFrame):
        """Show sample results"""
        print(f"\n{'='*80}")
        print(f"SAMPLE RESULTS (First 10)")
        print(f"{'='*80}\n")

        for idx, row in df.head(10).iterrows():
            print(f"{idx+1}. {row.get('business_name', 'N/A')}")
            print(f"   City: {row.get('city', 'N/A')}, {row.get('province', 'N/A')}")

            if 'product' in row and pd.notna(row['product']):
                product = str(row['product'])[:60]
                print(f"   Product: {product}")

            if 'postal_code' in row and pd.notna(row['postal_code']):
                print(f"   Postal: {row['postal_code']}")

            print()

    def run(self, input_file: Path, output_file: Path):
        """Main processing"""
        print(f"\n{'='*80}")
        print(f"CANADIAN IMPORTERS DATABASE PROCESSOR")
        print(f"{'='*80}")

        # Load
        df = self.load_data(input_file)

        # Process
        df = self.standardize_columns(df)
        df = self.filter_hamilton_area(df)

        if len(df) == 0:
            print(f"\n⚠️  No importers found in Hamilton area")
            return None

        df = self.add_metadata(df)
        df = self.clean_data(df)

        # Export
        self.export(df, output_file)

        # Show sample
        self.show_sample(df)

        print(f"\n{'='*80}")
        print(f"✅ SUCCESS: {len(df)} Hamilton-area importers processed")
        print(f"{'='*80}\n")

        return output_file


def main():
    """Main execution"""

    processor = CanadianImportersProcessor()
    data_dir = processor.data_dir

    # Determine input file
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    else:
        # Default input filename
        input_file = data_dir / 'canadian_importers_raw.csv'

    if not input_file.exists():
        print(f"\n❌ Input file not found: {input_file}")
        print(f"\nTo use this script:")
        print(f"1. Download 'Major Importers by city' CSV from:")
        print(f"   https://open.canada.ca/data/en/dataset/2e7c5a58-986f-402c-9dec-a45e0dadf8dd")
        print(f"2. Save to: {data_dir / 'canadian_importers_raw.csv'}")
        print(f"3. Run: python {Path(__file__).name}")
        print(f"\nOr specify a custom path:")
        print(f"   python {Path(__file__).name} /path/to/your/file.csv")
        sys.exit(1)

    # Determine output file
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    else:
        output_file = data_dir / 'canadian_importers_hamilton.csv'

    # Process
    result = processor.run(input_file, output_file)

    if result:
        print(f"\n✅ Next step: Run validation pipeline:")
        print(f"   python scripts/validation_pipeline_v2.py {result}")


if __name__ == '__main__':
    main()
