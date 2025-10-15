#!/usr/bin/env python3
"""
Export Qualified Leads from Database
Works with the existing v3 pipeline and database structure

Usage:
    python scripts/export_qualified_leads.py --target 30
    python scripts/export_qualified_leads.py --target 30 --output data/my_leads.csv
"""

import os
import sys
import argparse
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.exports.csv_exporter import CSVExporter
import aiosqlite


async def count_qualified_leads(db_path: str):
    """Count qualified leads in database"""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM businesses WHERE status = 'QUALIFIED'"
        )
        row = await cursor.fetchone()
        return row['count']
    finally:
        await db.close()


def run_lead_generation(target_count: int, max_attempts: int = 3):
    """
    Run the v3 pipeline to generate more leads

    Args:
        target_count: Number of leads to generate
        max_attempts: Maximum number of generation attempts

    Returns:
        bool: True if successful
    """
    print(f"\n{'='*70}")
    print(f"🔄 GENERATING MORE LEADS")
    print(f"{'='*70}")
    print(f"Running: ./generate_v3 {target_count}")
    print(f"This may take a few minutes...\n")

    try:
        result = subprocess.run(
            ['./generate_v3', str(target_count)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        print(result.stdout)
        print(f"\n✅ Lead generation complete")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Lead generation failed:")
        print(e.stderr)
        return False

    except subprocess.TimeoutExpired:
        print(f"❌ Lead generation timed out (>10 minutes)")
        return False

    except Exception as e:
        print(f"❌ Error running lead generation: {e}")
        return False


async def export_qualified_leads(db_path: str, target_count: int, output_file: str = None, auto_generate: bool = True):
    """
    Export qualified leads from the database, automatically generating more if needed

    Args:
        db_path: Path to leads database
        target_count: Number of qualified leads needed
        output_file: Optional output CSV path
        auto_generate: If True, automatically run v3 pipeline when not enough leads
    """

    print(f"\n{'='*70}")
    print(f"📊 EXPORTING QUALIFIED LEADS")
    print(f"{'='*70}")
    print(f"🎯 Target:      {target_count} qualified leads")
    print(f"💾 Database:    {db_path}")
    print(f"🔄 Auto-generate: {'Yes' if auto_generate else 'No'}")
    print(f"{'='*70}\n")

    # Connect to database
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    try:
        # Count qualified leads
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM businesses WHERE status = 'QUALIFIED'"
        )
        row = await cursor.fetchone()
        qualified_count = row['count']

        print(f"✅ Found {qualified_count} qualified leads in database")

        # If not enough leads and auto-generate is enabled, generate more
        if qualified_count < target_count and auto_generate:
            shortfall = target_count - qualified_count
            print(f"\n⚠️  Need {shortfall} more qualified leads to reach target")

            # Close DB connection before running pipeline
            await db.close()

            # Calculate how many raw leads to fetch (assume ~10% qualification rate)
            # Add buffer to account for duplicates and excluded leads
            fetch_count = max(target_count * 15, shortfall * 15)

            print(f"🔄 Automatically generating {fetch_count} raw leads...")
            print(f"   (Estimated to yield {shortfall}+ qualified leads)\n")

            success = run_lead_generation(fetch_count)

            if not success:
                print(f"\n❌ Could not generate more leads automatically")
                print(f"   Proceeding with {qualified_count} available leads\n")
            else:
                # Recount after generation
                new_count = await count_qualified_leads(db_path)
                added = new_count - qualified_count
                print(f"\n✅ Generated {added} additional qualified leads")
                print(f"   Total now: {new_count} qualified leads\n")
                qualified_count = new_count

            # Reconnect to database for export
            db = await aiosqlite.connect(db_path)
            db.row_factory = aiosqlite.Row
            cursor = db.cursor()

        elif qualified_count < target_count:
            # Auto-generate disabled, just show warning
            shortfall = target_count - qualified_count
            print(f"\n⚠️  WARNING: Only {qualified_count}/{target_count} qualified leads available")
            print(f"   Missing: {shortfall} leads")
            print(f"\n💡 To auto-generate more leads, run without --no-generate flag")

            # Show review_required count
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM businesses WHERE status = 'REVIEW_REQUIRED'"
            )
            row = await cursor.fetchone()
            review_count = row['count']

            if review_count > 0:
                print(f"\n📋 {review_count} leads in REVIEW_REQUIRED status")
                print(f"   Consider manually reviewing these leads")

        # Generate timestamped filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'data/qualified_leads_{timestamp}.csv'

        # Export using existing CSV exporter
        print(f"\n📤 Exporting to: {output_file}")
        exporter = CSVExporter(db_path)
        stats = await exporter.export(output_file)

        print(f"\n✅ Export Complete:")
        print(f"   File: {output_file}")
        print(f"   Total businesses: {stats['total']}")
        print(f"   Qualified: {stats['qualified']}")
        print(f"   Excluded: {stats['excluded']}")
        print(f"   Review Required: {stats['review_required']}")

        # Show sample of qualified leads
        cursor = await db.execute(
            """SELECT original_name, phone, website, employee_count
               FROM businesses
               WHERE status = 'QUALIFIED'
               LIMIT 10"""
        )

        qualified_sample = await cursor.fetchall()

        if qualified_sample:
            print(f"\n📋 Sample of Qualified Leads:")
            print(f"{'='*70}")
            for idx, lead in enumerate(qualified_sample, 1):
                emp = lead['employee_count'] if lead['employee_count'] else '?'
                print(f"{idx:2d}. {lead['original_name']:<40} ({emp} employees)")

            if qualified_count > 10:
                print(f"... and {qualified_count - 10} more")

        print(f"\n{'='*70}")
        if stats['qualified'] >= target_count:
            print(f"✅ SUCCESS! Target met: {stats['qualified']}/{target_count} qualified leads exported")
        elif stats['qualified'] > 0:
            shortfall = target_count - stats['qualified']
            print(f"⚠️  PARTIAL SUCCESS: {stats['qualified']}/{target_count} qualified leads exported")
            print(f"   Still need {shortfall} more leads to reach target")
        else:
            print(f"❌ WARNING: No qualified leads found")
            print(f"   All {stats['total']} businesses were excluded or require review")

        print(f"📂 File: {output_file}")
        print(f"{'='*70}\n")

        return output_file, stats['qualified']

    finally:
        await db.close()


