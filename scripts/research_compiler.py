#!/usr/bin/env python3
"""
Research Compiler - Business Intelligence Formatter
Formats business research data for easy copy/paste into Google Sheets and email templates.
"""

import json
from datetime import datetime
from pathlib import Path
import re

class ResearchCompiler:
    def __init__(self):
        """Initialize research compiler."""
        self.research_data = {}
        
    def compile_business_profile(self, business_data):
        """Compile complete business profile from research data."""
        profile = {
            'basic_info': {
                'business_name': business_data.get('business_name', ''),
                'owner_name': business_data.get('owner_name', ''),
                'website': business_data.get('website', ''),
                'phone': business_data.get('phone', ''),
                'address': business_data.get('address', ''),
                'years_in_business': business_data.get('years_in_business', ''),
                'google_rating': business_data.get('google_rating', ''),
                'review_count': business_data.get('review_count', '')
            },
            'financial_estimates': {
                'revenue_estimate': business_data.get('revenue_estimate', ''),
                'sde_estimate': business_data.get('sde_estimate', ''),
                'employee_count': business_data.get('employee_count', ''),
                'acquisition_score': business_data.get('acquisition_score', '')
            },
            'digital_presence': {
                'website_last_updated': business_data.get('website_last_updated', ''),
                'seo_opportunities': business_data.get('seo_opportunities', []),
                'social_media_presence': business_data.get('social_media_presence', ''),
                'online_marketing_potential': business_data.get('online_marketing_potential', '')
            },
            'competitive_analysis': {
                'main_competitors': business_data.get('main_competitors', []),
                'market_position': business_data.get('market_position', ''),
                'unique_selling_proposition': business_data.get('unique_selling_proposition', ''),
                'competitive_advantages': business_data.get('competitive_advantages', [])
            },
            'acquisition_insights': {
                'buy_then_build_opportunities': business_data.get('buy_then_build_opportunities', []),
                'risk_factors': business_data.get('risk_factors', []),
                'growth_potential': business_data.get('growth_potential', ''),
                'recommended_approach': business_data.get('recommended_approach', '')
            }
        }
        
        return profile
        
    def format_for_google_sheets(self, profile):
        """Format profile data for Google Sheets row."""
        basic = profile['basic_info']
        financial = profile['financial_estimates']
        
        # Create single-row format for prospects sheet
        sheet_row = [
            basic['business_name'],
            basic['owner_name'],
            '',  # Email (to be filled later)
            basic['phone'],
            basic['website'],
            financial['revenue_estimate'],
            basic['years_in_business'],
            financial['acquisition_score'],
            '',  # Initial Email Sent
            '',  # Follow-up 1
            '',  # Follow-up 2
            'No Reply',  # Response Status
            '',  # Response Date
            '',  # Meeting Scheduled
            self._compile_notes(profile),  # Notes
            'Research completed',  # Next Action
            self._determine_priority(financial.get('acquisition_score', 0))  # Priority
        ]
        
        return sheet_row
        
    def _compile_notes(self, profile):
        """Compile key insights into notes field."""
        notes = []
        
        # Add key opportunities
        opportunities = profile['acquisition_insights']['buy_then_build_opportunities']
        if opportunities:
            notes.append(f"Opportunities: {', '.join(opportunities[:2])}")
            
        # Add key risks
        risks = profile['acquisition_insights']['risk_factors']
        if risks:
            notes.append(f"Risks: {', '.join(risks[:2])}")
            
        # Add recommended approach
        approach = profile['acquisition_insights']['recommended_approach']
        if approach:
            notes.append(f"Approach: {approach}")
            
        return ' | '.join(notes)
        
    def _determine_priority(self, acquisition_score):
        """Determine priority based on acquisition score."""
        try:
            score = int(acquisition_score)
            if score >= 80:
                return 'High'
            elif score >= 60:
                return 'Medium'
            else:
                return 'Low'
        except (ValueError, TypeError):
            return 'Medium'
    
    def format_for_email_template(self, profile):
        """Format data for personalized email creation."""
        basic = profile['basic_info']
        insights = profile['acquisition_insights']
        digital = profile['digital_presence']
        
        email_data = {
            'business_name': basic['business_name'],
            'owner_name': basic['owner_name'],
            'years_in_business': basic['years_in_business'],
            'key_strength': self._extract_key_strength(profile),
            'main_opportunity': self._extract_main_opportunity(profile),
            'approach_angle': insights.get('recommended_approach', 'legacy'),
            'personalization_points': self._extract_personalization_points(profile)
        }
        
        return email_data
        
    def _extract_key_strength(self, profile):
        """Extract the key business strength for email personalization."""
        advantages = profile['competitive_analysis']['competitive_advantages']
        if advantages:
            return advantages[0]
            
        # Fall back to other indicators
        rating = profile['basic_info']['google_rating']
        years = profile['basic_info']['years_in_business']
        
        if rating and float(rating) > 4.5:
            return f"exceptional {rating}-star customer rating"
        elif years and int(years) > 20:
            return f"{years} years of proven market presence"
        else:
            return "strong market position"
            
    def _extract_main_opportunity(self, profile):
        """Extract the main growth opportunity."""
        opportunities = profile['acquisition_insights']['buy_then_build_opportunities']
        if opportunities:
            return opportunities[0]
            
        # Fall back to digital opportunities
        seo_opps = profile['digital_presence']['seo_opportunities']
        if seo_opps:
            return f"digital growth through {seo_opps[0]}"
            
        return "operational scaling and digital transformation"
        
    def _extract_personalization_points(self, profile):
        """Extract specific details for email personalization."""
        points = []
        
        basic = profile['basic_info']
        if basic['google_rating'] and basic['review_count']:
            points.append(f"{basic['review_count']} customer reviews with {basic['google_rating']} rating")
            
        if basic['years_in_business']:
            points.append(f"established in {datetime.now().year - int(basic['years_in_business'])}")
            
        digital = profile['digital_presence']
        if digital['website_last_updated']:
            points.append(f"website last updated {digital['website_last_updated']}")
            
        return points[:3]  # Limit to top 3 points
    
    def generate_meeting_brief(self, profile):
        """Generate meeting preparation brief."""
        basic = profile['basic_info']
        financial = profile['financial_estimates']
        insights = profile['acquisition_insights']
        competitive = profile['competitive_analysis']
        
        brief = {
            'quick_reference': {
                'business': basic['business_name'],
                'owner': basic['owner_name'],
                'revenue': financial['revenue_estimate'],
                'score': financial['acquisition_score'],
                'key_facts': [
                    f"{basic['years_in_business']} years in business",
                    f"Google rating: {basic['google_rating']}",
                    f"Estimated employees: {financial['employee_count']}"
                ]
            },
            'strategic_questions': [
                "How has the business evolved since you started?",
                "What are your biggest operational challenges today?",
                "Have you thought about succession planning?",
                "What would need to happen for you to consider a transition?",
                "How important is preserving the company culture?",
                "What are your growth aspirations for the next 5 years?",
                "What keeps you up at night about the business?"
            ],
            'value_propositions': insights.get('buy_then_build_opportunities', []),
            'potential_objections': [
                "Not ready to sell yet",
                "Concerned about employee welfare",
                "Emotional attachment to business",
                "Valuation expectations too high",
                "Distrust of buyers"
            ],
            'deal_structure_options': [
                "Asset purchase with earnout",
                "Stock purchase with seller financing",
                "Management buyout structure",
                "Gradual transition over 12-24 months"
            ]
        }
        
        return brief
    
    def export_formatted_data(self, profile, output_format='all'):
        """Export data in various formats."""
        exports = {}
        
        if output_format in ['all', 'sheets']:
            exports['google_sheets_row'] = self.format_for_google_sheets(profile)
            
        if output_format in ['all', 'email']:
            exports['email_template_data'] = self.format_for_email_template(profile)
            
        if output_format in ['all', 'meeting']:
            exports['meeting_brief'] = self.generate_meeting_brief(profile)
            
        return exports
    
    def save_research_file(self, profile, filename=None):
        """Save complete research profile to file."""
        if not filename:
            business_name = profile['basic_info']['business_name'].replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"../data/research_{business_name}_{timestamp}.json"
            
        with open(filename, 'w') as f:
            json.dump(profile, f, indent=2)
            
        print(f"Research saved to: {filename}")
        return filename

