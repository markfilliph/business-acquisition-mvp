#!/usr/bin/env python3
"""
Revalidate Existing Leads with Enhanced Validation
Applies new content validation and website search to existing leads.
"""
import sys
import asyncio
import json
sys.path.insert(0, '/mnt/d/AI_Automated_Potential_Business_outreach')

from src.integrations.website_content_validator import WebsiteContentValidator
from src.integrations.web_search import search_web
from datetime import datetime


async def revalidate_leads(input_file: str):
    """Revalidate existing leads with new features."""

    print(f"🔄 Revalidating Leads with Enhanced Features")
    print(f"{'='*70}")
    print(f"Input: {input_file}")
    print(f"{'='*70}\n")

    # Load existing leads
    with open(input_file, 'r') as f:
        data = json.load(f)

    original_leads = data['leads']
    print(f"📊 Original leads: {len(original_leads)}\n")

    # Retail/non-profit exclusions
    excluded_keywords = {
        'supermarket', 'convenience', 'art supplies', 'community bikes',
        'community', 'institute', 'foundation', 'society', 'association',
        'non-profit', 'not-for-profit', 'charity', 'centre', 'center',
        'fastenal'  # Retail chain
    }

    content_validator = WebsiteContentValidator()

    validated_leads = []
    stats = {
        'original': len(original_leads),
        'retail_nonprofit': 0,
        'content_failed': 0,
        'website_found': 0,
        'passed': 0
    }

    for i, lead in enumerate(original_leads, 1):
        business_name = lead['business_name']
        website = lead.get('website')

        print(f"{i}. {business_name}")

        # Check retail/non-profit exclusions
        name_lower = business_name.lower()
        if any(keyword in name_lower for keyword in excluded_keywords):
            stats['retail_nonprofit'] += 1
            print(f"   ❌ EXCLUDED: Retail/Non-Profit")
            continue

        # Try to find missing website
        if not website:
            print(f"   🔍 Searching for website...")
            results = await search_web(f"{business_name} Hamilton Ontario", max_results=3)

            if results:
                # Validate first result
                candidate_url = results[0]['url']

                # Simple validation: check if accessible
                import aiohttp
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(candidate_url, timeout=5) as response:
                            if response.status in [200, 403, 405]:
                                website = candidate_url
                                lead['website'] = website
                                stats['website_found'] += 1
                                print(f"   ✅ Found: {website}")
                except Exception:
                    print(f"   ⚠️  Website search failed")

        # Content validation if website exists
        if website:
            is_valid, reason, details = await content_validator.validate_business_website(
                business_name,
                website
            )

            if not is_valid:
                stats['content_failed'] += 1
                print(f"   ❌ CONTENT: {reason}")
                continue

            confidence = details.get('confidence', 'medium')
            green_flags = details.get('green_flag_count', 0)

            if green_flags > 0:
                print(f"   ✅ VALIDATED [{confidence} confidence, {green_flags} green flags]")
            else:
                print(f"   ✅ VALIDATED")

            # Add validation metadata
            lead['validation'] = {
                'content_validated': True,
                'confidence': confidence,
                'green_flags': green_flags,
                'red_flags': details.get('red_flag_count', 0)
            }
        else:
            print(f"   ✅ PASSED (no website to validate)")
            lead['validation'] = {
                'content_validated': False,
                'confidence': 'low',
                'note': 'No website available for content validation'
            }

        validated_leads.append(lead)
        stats['passed'] += 1

    # Create new output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON output
    json_output = f"output/validated_leads_{timestamp}.json"
    with open(json_output, 'w') as f:
        json.dump({
            'generated_at': timestamp,
            'original_count': stats['original'],
            'validated_count': len(validated_leads),
            'criteria': data.get('criteria', {}),
            'validation_summary': stats,
            'leads': validated_leads
        }, f, indent=2)

    # Text summary output
    txt_output = f"output/validated_leads_summary_{timestamp}.txt"
    with open(txt_output, 'w') as f:
        f.write("ENHANCED LEAD VALIDATION - SUMMARY REPORT\n")
        f.write("="*70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Run ID: {timestamp}\n\n")

        f.write("VALIDATION RESULTS\n")
        f.write("-"*70 + "\n")
        f.write(f"Original Leads: {stats['original']}\n")
        f.write(f"Validated Leads: {stats['passed']}\n\n")

        f.write("REJECTION BREAKDOWN\n")
        f.write("-"*70 + "\n")
        f.write(f"🏪 Retail/Non-Profit Excluded: {stats['retail_nonprofit']}\n")
        f.write(f"📄 Content Validation Failed: {stats['content_failed']}\n")
        f.write(f"🔍 Websites Found: {stats['website_found']}\n\n")

        f.write("CRITERIA ENFORCEMENT\n")
        f.write("-"*70 + "\n")
        criteria = data.get('criteria', {})
        f.write(f"Revenue Range: ${criteria.get('revenue_min', 0):,} - ${criteria.get('revenue_max', 0):,}\n")
        f.write(f"Minimum Age: {criteria.get('min_years', 0)}+ years\n")
        f.write(f"Maximum Employees: {criteria.get('max_employees', 0)}\n\n")

        f.write("VALIDATED LEADS\n")
        f.write("="*70 + "\n\n")

        for i, lead in enumerate(validated_leads, 1):
            f.write(f"{i}. {lead['business_name']}\n")
            f.write(f"   Address: {lead['address']}, {lead['city']}, ON\n")
            f.write(f"   Phone: {lead['phone']}\n")
            if lead.get('website'):
                f.write(f"   Website: {lead['website']}\n")
            f.write(f"   Industry: {lead['industry']}\n")
            f.write(f"   Revenue: ${lead['estimated_revenue']:,}\n")
            f.write(f"   Years: {lead['years_in_business']}\n")
            f.write(f"   Employees: {lead['employee_count']}\n")

            validation = lead.get('validation', {})
            if validation.get('content_validated'):
                conf = validation.get('confidence', 'medium')
                green = validation.get('green_flags', 0)
                f.write(f"   ✅ Content Validated: {conf} confidence ({green} B2B indicators)\n")
            else:
                f.write(f"   ⚠️  {validation.get('note', 'Not validated')}\n")
            f.write("\n")

    print(f"\n{'='*70}")
    print(f"✅ VALIDATION COMPLETE")
    print(f"\n📊 Results:")
    print(f"   Original: {stats['original']}")
    print(f"   Validated: {stats['passed']}")
    print(f"   Excluded (Retail/Non-Profit): {stats['retail_nonprofit']}")
    print(f"   Content Validation Failed: {stats['content_failed']}")
    print(f"   Websites Found: {stats['website_found']}")
    print(f"\n📄 Output Files:")
    print(f"   JSON: {json_output}")
    print(f"   Summary: {txt_output}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Revalidate existing leads")
    parser.add_argument('input_file', help="Path to JSON file with leads")
    args = parser.parse_args()

    try:
        asyncio.run(revalidate_leads(args.input_file))
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
