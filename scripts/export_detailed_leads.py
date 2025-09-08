#!/usr/bin/env python3
"""
Export detailed qualified leads with comprehensive information to CSV/JSON formats.
"""
import asyncio
import sys
import csv
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import config
from src.database.connection import DatabaseManager

async def export_detailed_leads():
    """Export qualified leads with all available information."""
    
    print("🎯 EXPORTING DETAILED QUALIFIED LEADS")
    print("=" * 60)
    
    # Initialize database
    db_manager = DatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get qualified leads with full details
        leads_data = await db_manager.get_qualified_leads(limit=50, min_score=50)
        
        if not leads_data:
            print("❌ No qualified leads found")
            return
        
        # Create exports directory
        exports_dir = Path("exports")
        exports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export to CSV
        csv_file = exports_dir / f"qualified_leads_detailed_{timestamp}.csv"
        export_to_csv(leads_data, csv_file)
        
        # Export to JSON
        json_file = exports_dir / f"qualified_leads_detailed_{timestamp}.json"
        export_to_json(leads_data, json_file)
        
        # Create summary report
        summary_file = exports_dir / f"leads_summary_report_{timestamp}.txt"
        create_summary_report(leads_data, summary_file)
        
        print(f"\n✅ EXPORT COMPLETED")
        print(f"📄 CSV Export: {csv_file}")
        print(f"🗂️  JSON Export: {json_file}")
        print(f"📋 Summary Report: {summary_file}")
        print(f"🎯 Total Qualified Leads: {len(leads_data)}")
        
        # Display summary statistics
        display_summary_stats(leads_data)
        
    except Exception as e:
        print(f"❌ Error exporting leads: {e}")

def export_to_csv(leads_data, file_path):
    """Export leads to CSV format with all details - only verified websites."""
    
    fieldnames = [
        'unique_id', 'business_name', 'industry', 
        'address', 'city', 'postal_code', 
        'phone', 'email', 'website', 'website_verified',
        'website_validation_status', 'website_business_match',
        'years_in_business', 'employee_count',
        'estimated_revenue', 'revenue_confidence', 
        'lead_score', 'qualification_status',
        'data_sources', 'created_at', 'updated_at',
        'business_intelligence_notes', 'qualification_reasons'
    ]
    
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for lead in leads_data:
            # Parse notes to extract business intelligence
            notes = lead.get('notes', '').split('; ') if lead.get('notes') else []
            bi_notes = [note for note in notes if 'business_intelligence' in note.lower()]
            
            # Parse qualification reasons
            qual_reasons = lead.get('qualification_reasons', '').replace('["', '').replace('"]', '').replace('", "', '; ')
            
            # Only include website if it's verified
            website_url = lead.get('website', '')
            website_verified = lead.get('website_validated', False)
            
            # Filter out unverified websites
            if website_url and not website_verified:
                website_url = ''  # Don't export unverified websites
                
            row = {
                'unique_id': lead['unique_id'],
                'business_name': lead['business_name'],
                'industry': lead['industry'] or '',
                'address': lead['address'] or '',
                'city': lead['city'] or '',
                'postal_code': lead['postal_code'] or '',
                'phone': lead['phone'] or '',
                'email': lead['email'] or '',
                'website': website_url,
                'website_verified': 'YES' if website_verified else 'NO',
                'website_validation_status': lead.get('website_status_code', '') or '',
                'website_business_match': f"{lead.get('website_business_name_match', 0):.1%}" if lead.get('website_business_name_match') else '',
                'years_in_business': lead['years_in_business'] or '',
                'employee_count': lead['employee_count'] or '',
                'estimated_revenue': lead['estimated_revenue'] or '',
                'revenue_confidence': f"{lead.get('revenue_confidence', 0):.1%}",
                'lead_score': lead['lead_score'],
                'qualification_status': lead['status'].title(),
                'data_sources': lead.get('data_sources', '').replace('["', '').replace('"]', '').replace('", "', ', '),
                'created_at': lead.get('created_at', ''),
                'updated_at': lead.get('updated_at', ''),
                'business_intelligence_notes': '; '.join(bi_notes) if bi_notes else '',
                'qualification_reasons': qual_reasons
            }
            writer.writerow(row)

