#!/usr/bin/env python3
"""
Follow-up Email Automation System
Sends automated follow-up sequences to non-responders
"""

import json
import time
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FollowUpSequence:
    business_name: str
    sequence_name: str
    current_step: int
    last_sent_date: datetime
    next_send_date: datetime
    completed: bool = False
    responded: bool = False
    unsubscribed: bool = False

class FollowUpAutomation:
    def __init__(self, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sequences: List[FollowUpSequence] = []
        self.follow_up_templates = self.load_follow_up_templates()
        
    def load_follow_up_templates(self) -> Dict[str, List[Dict]]:
        """Load follow-up email templates for different sequences"""
        
        # Hamilton X Packaging follow-up sequence
        hxpp_sequence = [
            {
                "delay_days": 7,
                "subject": "Quick follow-up - HXPP packaging expansion",
                "body": """Dear Hamilton X Packaging Team,

I wanted to follow up on my email last week about HXPP's impressive 30-year track record in specialized export packaging.

I understand you're busy running day-to-day operations, but I wanted to make sure my message didn't get lost in your inbox.

The opportunity I mentioned - connecting HXPP with growth partners who understand specialized manufacturing services - could be worth exploring when you have a moment.

Many packaging specialists have found it valuable to have a brief, no-obligation conversation about their long-term business planning, especially with the current manufacturing boom in Ontario.

Would a 15-minute call this week or next work to discuss how other technical specialists have approached their growth planning?

Best regards,
Mark Fillingham
Acquisition Advisory Services
Direct: (555) 123-4567"""
            },
            {
                "delay_days": 14,
                "subject": "Final follow-up - Export packaging growth opportunities",
                "body": """Dear HXPP Leadership,

This will be my final email regarding growth partnership opportunities for Hamilton X Packaging.

I recognize that unsolicited outreach isn't always welcome, and I want to respect your time and preferences.

However, given HXPP's unique position in the export packaging market and the significant growth happening in Ontario manufacturing, I thought it worth one last attempt to connect.

If you're ever interested in exploring how other 30-year family operations have successfully planned for their next phase of growth while preserving what they've built, I'd be happy to share those insights.

If not, I completely understand and won't reach out again.

Either way, I wish HXPP continued success in your specialized packaging work.

Best regards,
Mark Fillingham
Acquisition Advisory Services

P.S. If you'd prefer not to receive further communications, simply reply with "Remove" and I'll ensure you're taken off any future contact lists."""
            }
        ]
        
        # G.S. Dunn follow-up sequence
        gsdunn_sequence = [
            {
                "delay_days": 7,
                "subject": "Quick follow-up - G.S. Dunn specialty processing",
                "body": """Dear Luis and G.S. Dunn Team,

I wanted to follow up on my email last week about G.S. Dunn's specialized mustard processing expertise and market position.

I understand you're busy with production and daily operations, but I wanted to ensure my message didn't get overlooked.

The growth partnership opportunity I mentioned - connecting G.S. Dunn with investors who appreciate niche food processing specialists - might be worth considering when you have a moment.

Many specialty processors have found value in having a brief, no-commitment conversation about their business planning, especially with the current boom in specialty food markets.

Would a 15-minute call work to discuss how other niche processors have approached expansion while maintaining their technical expertise?

Best regards,
Mark Fillingham
Acquisition Advisory Services
Direct: (555) 123-4567"""
            },
            {
                "delay_days": 14,
                "subject": "Final follow-up - Specialty food processing opportunities",
                "body": """Dear G.S. Dunn Leadership,

This will be my final email about growth partnership opportunities for G.S. Dunn's mustard processing operation.

I understand that cold outreach may not be your preferred way to explore business opportunities, and I want to respect your communication preferences.

However, given G.S. Dunn's unique market position in specialty condiment processing and the growth in the specialty food sector, I thought it merited one final attempt to connect.

If you're ever curious about how other 30+ year specialty processors have successfully expanded their operations while preserving their core technical expertise, I'd be happy to share those insights.

If not, I completely understand and won't contact you again.

Regardless, I wish G.S. Dunn continued success in your specialized processing work.

Best regards,
Mark Fillingham
Acquisition Advisory Services

P.S. If you'd prefer to avoid any future communications, simply reply with "Remove" and I'll ensure you're removed from all contact lists."""
            }
        ]
        
        return {
            "Hamilton X Packaging": hxpp_sequence,
            "G.S. Dunn Limited": gsdunn_sequence
        }
    
    def initialize_sequences(self, prospects: List[Dict]) -> None:
        """Initialize follow-up sequences for prospects who received initial emails"""
        try:
            # Load sent email log to identify who received initial emails
            with open("data/email_sent_log.json", 'r') as file:
                sent_emails = json.load(file)
        except FileNotFoundError:
            logger.warning("No sent email log found - run email sender first")
            return
        
        # Load existing response data to exclude responders
        responders = set()
        try:
            with open("data/email_responses.json", 'r') as file:
                responses = json.load(file)
                responders = {r['business_name'] for r in responses}
        except FileNotFoundError:
            logger.info("No response data found - all prospects eligible for follow-up")
        
        # Load unsubscribed list
        unsubscribed = set()
        try:
            with open("data/unsubscribed.json", 'r') as file:
                unsubscribed = set(json.load(file))
        except FileNotFoundError:
            logger.info("No unsubscribed list found")
        
        # Create sequences for prospects who received initial emails but haven't responded
        for email_log in sent_emails:
            if email_log['status'] == 'sent':
                business_name = email_log['business_name']
                
                # Skip if already responded or unsubscribed
                if business_name in responders or business_name in unsubscribed:
                    continue
                
                # Check if sequence already exists
                existing = next((s for s in self.sequences if s.business_name == business_name), None)
                if existing:
                    continue
                
                # Create new sequence
                initial_date = datetime.fromisoformat(email_log['timestamp'])
                first_follow_up_date = initial_date + timedelta(days=7)  # First follow-up after 7 days
                
                sequence = FollowUpSequence(
                    business_name=business_name,
                    sequence_name="standard_follow_up",
                    current_step=0,
                    last_sent_date=initial_date,
                    next_send_date=first_follow_up_date
                )
                
                self.sequences.append(sequence)
                logger.info(f"Initialized follow-up sequence for {business_name}")
    
    def get_due_follow_ups(self) -> List[FollowUpSequence]:
        """Get follow-up sequences that are due to be sent"""
        now = datetime.now()
        due_sequences = []
        
        for sequence in self.sequences:
            if (not sequence.completed and 
                not sequence.responded and 
                not sequence.unsubscribed and
                sequence.next_send_date <= now):
                due_sequences.append(sequence)
        
        return due_sequences
    
    def send_follow_up_email(self, sequence: FollowUpSequence, 
                           sender_email: str, sender_password: str,
                           dry_run: bool = True) -> bool:
        """Send follow-up email for a sequence"""
        try:
            # Get template for current step
            if sequence.business_name not in self.follow_up_templates:
                logger.warning(f"No follow-up templates for {sequence.business_name}")
                return False
            
            templates = self.follow_up_templates[sequence.business_name]
            if sequence.current_step >= len(templates):
                # Sequence completed
                sequence.completed = True
                logger.info(f"Follow-up sequence completed for {sequence.business_name}")
                return True
            
            template = templates[sequence.current_step]
            
            # Get prospect email (would need to load from prospects data)
            prospect_email = self.get_prospect_email(sequence.business_name)
            if not prospect_email:
                logger.warning(f"No email found for {sequence.business_name}")
                return False
            
            if dry_run:
                logger.info(f"[DRY RUN] Would send follow-up #{sequence.current_step + 1} to {sequence.business_name}")
                logger.info(f"Subject: {template['subject']}")
                
                # Update sequence (dry run)
                sequence.current_step += 1
                sequence.last_sent_date = datetime.now()
                
                if sequence.current_step < len(templates):
                    next_template = templates[sequence.current_step]
                    sequence.next_send_date = datetime.now() + timedelta(days=next_template['delay_days'])
                else:
                    sequence.completed = True
                
                return True
            
            # Create and send email
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = prospect_email
            msg['Subject'] = template['subject']
            msg.attach(MIMEText(template['body'], 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, prospect_email, msg.as_string())
            server.quit()
            
            # Update sequence
            sequence.current_step += 1
            sequence.last_sent_date = datetime.now()
            
            # Schedule next follow-up if not completed
            if sequence.current_step < len(templates):
                next_template = templates[sequence.current_step]
                sequence.next_send_date = datetime.now() + timedelta(days=next_template['delay_days'])
            else:
                sequence.completed = True
            
            logger.info(f"Follow-up #{sequence.current_step} sent to {sequence.business_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send follow-up to {sequence.business_name}: {e}")
            return False
    
    def get_prospect_email(self, business_name: str) -> Optional[str]:
        """Get prospect email address (placeholder - would need actual implementation)"""
        # This would normally load from prospect data
        # For now, return placeholder emails
        prospect_emails = {
            "Hamilton X Packaging": "info@hxpp.ca",  # Contact form - would need actual email
            "G.S. Dunn Limited": "info@gsdunn.com"   # Would need to find actual email
        }
        
        return prospect_emails.get(business_name)
    
    def update_sequence_status(self, business_name: str, status: str) -> None:
        """Update sequence status based on responses or unsubscribes"""
        for sequence in self.sequences:
            if sequence.business_name == business_name:
                if status == 'responded':
                    sequence.responded = True
                    logger.info(f"Marked {business_name} as responded - stopping follow-ups")
                elif status == 'unsubscribed':
                    sequence.unsubscribed = True
                    logger.info(f"Marked {business_name} as unsubscribed - stopping follow-ups")
                break
    
    def run_follow_up_campaign(self, sender_email: str, sender_password: str,
                             dry_run: bool = True, delay_seconds: int = 300) -> None:
        """Run follow-up campaign for all due sequences"""
        due_sequences = self.get_due_follow_ups()
        
        if not due_sequences:
            logger.info("No follow-ups due at this time")
            return
        
        logger.info(f"Processing {len(due_sequences)} due follow-ups")
        
        for sequence in due_sequences:
            success = self.send_follow_up_email(sequence, sender_email, sender_password, dry_run)
            
            if success and not dry_run:
                logger.info(f"Waiting {delay_seconds} seconds before next email...")
                time.sleep(delay_seconds)
        
        # Save updated sequences
        self.save_sequences()
        logger.info("Follow-up campaign completed")
    
    def save_sequences(self, filename: str = "data/follow_up_sequences.json") -> None:
        """Save follow-up sequences to file"""
        try:
            sequences_data = []
            for sequence in self.sequences:
                data = {
                    'business_name': sequence.business_name,
                    'sequence_name': sequence.sequence_name,
                    'current_step': sequence.current_step,
                    'last_sent_date': sequence.last_sent_date.isoformat(),
                    'next_send_date': sequence.next_send_date.isoformat(),
                    'completed': sequence.completed,
                    'responded': sequence.responded,
                    'unsubscribed': sequence.unsubscribed
                }
                sequences_data.append(data)
            
            with open(filename, 'w') as file:
                json.dump(sequences_data, file, indent=2)
            
            logger.info(f"Follow-up sequences saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving sequences: {e}")
    
    def load_sequences(self, filename: str = "data/follow_up_sequences.json") -> None:
        """Load follow-up sequences from file"""
        try:
            with open(filename, 'r') as file:
                sequences_data = json.load(file)
            
            self.sequences = []
            for data in sequences_data:
                sequence = FollowUpSequence(
                    business_name=data['business_name'],
                    sequence_name=data['sequence_name'],
                    current_step=data['current_step'],
                    last_sent_date=datetime.fromisoformat(data['last_sent_date']),
                    next_send_date=datetime.fromisoformat(data['next_send_date']),
                    completed=data['completed'],
                    responded=data['responded'],
                    unsubscribed=data['unsubscribed']
                )
                self.sequences.append(sequence)
            
            logger.info(f"Loaded {len(self.sequences)} follow-up sequences")
            
        except FileNotFoundError:
            logger.info("No existing sequences file found - will create new")
            self.sequences = []
        except Exception as e:
            logger.error(f"Error loading sequences: {e}")
            self.sequences = []
    
    def generate_sequence_report(self) -> str:
        """Generate report on follow-up sequence status"""
        if not self.sequences:
            return "No follow-up sequences found."
        
        total = len(self.sequences)
        active = len([s for s in self.sequences if not s.completed and not s.responded and not s.unsubscribed])
        completed = len([s for s in self.sequences if s.completed])
        responded = len([s for s in self.sequences if s.responded])
        unsubscribed = len([s for s in self.sequences if s.unsubscribed])
        due_now = len(self.get_due_follow_ups())
        
        report = f"""
📧 FOLLOW-UP AUTOMATION REPORT
{'='*35}

📊 Sequence Status:
• Total Sequences: {total}
• Active Sequences: {active}
• Completed Sequences: {completed}
• Responded (Stopped): {responded}
• Unsubscribed (Stopped): {unsubscribed}
• Due Now: {due_now}

📋 Sequence Details:
"""
        
        for sequence in self.sequences:
            status = "Active"
            if sequence.completed:
                status = "Completed"
            elif sequence.responded:
                status = "Responded"
            elif sequence.unsubscribed:
                status = "Unsubscribed"
            
            report += f"• {sequence.business_name}: Step {sequence.current_step + 1} - {status}\n"
        
        return report

def main():
    """Main execution function"""
    print("🔄 Follow-up Email Automation System")
    print("=" * 40)
    
    automation = FollowUpAutomation()
    automation.load_sequences()
    
    print("\nOptions:")
    print("1. Initialize new follow-up sequences")
    print("2. Run due follow-ups")
    print("3. View sequence status report")
    print("4. Update sequence status (responded/unsubscribed)")
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == "1":
        prospects = []  # Would load from actual prospect data
        automation.initialize_sequences(prospects)
        automation.save_sequences()
        print("✅ Follow-up sequences initialized")
    
    elif choice == "2":
        sender_email = input("Enter sender email: ").strip()
        dry_run = input("Run in dry-run mode? (y/n): ").strip().lower() == 'y'
        
        if not dry_run:
            sender_password = input("Enter sender email password: ").strip()
            delay = int(input("Delay between emails (seconds, default 300): ") or "300")
        else:
            sender_password = ""
            delay = 0
        
        automation.run_follow_up_campaign(sender_email, sender_password, dry_run, delay)
    
    elif choice == "3":
        report = automation.generate_sequence_report()
        print(report)
    
    elif choice == "4":
        business_name = input("Business name: ").strip()
        status = input("Status (responded/unsubscribed): ").strip()
        automation.update_sequence_status(business_name, status)
        automation.save_sequences()
        print(f"✅ {business_name} marked as {status}")
    
    print("\n🔄 Follow-up automation completed!")

if __name__ == "__main__":
    main()