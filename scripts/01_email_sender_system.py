#!/usr/bin/env python3
"""
Email Automation System for Business Acquisition Outreach
Sends personalized emails to qualified prospects with tracking
"""

import smtplib
import csv
import json
import time
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import List, Dict, Optional
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Prospect:
    business_name: str
    owner_name: str
    email: str
    phone: str
    website: str
    industry: str
    revenue: str
    years: int
    score: int

@dataclass
class EmailTemplate:
    subject: str
    body: str
    approach: str  # 'legacy', 'growth', 'direct'

class EmailSender:
    def __init__(self, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.prospects: List[Prospect] = []
        self.templates: Dict[str, List[EmailTemplate]] = {}
        self.sent_log: List[Dict] = []
        
    def load_prospects(self, csv_file: str) -> None:
        """Load prospects from CSV file"""
        try:
            with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Handle years field that might contain non-numeric values
                    years_str = str(row['Years in Business']).replace('+', '').replace('~', '')
                    try:
                        years = int(years_str)
                    except ValueError:
                        years = 25  # Default for non-numeric values
                    
                    prospect = Prospect(
                        business_name=row['Business Name'],
                        owner_name=row['Owner Name'],
                        email=row.get('Email', ''),  # Will need to be populated
                        phone=row['Phone'],
                        website=row['Website'],
                        industry=row['Industry'],
                        revenue=row['Revenue Estimate'],
                        years=years,
                        score=int(row['Acquisition Score'])
                    )
                    self.prospects.append(prospect)
            logger.info(f"Loaded {len(self.prospects)} prospects")
        except Exception as e:
            logger.error(f"Error loading prospects: {e}")
            
    def load_email_templates(self) -> None:
        """Load email templates from the final templates file"""
        # Hamilton X Packaging templates
        hxpp_templates = [
            EmailTemplate(
                subject="30 Years of Export Packaging Excellence - HXPP",
                approach="legacy",
                body="""Dear Hamilton X Packaging Leadership,

I was researching Hamilton's most established family operations when HXPP caught my attention for your specialized export crating and packaging expertise since 1994.

Thirty years of serving advanced manufacturing companies in the GTA demonstrates remarkable consistency in a highly technical field. Your ability to handle custom packaging for any size or weight component shows the kind of specialized knowledge that creates lasting competitive advantages.

As someone who works with family-operated businesses, I'm curious about your long-term vision for HXPP. Have you considered how to ensure your specialized packaging expertise continues while exploring opportunities for expansion?

I work with buyers who deeply respect what family operators have built and focus on preserving operational excellence while expanding market reach.

Would you be open to a brief conversation about how other packaging specialists have successfully planned for their next growth phase?

Best regards,
Mark Fillingham
Acquisition Advisory Services"""
            ),
            EmailTemplate(
                subject="Export Growth Opportunities for Packaging Specialists",
                approach="growth",
                body="""Dear HXPP Team,

Your 30 years of specialized export crating expertise positions HXPP perfectly for significant expansion across Ontario's booming manufacturing sector.

I see tremendous untapped potential: advanced manufacturing is growing rapidly, and your custom packaging capabilities could serve a much larger market. Your proven ability to handle complex export requirements is exactly what expanding manufacturers need.

I work with growth partners who specialize in scaling specialized service businesses. They provide:
- Geographic expansion capital
- Advanced equipment investment  
- Digital marketing to reach more manufacturers
- Operational scaling while preserving family culture

Your technical expertise and manufacturing relationships would remain the foundation while significantly expanding your service territory.

Would you be interested in exploring how a partnership could scale HXPP's capabilities across Ontario's entire manufacturing base?

Best regards,
Mark Fillingham
Acquisition Advisory Services"""
            ),
            EmailTemplate(
                subject="Acquisition Interest - HXPP Packaging Expertise",
                approach="direct",
                body="""Dear HXPP Ownership,

I represent buyers seeking established packaging specialists with proven export capabilities. Hamilton X Packaging's 30-year reputation and specialized technical expertise make it exactly what they value.

We're prepared to offer:
- Confidential valuation recognizing your 30-year family investment
- Preservation of HXPP's specialized packaging capabilities
- Investment in advanced equipment and facility expansion
- Retention of existing manufacturing relationships
- Significant financial returns for your family's technical expertise

Our buyers understand that businesses like HXPP aren't commodity operations - they're technical specialists with irreplaceable knowledge and proven export capabilities.

Your custom packaging expertise and manufacturing industry relationships create substantial value that we're ready to recognize financially.

Would you consider a confidential discussion about what this acquisition opportunity could provide?

Respectfully,
Mark Fillingham
Acquisition Advisory Services"""
            )
        ]
        
        # G.S. Dunn templates
        gsdunn_templates = [
            EmailTemplate(
                subject="30+ Years of Mustard Processing Excellence - G.S. Dunn",
                approach="legacy",
                body="""Dear Luis Rivas and G.S. Dunn Leadership,

I was researching Hamilton's most specialized food manufacturers when G.S. Dunn Limited stood out for your unique focus on mustard processing over the past 30+ years.

Your niche expertise in mustard processing represents something increasingly valuable in today's market - deep specialization that creates unassailable competitive advantages. This level of focused knowledge and established brand recognition is exactly what discerning buyers seek.

As someone who works with specialized food processors, I'm curious about your long-term vision for G.S. Dunn. Have you considered how to ensure your mustard processing expertise continues while exploring opportunities to expand your market reach?

I work with buyers who appreciate niche market leaders and focus on preserving specialized knowledge while scaling operations.

Would you be open to a brief conversation about how other specialty processors have successfully planned for growth while maintaining their technical expertise?

Best regards,
Mark Fillingham
Acquisition Advisory Services"""
            ),
            EmailTemplate(
                subject="Specialty Food Processing Growth - Mustard Market Expansion",
                approach="growth",
                body="""Dear Luis and G.S. Dunn Team,

Your 30+ years of mustard processing expertise positions G.S. Dunn perfectly for significant expansion in the growing specialty condiment market.

I see incredible growth potential: specialty food markets are booming, and your established processing knowledge could capture much larger market share. Private label opportunities, retail expansion, and potentially export markets could multiply your current operations.

I work with growth partners who specialize in scaling niche food processors. They provide:
- Market expansion capital
- Distribution network access
- Retail partnership development
- Production scaling expertise

Your specialized mustard processing knowledge would remain the foundation while significantly expanding your product reach and market presence.

Would you be interested in exploring how a partnership could scale G.S. Dunn's processing capabilities into new markets while preserving your technical expertise?

Best regards,
Mark Fillingham
Acquisition Advisory Services"""
            ),
            EmailTemplate(
                subject="Acquisition Interest - G.S. Dunn Specialty Processing",
                approach="direct",
                body="""Dear G.S. Dunn Ownership,

I represent buyers seeking established specialty food processors with proven niche market expertise. G.S. Dunn's 30+ year focus on mustard processing and established brand recognition make it exactly what they value.

We're prepared to offer:
- Confidential valuation recognizing your specialized market position
- Preservation of G.S. Dunn's mustard processing expertise
- Investment in production capacity and technology upgrades
- Retention of existing brand recognition and processing knowledge
- Significant financial returns for decades of niche market development

Our buyers understand that businesses like G.S. Dunn aren't commodity food processors - they're specialists with irreplaceable technical knowledge and established market positions.

Your mustard processing expertise and brand recognition create substantial value in the growing specialty food market.

Would you consider a confidential discussion about this acquisition opportunity?

Respectfully,
Mark Fillingham
Acquisition Advisory Services"""
            )
        ]
        
        self.templates = {
            "Hamilton X Packaging": hxpp_templates,
            "G.S. Dunn Limited": gsdunn_templates
        }
        logger.info(f"Loaded templates for {len(self.templates)} businesses")
    
    def create_email(self, prospect: Prospect, template: EmailTemplate, sender_email: str) -> MIMEMultipart:
        """Create formatted email message"""
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = prospect.email
        msg['Subject'] = template.subject
        
        # Add email body
        msg.attach(MIMEText(template.body, 'plain'))
        
        return msg
    
    def send_email(self, prospect: Prospect, template: EmailTemplate, 
                  sender_email: str, sender_password: str, dry_run: bool = True) -> bool:
        """Send email to prospect with tracking"""
        try:
            if not prospect.email:
                logger.warning(f"No email found for {prospect.business_name}")
                return False
                
            msg = self.create_email(prospect, template, sender_email)
            
            if dry_run:
                logger.info(f"[DRY RUN] Would send {template.approach} email to {prospect.business_name}")
                logger.info(f"Subject: {template.subject}")
                self.log_email_sent(prospect, template, "dry_run")
                return True
            
            # Send actual email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            
            text = msg.as_string()
            server.sendmail(sender_email, prospect.email, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {prospect.business_name} ({template.approach})")
            self.log_email_sent(prospect, template, "sent")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {prospect.business_name}: {e}")
            self.log_email_sent(prospect, template, "failed", str(e))
            return False
    
    def log_email_sent(self, prospect: Prospect, template: EmailTemplate, 
                      status: str, error: str = None) -> None:
        """Log sent email for tracking"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "business_name": prospect.business_name,
            "email": prospect.email,
            "subject": template.subject,
            "approach": template.approach,
            "status": status,
            "error": error
        }
        self.sent_log.append(log_entry)
    
    def save_sent_log(self, filename: str = "data/email_sent_log.json") -> None:
        """Save sent email log to file"""
        try:
            with open(filename, 'w') as file:
                json.dump(self.sent_log, file, indent=2)
            logger.info(f"Email log saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving email log: {e}")
    
    def run_campaign(self, sender_email: str, sender_password: str, 
                    approach: str = "legacy", dry_run: bool = True, 
                    delay_seconds: int = 300) -> None:
        """Run email campaign for all prospects"""
        logger.info(f"Starting email campaign - Approach: {approach}, Dry Run: {dry_run}")
        
        for prospect in self.prospects:
            if prospect.business_name in self.templates:
                # Find template with matching approach
                templates = self.templates[prospect.business_name]
                template = next((t for t in templates if t.approach == approach), templates[0])
                
                # Send email
                success = self.send_email(prospect, template, sender_email, sender_password, dry_run)
                
                if success and not dry_run:
                    logger.info(f"Waiting {delay_seconds} seconds before next email...")
                    time.sleep(delay_seconds)  # 5 minute delay between emails
        
        # Save log
        self.save_sent_log()
        logger.info("Campaign completed")

def main():
    """Main execution function"""
    print("🚀 Business Acquisition Email Campaign System")
    print("=" * 50)
    
    # Initialize email sender
    sender = EmailSender()
    
    # Load data
    sender.load_prospects("data/final_target_prospects.csv")
    sender.load_email_templates()
    
    print(f"\n📊 Campaign Summary:")
    print(f"• Prospects loaded: {len(sender.prospects)}")
    print(f"• Template sets: {len(sender.templates)}")
    
    # Configuration
    sender_email = input("\nEnter sender email: ").strip()
    
    print("\nApproach options:")
    print("1. legacy - Legacy preservation focus")
    print("2. growth - Growth partnership focus") 
    print("3. direct - Direct acquisition approach")
    approach = input("Select approach (1-3): ").strip()
    
    approach_map = {"1": "legacy", "2": "growth", "3": "direct"}
    selected_approach = approach_map.get(approach, "legacy")
    
    dry_run = input("Run in dry-run mode? (y/n): ").strip().lower() == 'y'
    
    if not dry_run:
        sender_password = input("Enter sender email password: ").strip()
        delay = int(input("Delay between emails (seconds, default 300): ") or "300")
    else:
        sender_password = ""
        delay = 0
    
    print(f"\n🎯 Running campaign:")
    print(f"• Approach: {selected_approach}")
    print(f"• Dry run: {dry_run}")
    print(f"• Delay: {delay}s")
    
    # Run campaign
    sender.run_campaign(
        sender_email=sender_email,
        sender_password=sender_password,
        approach=selected_approach,
        dry_run=dry_run,
        delay_seconds=delay
    )
    
    print("\n✅ Campaign completed! Check data/email_sent_log.json for details.")

if __name__ == "__main__":
    main()