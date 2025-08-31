#!/usr/bin/env python3
"""
Email Finder - Business Contact Discovery
Implements the email finding logic from Claude Instructions Phase 4.
"""

import requests
from urllib.parse import urlparse
import re
from email_validator import validate_email, EmailNotValidError
import time
from pathlib import Path

class EmailFinder:
    def __init__(self):
        """Initialize email finder with common patterns."""
        self.common_patterns = [
            '{first}@{domain}',
            '{first}.{last}@{domain}',
            '{first}{last}@{domain}',
            '{first_initial}{last}@{domain}',
            '{first_initial}.{last}@{domain}',
            'info@{domain}',
            'contact@{domain}',
            'admin@{domain}',
            'owner@{domain}',
            'sales@{domain}'
        ]
        
        self.contact_pages = [
            '/contact',
            '/about',
            '/about-us',
            '/team',
            '/staff',
            '/contact-us'
        ]
        
    def generate_email_patterns(self, first_name, last_name, domain):
        """Generate possible email patterns for a person."""
        if not first_name or not domain:
            return []
            
        # Clean inputs
        first = first_name.lower().strip()
        last = last_name.lower().strip() if last_name else ''
        domain = domain.lower().strip()
        
        # Remove www. if present
        if domain.startswith('www.'):
            domain = domain[4:]
            
        emails = []
        
        for pattern in self.common_patterns:
            try:
                email = pattern.format(
                    first=first,
                    last=last,
                    first_initial=first[0] if first else '',
                    domain=domain
                )
                emails.append(email)
            except (IndexError, KeyError):
                continue
                
        return list(set(emails))  # Remove duplicates
    
    def search_website_for_emails(self, website_url):
        """Search website for email addresses."""
        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url
            
        found_emails = []
        
        # Email regex pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Check main page and contact pages
        pages_to_check = [website_url] + [website_url.rstrip('/') + page for page in self.contact_pages]
        
        for page_url in pages_to_check:
            try:
                response = requests.get(page_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code == 200:
                    # Find emails in page content
                    emails = re.findall(email_pattern, response.text, re.IGNORECASE)
                    
                    # Filter out common false positives
                    filtered_emails = []
                    for email in emails:
                        email = email.lower()
                        if not any(exclude in email for exclude in [
                            'example.com', 'test.com', 'placeholder', 'yourname',
                            'noreply', 'donotreply', 'no-reply'
                        ]):
                            filtered_emails.append(email)
                    
                    found_emails.extend(filtered_emails)
                    
                time.sleep(1)  # Be respectful
                
            except Exception as e:
                print(f"Error checking {page_url}: {e}")
                continue
                
        return list(set(found_emails))  # Remove duplicates
    
    def validate_email_address(self, email):
        """Validate email address format."""
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False
    
    def google_search_patterns(self, owner_name, business_name, domain):
        """Generate Google search queries for finding emails."""
        domain_clean = domain.replace('www.', '').replace('http://', '').replace('https://', '')
        
        search_queries = [
            f'"{owner_name}" "{business_name}" email',
            f'site:{domain_clean} email',
            f'"{business_name}" contact email',
            f'"{owner_name}" "{domain_clean}" email',
            f'"{business_name}" owner email contact',
            f'"{owner_name}" {domain_clean} -linkedin -facebook'
        ]
        
        return search_queries
    
    def hunter_io_strategy(self, domain, first_name=None, last_name=None):
        """Generate Hunter.io search strategy (manual process description)."""
        strategy = {
            'domain_search': f"Search domain: {domain}",
            'patterns_to_try': [],
            'verification_needed': True
        }
        
        if first_name and last_name:
            strategy['name_search'] = f"Search: {first_name} {last_name} at {domain}"
            strategy['patterns_to_try'] = self.generate_email_patterns(first_name, last_name, domain)
        
        return strategy
    
    def find_business_email(self, business_name, owner_name=None, website=None):
        """Main email finding function."""
        results = {
            'business_name': business_name,
            'owner_name': owner_name,
            'website': website,
            'found_emails': [],
            'suggested_patterns': [],
            'google_searches': [],
            'hunter_strategy': {},
            'manual_checks': []
        }
        
        if not website:
            print(f"No website provided for {business_name}")
            return results
            
        # Extract domain
        try:
            domain = urlparse(website).netloc or website
            domain = domain.replace('www.', '')
        except:
            domain = website.replace('www.', '').replace('http://', '').replace('https://', '')
        
        # 1. Search website for emails
        print(f"Searching website: {website}")
        found_emails = self.search_website_for_emails(website)
        results['found_emails'] = found_emails
        
        # 2. Generate email patterns if owner name provided
        if owner_name:
            name_parts = owner_name.split()
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[-1] if len(name_parts) > 1 else ''
            
            patterns = self.generate_email_patterns(first_name, last_name, domain)
            results['suggested_patterns'] = patterns
            
            # 3. Google search queries
            results['google_searches'] = self.google_search_patterns(owner_name, business_name, domain)
            
            # 4. Hunter.io strategy
            results['hunter_strategy'] = self.hunter_io_strategy(domain, first_name, last_name)
        
        # 5. Manual check recommendations
        results['manual_checks'] = [
            f"Check {website.rstrip('/')}{page}" for page in self.contact_pages
        ]
        
        return results
    
    def print_results(self, results):
        """Print formatted results."""
        print(f"\n{'='*50}")
        print(f"EMAIL SEARCH RESULTS: {results['business_name']}")
        print(f"{'='*50}")
        
        if results['found_emails']:
            print(f"\n✅ FOUND EMAILS ON WEBSITE:")
            for email in results['found_emails']:
                validity = "✓ Valid" if self.validate_email_address(email) else "✗ Invalid"
                print(f"   {email} ({validity})")
        else:
            print(f"\n❌ No emails found on website")
            
        if results['suggested_patterns']:
            print(f"\n💡 SUGGESTED EMAIL PATTERNS:")
            for pattern in results['suggested_patterns'][:5]:  # Show top 5
                validity = "✓ Valid format" if self.validate_email_address(pattern) else "✗ Invalid format"
                print(f"   {pattern} ({validity})")
                
        print(f"\n🔍 GOOGLE SEARCH QUERIES:")
        for query in results['google_searches']:
            print(f"   \"{query}\"")
            
        if results['hunter_strategy']:
            print(f"\n🎯 HUNTER.IO STRATEGY:")
            strategy = results['hunter_strategy']
            print(f"   Domain Search: {strategy.get('domain_search', '')}")
            if 'name_search' in strategy:
                print(f"   Name Search: {strategy['name_search']}")
                
        print(f"\n📋 MANUAL CHECKS:")
        for check in results['manual_checks']:
            print(f"   {check}")

def main():
    """Main function for command line usage."""
    finder = EmailFinder()
    
    print("Business Email Finder")
    print("=" * 30)
    
    business_name = input("Business name: ").strip()
    owner_name = input("Owner name (optional): ").strip() or None
    website = input("Website: ").strip()
    
    if not business_name or not website:
        print("Business name and website are required.")
        return
        
    print("\nSearching for email addresses...")
    results = finder.find_business_email(business_name, owner_name, website)
    finder.print_results(results)
    
    # Save results to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"../data/email_search_{business_name.replace(' ', '_')}_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"Email Search Results: {business_name}\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write("=" * 50 + "\n\n")
        
        f.write("Found Emails:\n")
        for email in results['found_emails']:
            f.write(f"  {email}\n")
            
        f.write("\nSuggested Patterns:\n")
        for pattern in results['suggested_patterns']:
            f.write(f"  {pattern}\n")
            
        f.write("\nGoogle Search Queries:\n")
        for query in results['google_searches']:
            f.write(f"  {query}\n")
    
    print(f"\nResults saved to: {filename}")

if __name__ == "__main__":
    main()