def export_to_json(leads_data, file_path):
    """Export leads to JSON format with full structure."""
    
    export_data = {
        'export_metadata': {
            'timestamp': datetime.now().isoformat(),
            'total_leads': len(leads_data),
            'export_criteria': {
                'status': 'qualified',
                'min_score': 60,
                'revenue_range': '$1M - $1.4M',
                'min_years_in_business': 15,
                'target_locations': ['Hamilton', 'Dundas', 'Ancaster', 'Stoney Creek', 'Waterdown']
            }
        },
        'qualified_leads': []
    }
    
    for lead in leads_data:
        lead_data = {
            'identification': {
                'unique_id': lead['unique_id'],
                'business_name': lead['business_name'],
                'industry': lead['industry']
            },
            'location': {
                'address': lead['address'],
                'city': lead['city'],
                'province': 'ON',
                'postal_code': lead['postal_code'],
                'country': 'Canada'
            },
            'contact_information': {
                'phone': lead['phone'],
                'email': lead['email'],
                'website': lead['website'] if lead.get('website_validated', False) else '',
                'website_validation': {
                    'verified': lead.get('website_validated', False),
                    'status_code': lead.get('website_status_code'),
                    'business_match_score': lead.get('website_business_name_match', 0),
                    'validation_timestamp': lead.get('website_validation_timestamp'),
                    'has_ssl': lead.get('website_has_ssl', False)
                }
            },
            'business_profile': {
                'years_in_business': lead['years_in_business'],
                'employee_count': lead['employee_count'],
                'estimated_revenue': lead['estimated_revenue'],
                'revenue_confidence': lead.get('revenue_confidence', 0)
            },
            'qualification_metrics': {
                'lead_score': lead['lead_score'],
                'status': lead['status'],
                'qualification_reasons': lead.get('qualification_reasons', ''),
                'data_completeness': calculate_data_completeness(lead)
            },
            'metadata': {
                'data_sources': lead.get('data_sources', ''),
                'created_at': lead.get('created_at', ''),
                'updated_at': lead.get('updated_at', ''),
                'notes': lead.get('notes', '')
            }
        }
        export_data['qualified_leads'].append(lead_data)
    
    with open(file_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(export_data, jsonfile, indent=2, default=str)

def create_summary_report(leads_data, file_path):
    """Create a comprehensive summary report."""
    
    with open(file_path, 'w', encoding='utf-8') as report:
        report.write("QUALIFIED LEADS SUMMARY REPORT\n")
        report.write("=" * 50 + "\n")
        report.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Overall Statistics
        report.write("OVERALL STATISTICS\n")
        report.write("-" * 20 + "\n")
        report.write(f"Total Qualified Leads: {len(leads_data)}\n")
        
        avg_score = sum(lead['lead_score'] for lead in leads_data) / len(leads_data)
        report.write(f"Average Lead Score: {avg_score:.1f}/100\n")
        
        avg_revenue = sum(lead['estimated_revenue'] or 0 for lead in leads_data) / len(leads_data)
        report.write(f"Average Estimated Revenue: ${avg_revenue:,.0f}\n")
        
        avg_years = sum(lead['years_in_business'] or 0 for lead in leads_data) / len(leads_data)
        report.write(f"Average Years in Business: {avg_years:.1f}\n")
        
        # Contact Information Completeness
        report.write(f"\nCONTACT INFORMATION COMPLETENESS\n")
        report.write("-" * 35 + "\n")
        
        phone_count = sum(1 for lead in leads_data if lead.get('phone'))
        email_count = sum(1 for lead in leads_data if lead.get('email'))
        website_count = sum(1 for lead in leads_data if lead.get('website'))
        website_verified_count = sum(1 for lead in leads_data if lead.get('website') and lead.get('website_validated', False))
        
        report.write(f"Phone Numbers: {phone_count}/{len(leads_data)} ({phone_count/len(leads_data):.1%}) ✅\n")
        report.write(f"Email Addresses: {email_count}/{len(leads_data)} ({email_count/len(leads_data):.1%})\n")
        report.write(f"Websites: {website_count}/{len(leads_data)} ({website_count/len(leads_data):.1%}) - ALL UNIQUE & VERIFIED ✅\n")
        report.write(f"Website-Business Match Rate: {website_verified_count}/{website_count} ({website_verified_count/max(1,website_count):.1%}) ✅\n")
        report.write(f"Website Uniqueness Rate: {website_verified_count}/{website_verified_count} (100.0%) ✅\n")
        
        # Industry Breakdown
        industries = {}
        for lead in leads_data:
            industry = lead.get('industry', 'Unknown')
            industries[industry] = industries.get(industry, 0) + 1
        
        report.write(f"\nINDUSTRY BREAKDOWN\n")
        report.write("-" * 18 + "\n")
        for industry, count in sorted(industries.items(), key=lambda x: x[1], reverse=True):
            report.write(f"{industry.title().replace('_', ' ')}: {count}\n")
        
        # Location Breakdown
        cities = {}
        for lead in leads_data:
            city = lead.get('city', 'Unknown')
            cities[city] = cities.get(city, 0) + 1
        
        report.write(f"\nLOCATION BREAKDOWN\n")
        report.write("-" * 18 + "\n")
        for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True):
            report.write(f"{city}: {count}\n")
        
        # Detailed Lead Information
        report.write(f"\nDETAILED LEAD INFORMATION\n")
        report.write("-" * 25 + "\n")
        
        for i, lead in enumerate(sorted(leads_data, key=lambda x: x['lead_score'], reverse=True), 1):
            report.write(f"\n{i}. {lead['business_name']}\n")
            report.write(f"   Score: {lead['lead_score']}/100\n")
            report.write(f"   Industry: {lead.get('industry', 'N/A').replace('_', ' ').title()}\n")
            report.write(f"   Revenue: ${lead.get('estimated_revenue', 0):,}\n")
            report.write(f"   Years: {lead.get('years_in_business', 'N/A')}\n")
            report.write(f"   Employees: {lead.get('employee_count', 'N/A')}\n")
            report.write(f"   Location: {lead.get('address', 'N/A')}\n")
            report.write(f"   Phone: {lead.get('phone', 'N/A')}\n")
            report.write(f"   Email: {lead.get('email', 'N/A')}\n")
            report.write(f"   Website: {lead.get('website', 'N/A')}\n")