def main():
    """Command-line interface"""

    parser = argparse.ArgumentParser(
        description='Export qualified leads from v3 database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all qualified leads
  python scripts/export_qualified_leads.py --target 30

  # Export to specific file
  python scripts/export_qualified_leads.py --target 30 --output data/my_leads.csv

  # Use different database
  python scripts/export_qualified_leads.py --db data/custom.db --target 40
        """
    )

    parser.add_argument(
        '--target',
        type=int,
        default=30,
        help='Number of qualified leads needed (default: 30)'
    )

    parser.add_argument(
        '--db',
        type=str,
        default='data/leads_v3.db',
        help='Database path (default: data/leads_v3.db)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output CSV file (default: data/qualified_leads_TIMESTAMP.csv)'
    )

    parser.add_argument(
        '--no-generate',
        action='store_true',
        help='Disable automatic lead generation when target not met'
    )

    args = parser.parse_args()

    # Check if database exists
    if not os.path.exists(args.db):
        print(f"❌ Error: Database not found: {args.db}")
        print(f"\n💡 Creating new database and generating leads...")

        # Create database by running pipeline
        if not args.no_generate:
            success = run_lead_generation(args.target)
            if not success:
                print(f"❌ Failed to create database")
                sys.exit(1)
        else:
            print(f"❌ Cannot proceed without database (--no-generate flag set)")
            sys.exit(1)

    # Run export
    result = asyncio.run(export_qualified_leads(
        db_path=args.db,
        target_count=args.target,
        output_file=args.output,
        auto_generate=not args.no_generate
    ))

    if result:
        output_file, qualified_count = result

        if qualified_count >= args.target:
            print(f"🎉 Target achieved! You have {qualified_count} qualified leads ready for outreach.")
        elif qualified_count > 0:
            print(f"📊 You have {qualified_count} qualified leads (target was {args.target}).")
            print(f"   Consider:")
            print(f"   • Running again to generate more leads")
            print(f"   • Reviewing REVIEW_REQUIRED businesses")
            print(f"   • Slightly relaxing validation criteria")

        print(f"\n🚀 Next steps:")
        print(f"   1. Review: {output_file}")
        print(f"   2. Import to CRM or begin outreach")
        print(f"   3. Track responses\n")

        # Exit with appropriate code
        sys.exit(0 if qualified_count >= args.target else 1)


if __name__ == "__main__":
    main()
