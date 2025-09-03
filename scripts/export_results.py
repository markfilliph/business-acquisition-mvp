#!/usr/bin/env python3
"""
Export qualified leads to various formats (CSV, Excel, Google Sheets).
"""
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import config
from src.utils.logging_config import configure_logging
from src.database.connection import DatabaseManager


async def export_to_csv(leads_data: list, filename: str):
    """Export leads to CSV format."""
    
    if not leads_data:
        print("No leads to export")
        return
    
    # Define CSV headers based on the BusinessLead.to_dict() structure
    headers = [
        "unique_id", "business_name", "industry", "address", "city", "postal_code",
        "phone", "email", "website", "years_in_business", "employee_count",
        "estimated_revenue", "revenue_confidence", "lead_score", "qualification_status",
        "status", "confidence_score", "data_sources", "created_at", "updated_at", "notes"
    ]
    
    # Create output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    filepath = output_dir / filename
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for lead_data in leads_data:
            # Extract only the headers we want
            row = {header: lead_data.get(header, '') for header in headers}
            writer.writerow(row)
    
    print(f"✅ Exported {len(leads_data)} leads to {filepath}")


async def export_to_json(leads_data: list, filename: str):
    """Export leads to JSON format."""
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    filepath = output_dir / filename
    
    # Create export package
    export_data = {
        "export_timestamp": datetime.utcnow().isoformat(),
        "total_leads": len(leads_data),
        "leads": leads_data
    }
    
    with open(filepath, 'w', encoding='utf-8') as jsonfile:
        json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"✅ Exported {len(leads_data)} leads to {filepath}")


def format_for_google_sheets(leads_data: list) -> list:
    """Format leads data for Google Sheets import."""
    
    # Headers for Google Sheets (matching the prospects tracker)
    headers = [
        "Business Name", "Owner Name", "Email", "Phone", "Website",
        "Revenue Estimate", "Years in Business", "Acquisition Score",
        "Initial Email Sent", "Follow-up 1", "Follow-up 2",
        "Response Status", "Response Date", "Meeting Scheduled",
        "Notes", "Next Action", "Priority"
    ]
    
    formatted_data = [headers]  # Start with headers
    
    for lead_data in leads_data:
        # Extract priority based on score
        score = lead_data.get('lead_score', 0)
        if score >= 80:
            priority = 'High'
        elif score >= 60:
            priority = 'Medium'
        else:
            priority = 'Low'
        
        # Format notes
        notes = lead_data.get('notes', '')
        if len(notes) > 100:
            notes = notes[:100] + "..."
        
        row = [
            lead_data.get('business_name', ''),
            '',  # Owner Name (to be filled manually)
            lead_data.get('email', ''),
            lead_data.get('phone', ''),
            lead_data.get('website', ''),
            lead_data.get('estimated_revenue', ''),
            lead_data.get('years_in_business', ''),
            lead_data.get('lead_score', ''),
            '',  # Initial Email Sent
            '',  # Follow-up 1
            '',  # Follow-up 2
            'No Reply',  # Response Status
            '',  # Response Date
            '',  # Meeting Scheduled
            notes,  # Notes
            'Research completed',  # Next Action
            priority  # Priority
        ]
        
        formatted_data.append(row)
    
    return formatted_data


async def main():
    """Main export function."""
    
    # Configure logging
    configure_logging(config)
    
    print("📤 Lead Export Utility")
    print("=" * 30)
    
    # Initialize database
    db_manager = DatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get qualified leads
        leads_data = await db_manager.get_qualified_leads(limit=100, min_score=60)
        
        if not leads_data:
            print("❌ No qualified leads found to export")
            return 1
        
        print(f"📊 Found {len(leads_data)} qualified leads")
        
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export options
        print("\nSelect export format:")
        print("1. CSV (for Excel/general use)")
        print("2. JSON (for technical analysis)")
        print("3. Google Sheets format (CSV optimized for Sheets)")
        print("4. All formats")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice in ['1', '4']:
            await export_to_csv(leads_data, f"qualified_leads_{timestamp}.csv")
        
        if choice in ['2', '4']:
            await export_to_json(leads_data, f"qualified_leads_{timestamp}.json")
        
        if choice in ['3', '4']:
            # Format for Google Sheets and export as CSV
            sheets_data = format_for_google_sheets(leads_data)
            
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            filepath = output_dir / f"google_sheets_import_{timestamp}.csv"
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(sheets_data)
            
            print(f"✅ Exported Google Sheets format to {filepath}")
        
        if choice not in ['1', '2', '3', '4']:
            print("❌ Invalid choice")
            return 1
        
        print(f"\n✅ Export completed!")
        print(f"Files saved in the 'output/' directory")
        
        # Display quick stats
        print(f"\n📈 QUICK STATS")
        print(f"Total leads: {len(leads_data)}")
        
        # Count by status
        status_counts = {}
        score_total = 0
        
        for lead in leads_data:
            status = lead.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            score_total += lead.get('lead_score', 0)
        
        for status, count in status_counts.items():
            print(f"{status.replace('_', ' ').title()}: {count}")
        
        avg_score = score_total / len(leads_data) if leads_data else 0
        print(f"Average score: {avg_score:.1f}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)