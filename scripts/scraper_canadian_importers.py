#!/usr/bin/env python3
"""
Canadian Importers Database Scraper
Downloads and filters Canadian government importer data for Hamilton area
Data source: Government of Canada Open Data Portal
"""
import pandas as pd
import requests
from pathlib import Path
from typing import List
import sys

class CanadianImportersScaper:
    """Downloads and processes Canadian Importers Database"""

    # Open Government Portal - Canadian Importers Database (2022)
    # https://open.canada.ca/data/en/dataset/2e7c5a58-986f-402c-9dec-a45e0dadf8dd
    BASE_URL = "https://open.canada.ca/data/en/dataset/2e7c5a58-986f-402c-9dec-a45e0dadf8dd"

    # Direct CSV download URLs (2022 data - most recent available)
    CSV_URLS = {
        'by_city': 'https://ised-isde.canada.ca/cid-bdic/2022/CID-BDIC-2022-MajorImportersByCity-ImportateursPrincipauxParVille.csv',
        'by_country': 'https://ised-isde.canada.ca/cid-bdic/2022/CID-BDIC-2022-MajorImportersByCountry-ImportateursPrincipauxParPays.csv',
    }

    TARGET_CITIES = [
        'Hamilton',
        'Dundas',
        'Ancaster',
        'Stoney Creek',
        'Burlington',  # Nearby
        'Waterdown',
    ]

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)

    def download_csv(self, url: str, filename: str) -> Path:
        """Download CSV file from URL"""
        print(f"\n📥 Downloading: {filename}...")

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            output_path = self.data_dir / filename

            with open(output_path, 'wb') as f:
                f.write(response.content)

            print(f"✅ Downloaded: {output_path} ({len(response.content)/1024:.1f} KB)")
            return output_path

        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading {url}: {e}")
            return None

    def filter_hamilton_area(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter for Hamilton area cities"""
        print(f"\n🔍 Filtering for Hamilton area...")
        print(f"Initial records: {len(df)}")

        # Determine city column name (may vary)
        city_col = None
        for col in df.columns:
            if 'city' in col.lower() or 'ville' in col.lower():
                city_col = col
                break

        if not city_col:
            print(f"⚠️  Could not find city column. Columns: {df.columns.tolist()}")
            return df

        print(f"Using city column: '{city_col}'")

        # Filter for target cities (case-insensitive)
        mask = df[city_col].str.lower().isin([city.lower() for city in self.TARGET_CITIES])
        filtered_df = df[mask].copy()

        print(f"✅ Found {len(filtered_df)} importers in Hamilton area")

        # Show city breakdown
        if len(filtered_df) > 0:
            city_counts = filtered_df[city_col].value_counts()
            print(f"\nCity breakdown:")
            for city, count in city_counts.items():
                print(f"   • {city}: {count}")

        return filtered_df

    def filter_ontario(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter for Ontario province"""
        # Determine province column
        prov_col = None
        for col in df.columns:
            if 'province' in col.lower() or 'prov' in col.lower():
                prov_col = col
                break

        if prov_col and prov_col in df.columns:
            df = df[df[prov_col].str.upper() == 'ON'].copy()
            print(f"✅ Filtered for Ontario only: {len(df)} records")

        return df

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names to English"""
        print(f"\n🔧 Standardizing columns...")

        # Common bilingual column mappings (English/French)
        mappings = {
            'company_name': ['company name', 'company', 'importer', 'nom de la société', 'importateur'],
            'city': ['city', 'ville'],
            'province': ['province', 'prov'],
            'postal_code': ['postal code', 'code postal'],
            'product': ['product', 'produit', 'hs code', 'commodity'],
            'country': ['country', 'pays', 'country of origin'],
        }

        renamed = {}
        for standard_name, variations in mappings.items():
            for col in df.columns:
                if any(var.lower() in col.lower() for var in variations):
                    renamed[col] = standard_name
                    break

        df = df.rename(columns=renamed)
        print(f"✅ Standardized columns: {list(renamed.values())}")

        return df

    def add_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add metadata columns"""
        df['source'] = 'Canadian Importers Database (2022)'
        df['industry'] = 'Wholesale Importer'
        df['data_type'] = 'Government Verified'

        return df

    def clean_and_deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean data and remove duplicates"""
        print(f"\n🧹 Cleaning and deduplicating...")

        initial_count = len(df)

        # Remove rows with missing company names
        if 'company_name' in df.columns:
            df = df[df['company_name'].notna()].copy()
            df = df[df['company_name'].str.strip() != ''].copy()

        # Remove duplicates based on company name + city
        if 'company_name' in df.columns and 'city' in df.columns:
            df = df.drop_duplicates(subset=['company_name', 'city'], keep='first')

        removed = initial_count - len(df)
        print(f"✅ Removed {removed} invalid/duplicate records")
        print(f"✅ Final count: {len(df)} importers")

        return df

    def export_results(self, df: pd.DataFrame, output_filename: str) -> Path:
        """Export to CSV"""
        output_path = self.data_dir / output_filename

        # Reorder columns for readability
        preferred_order = [
            'company_name', 'city', 'province', 'postal_code',
            'product', 'country', 'industry', 'source'
        ]

        # Keep only columns that exist
        existing_cols = [col for col in preferred_order if col in df.columns]
        other_cols = [col for col in df.columns if col not in existing_cols]
        final_cols = existing_cols + other_cols

        df = df[final_cols]

        df.to_csv(output_path, index=False)
        print(f"\n✅ Exported to: {output_path}")

        return output_path

    def run(self, output_filename: str = 'canadian_importers_hamilton.csv'):
        """Main execution"""
        print(f"\n{'='*80}")
        print(f"CANADIAN IMPORTERS DATABASE SCRAPER")
        print(f"{'='*80}")
        print(f"Data Source: Government of Canada Open Data Portal")
        print(f"Dataset: Canadian Importers Database (2022)")
        print(f"Target: Hamilton, ON area")

        # Download CSV
        temp_file = self.download_csv(
            self.CSV_URLS['by_city'],
            'temp_importers_by_city.csv'
        )

        if not temp_file or not temp_file.exists():
            print(f"\n❌ Failed to download data")
            return None

        # Load data
        print(f"\n📊 Loading data...")
        try:
            df = pd.read_csv(temp_file, encoding='utf-8')
            print(f"✅ Loaded {len(df)} total records")
        except UnicodeDecodeError:
            # Try alternate encoding for bilingual Canadian data
            df = pd.read_csv(temp_file, encoding='ISO-8859-1')
            print(f"✅ Loaded {len(df)} total records (ISO-8859-1 encoding)")

        print(f"Columns: {df.columns.tolist()}")

        # Process data
        df = self.standardize_columns(df)
        df = self.filter_ontario(df)
        df = self.filter_hamilton_area(df)
        df = self.add_metadata(df)
        df = self.clean_and_deduplicate(df)

        if len(df) == 0:
            print(f"\n⚠️  No importers found in Hamilton area")
            return None

        # Export
        output_path = self.export_results(df, output_filename)

        # Show sample
        print(f"\n{'='*80}")
        print(f"SAMPLE RESULTS (First 5)")
        print(f"{'='*80}\n")

        for idx, row in df.head(5).iterrows():
            print(f"{idx+1}. {row.get('company_name', 'N/A')}")
            print(f"   City: {row.get('city', 'N/A')}, {row.get('province', 'N/A')}")
            print(f"   Product: {row.get('product', 'N/A')}")
            if 'postal_code' in row and pd.notna(row['postal_code']):
                print(f"   Postal Code: {row['postal_code']}")
            print()

        print(f"{'='*80}")
        print(f"✅ SUCCESS: {len(df)} Hamilton-area importers extracted")
        print(f"{'='*80}\n")

        # Cleanup temp file
        if temp_file.exists():
            temp_file.unlink()

        return output_path


def main():
    """Main execution"""
    scraper = CanadianImportersScaper()

    output_filename = 'canadian_importers_hamilton.csv'
    if len(sys.argv) > 1:
        output_filename = sys.argv[1]

    result = scraper.run(output_filename)

    if result:
        print(f"\n✅ Next step: Run validation pipeline on this data:")
        print(f"   python scripts/validation_pipeline_v2.py {result}")
    else:
        print(f"\n❌ Scraping failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