def main():
    """Main function for command line usage."""
    compiler = ResearchCompiler()
    
    print("Business Research Compiler")
    print("=" * 30)
    
    # Example usage with sample data
    sample_data = {
        'business_name': 'Hamilton Manufacturing Co.',
        'owner_name': 'John Smith',
        'website': 'hamiltonmfg.com',
        'phone': '(905) 555-0123',
        'address': '123 Industrial Dr, Hamilton, ON',
        'years_in_business': '22',
        'google_rating': '4.6',
        'review_count': '47',
        'revenue_estimate': '$1.5M',
        'sde_estimate': '$300K',
        'employee_count': '8-12',
        'acquisition_score': '85',
        'website_last_updated': '2019',
        'seo_opportunities': ['local SEO', 'mobile optimization'],
        'social_media_presence': 'minimal',
        'buy_then_build_opportunities': ['digital marketing', 'e-commerce expansion', 'process automation'],
        'risk_factors': ['aging owner', 'dated technology'],
        'recommended_approach': 'legacy preservation'
    }
    
    print("\nCompiling sample business profile...")
    profile = compiler.compile_business_profile(sample_data)
    
    print("\nExporting in all formats...")
    exports = compiler.export_formatted_data(profile)
    
    print("\n📊 GOOGLE SHEETS ROW:")
    print(exports['google_sheets_row'])
    
    print("\n✉️ EMAIL TEMPLATE DATA:")
    email_data = exports['email_template_data']
    for key, value in email_data.items():
        print(f"  {key}: {value}")
        
    print("\n📋 MEETING BRIEF PREVIEW:")
    brief = exports['meeting_brief']
    print(f"  Business: {brief['quick_reference']['business']}")
    print(f"  Score: {brief['quick_reference']['score']}")
    print(f"  Top Questions: {brief['strategic_questions'][:2]}")
    
    # Save complete research
    filename = compiler.save_research_file(profile)
    
    print(f"\n✅ Research compilation complete!")
    print(f"Data ready for copy/paste into CRM and email templates.")

if __name__ == "__main__":
    main()