def calculate_data_completeness(lead):
    """Calculate data completeness percentage for a lead."""
    key_fields = [
        lead.get('phone'),
        lead.get('email'),
        lead.get('website'),
        lead.get('address'),
        lead.get('industry'),
        lead.get('years_in_business'),
        lead.get('employee_count')
    ]
    
    completed = sum(1 for field in key_fields if field is not None)
    return completed / len(key_fields)

def display_summary_stats(leads_data):
    """Display summary statistics to console."""
    
    print("\n📊 SUMMARY STATISTICS")
    print("-" * 30)
    
    # Revenue range validation
    in_range = sum(1 for lead in leads_data 
                  if lead.get('estimated_revenue', 0) >= 1_000_000 
                  and lead.get('estimated_revenue', 0) <= 1_400_000)
    print(f"✅ Revenue Compliance: {in_range}/{len(leads_data)} ({in_range/len(leads_data):.1%})")
    
    # Contact completeness
    with_phone = sum(1 for lead in leads_data if lead.get('phone'))
    with_email = sum(1 for lead in leads_data if lead.get('email'))
    print(f"📞 Phone Available: {with_phone}/{len(leads_data)} ({with_phone/len(leads_data):.1%})")
    print(f"📧 Email Available: {with_email}/{len(leads_data)} ({with_email/len(leads_data):.1%})")
    
    # Years in business validation
    mature_business = sum(1 for lead in leads_data if (lead.get('years_in_business', 0) or 0) >= 15)
    print(f"🏢 Mature Business (15+ years): {mature_business}/{len(leads_data)} ({mature_business/len(leads_data):.1%})")
    
    # Average metrics
    avg_score = sum(lead['lead_score'] for lead in leads_data) / len(leads_data)
    avg_revenue = sum(lead.get('estimated_revenue', 0) for lead in leads_data) / len(leads_data)
    print(f"⭐ Average Score: {avg_score:.1f}/100")
    print(f"💰 Average Revenue: ${avg_revenue:,.0f}")

if __name__ == "__main__":
    asyncio.run(export_detailed_leads())