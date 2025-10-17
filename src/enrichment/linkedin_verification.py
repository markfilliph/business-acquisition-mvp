"""
LinkedIn Manual Verification Tool

Helps manually verify employee counts by:
1. Searching for company on LinkedIn
2. Extracting employee count from LinkedIn page
3. Recording verified data
"""
import asyncio
import csv
from typing import Optional, Dict
import webbrowser
import time


class LinkedInVerifier:
    """
    Manual LinkedIn verification assistant.

    Opens LinkedIn company pages for manual verification.
    Records actual employee counts.
    """

    def __init__(self):
        self.verified_data = []

    def get_linkedin_search_url(self, company_name: str, website: Optional[str] = None) -> str:
        """Generate LinkedIn company search URL."""
        # Clean company name for search
        search_term = company_name.replace(',', '').replace('.', '')

        # Add location for better results
        search_query = f"{search_term} Hamilton Ontario"

        # LinkedIn company search URL
        encoded_query = search_query.replace(' ', '%20')
        return f"https://www.linkedin.com/search/results/companies/?keywords={encoded_query}"

    async def verify_companies_from_csv(self, input_csv: str, output_csv: str):
        """
        Interactive verification of companies from CSV.

        Args:
            input_csv: CSV with companies to verify
            output_csv: Output CSV with verified employee counts
        """
        print("\n" + "="*80)
        print("LINKEDIN MANUAL VERIFICATION TOOL")
        print("="*80)
        print("\nThis tool will:")
        print("1. Open LinkedIn search for each company")
        print("2. Ask you to manually find the company page")
        print("3. Record the actual employee count from LinkedIn")
        print("4. Mark companies as VERIFIED or EXCLUDED")
        print("\nPress ENTER to continue, or Ctrl+C to cancel...")
        input()

        with open(input_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            companies = list(reader)

        verified = []
        excluded = []
        skipped = []

        for i, company in enumerate(companies, 1):
            name = company.get('Business Name', '')
            website = company.get('Website', '')

            print(f"\n{'='*80}")
            print(f"Company {i}/{len(companies)}: {name}")
            print(f"Website: {website}")
            print(f"{'='*80}")

            # Get LinkedIn search URL
            linkedin_url = self.get_linkedin_search_url(name, website)

            print(f"\n🔍 Opening LinkedIn search: {linkedin_url}")
            print("\nINSTRUCTIONS:")
            print("1. Find the company's LinkedIn page")
            print("2. Check the employee count (usually shown as 'X employees on LinkedIn')")
            print("3. Check if it's a franchise, subsidiary, or large corporation")

            # Open browser
            webbrowser.open(linkedin_url)

            print("\n" + "-"*80)
            print("What did you find on LinkedIn?")
            print("  [number] - Enter actual employee count (e.g., 25)")
            print("  [range]  - Enter employee range (e.g., 11-50, 51-200)")
            print("  [f]      - Mark as FRANCHISE (exclude)")
            print("  [c]      - Mark as CORPORATION (exclude)")
            print("  [l]      - Mark as TOO LARGE (exclude)")
            print("  [n]      - Company NOT FOUND on LinkedIn")
            print("  [s]      - SKIP for now")
            print("  [q]      - QUIT verification")
            print("-"*80)

            response = input("Enter your finding: ").strip().lower()

            if response == 'q':
                print("\n⚠️  Quitting verification...")
                break
            elif response == 's':
                skipped.append(company)
                print("⏭️  Skipped")
                continue
            elif response == 'f':
                company['Exclusion Reason'] = 'FRANCHISE (LinkedIn verified)'
                company['LinkedIn Status'] = 'EXCLUDED - Franchise'
                excluded.append(company)
                print("❌ Marked as FRANCHISE - EXCLUDED")
                continue
            elif response == 'c':
                company['Exclusion Reason'] = 'LARGE CORPORATION (LinkedIn verified)'
                company['LinkedIn Status'] = 'EXCLUDED - Corporation'
                excluded.append(company)
                print("❌ Marked as CORPORATION - EXCLUDED")
                continue
            elif response == 'l':
                company['Exclusion Reason'] = 'TOO LARGE (LinkedIn verified)'
                company['LinkedIn Status'] = 'EXCLUDED - Too Large'
                excluded.append(company)
                print("❌ Marked as TOO LARGE - EXCLUDED")
                continue
            elif response == 'n':
                company['LinkedIn Employees'] = 'NOT FOUND'
                company['LinkedIn Status'] = 'NOT FOUND'
                company['Verification Status'] = 'UNVERIFIED'
                verified.append(company)
                print("⚠️  Company not found on LinkedIn")
                continue
            elif '-' in response:
                # Employee range
                try:
                    parts = response.split('-')
                    emp_min = int(parts[0])
                    emp_max = int(parts[1])

                    company['LinkedIn Employees'] = f"{emp_min}-{emp_max}"
                    company['LinkedIn Emp Min'] = emp_min
                    company['LinkedIn Emp Max'] = emp_max
                    company['LinkedIn Status'] = 'VERIFIED - Range'
                    company['Verification Status'] = 'VERIFIED'

                    # Check if meets criteria (5-30)
                    if emp_min >= 5 and emp_max <= 30:
                        verified.append(company)
                        print(f"✅ VERIFIED: {emp_min}-{emp_max} employees - QUALIFIES")
                    else:
                        company['Exclusion Reason'] = f'Employee count {emp_min}-{emp_max} outside range (5-30)'
                        company['LinkedIn Status'] = 'EXCLUDED - Employee Count'
                        excluded.append(company)
                        print(f"❌ EXCLUDED: {emp_min}-{emp_max} employees (outside 5-30 range)")
                except:
                    print("❌ Invalid range format. Skipping.")
                    skipped.append(company)
                continue
            elif response.isdigit():
                # Exact employee count
                emp_count = int(response)

                company['LinkedIn Employees'] = emp_count
                company['LinkedIn Emp Min'] = emp_count
                company['LinkedIn Emp Max'] = emp_count
                company['LinkedIn Status'] = 'VERIFIED - Exact'
                company['Verification Status'] = 'VERIFIED'

                # Check if meets criteria (5-30)
                if 5 <= emp_count <= 30:
                    verified.append(company)
                    print(f"✅ VERIFIED: {emp_count} employees - QUALIFIES")
                else:
                    company['Exclusion Reason'] = f'Employee count {emp_count} outside range (5-30)'
                    company['LinkedIn Status'] = 'EXCLUDED - Employee Count'
                    excluded.append(company)
                    print(f"❌ EXCLUDED: {emp_count} employees (outside 5-30 range)")
                continue
            else:
                print("❌ Invalid input. Skipping.")
                skipped.append(company)
                continue

            # Brief pause between companies
            time.sleep(1)

        # Save results
        print(f"\n{'='*80}")
        print("VERIFICATION COMPLETE")
        print(f"{'='*80}")
        print(f"✅ Verified & Qualified: {len(verified)}")
        print(f"❌ Excluded: {len(excluded)}")
        print(f"⏭️  Skipped: {len(skipped)}")
        print()

        # Write verified companies
        if verified:
            with open(output_csv, 'w', newline='', encoding='utf-8') as f:
                if verified:
                    fieldnames = list(verified[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(verified)
            print(f"✅ Verified companies saved to: {output_csv}")

        # Write excluded companies
        excluded_csv = output_csv.replace('.csv', '_EXCLUDED.csv')
        if excluded:
            with open(excluded_csv, 'w', newline='', encoding='utf-8') as f:
                fieldnames = list(excluded[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(excluded)
            print(f"❌ Excluded companies saved to: {excluded_csv}")

        return len(verified), len(excluded), len(skipped)


async def main():
    """Run LinkedIn verification on final leads."""
    verifier = LinkedInVerifier()

    input_file = 'data/FINAL_20_QUALIFIED_LEADS_20251016_220131.csv'
    output_file = 'data/LINKEDIN_VERIFIED_LEADS.csv'

    await verifier.verify_companies_from_csv(input_file, output_file)


if __name__ == '__main__':
    asyncio.run(main())
