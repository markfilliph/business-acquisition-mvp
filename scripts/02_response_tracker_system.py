#!/usr/bin/env python3
"""
Email Response Tracking and Management System
Tracks email responses, manages follow-ups, and schedules meetings
"""

import json
import csv
import smtplib
import imaplib
import email
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class EmailResponse:
    business_name: str
    sender_email: str
    subject: str
    body: str
    received_date: datetime
    response_type: str  # 'interested', 'not_interested', 'request_info', 'meeting', 'unsubscribe'
    sentiment_score: int  # 1-10 (1=very negative, 10=very positive)
    next_action: str
    meeting_scheduled: bool = False
    notes: str = ""

@dataclass
class FollowUpAction:
    business_name: str
    action_type: str  # 'send_email', 'make_call', 'schedule_meeting'
    scheduled_date: datetime
    completed: bool = False
    template_name: str = ""
    notes: str = ""

class EmailTracker:
    def __init__(self, imap_server: str = "imap.gmail.com", smtp_server: str = "smtp.gmail.com"):
        self.imap_server = imap_server
        self.smtp_server = smtp_server
        self.responses: List[EmailResponse] = []
        self.follow_ups: List[FollowUpAction] = []
        self.unsubscribed: Set[str] = set()
        
    def connect_to_inbox(self, email_address: str, password: str) -> imaplib.IMAP4_SSL:
        """Connect to email inbox"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(email_address, password)
            mail.select('inbox')
            logger.info("Connected to email inbox successfully")
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to inbox: {e}")
            return None
    
    def fetch_new_responses(self, email_address: str, password: str, 
                          since_date: datetime = None) -> List[EmailResponse]:
        """Fetch new email responses since last check"""
        mail = self.connect_to_inbox(email_address, password)
        if not mail:
            return []
        
        try:
            # Search for emails since specific date
            if since_date is None:
                since_date = datetime.now() - timedelta(days=7)  # Last 7 days
            
            date_str = since_date.strftime("%d-%b-%Y")
            result, data = mail.search(None, f'(SINCE "{date_str}")')
            
            email_ids = data[0].split()
            new_responses = []
            
            for email_id in email_ids:
                result, data = mail.fetch(email_id, '(RFC822)')
                if result == 'OK':
                    msg = email.message_from_bytes(data[0][1])
                    response = self.parse_email_response(msg)
                    if response:
                        new_responses.append(response)
            
            mail.logout()
            logger.info(f"Fetched {len(new_responses)} new responses")
            return new_responses
            
        except Exception as e:
            logger.error(f"Error fetching responses: {e}")
            return []
    
    def parse_email_response(self, msg: email.message.Message) -> Optional[EmailResponse]:
        """Parse email message and extract response information"""
        try:
            sender = msg['From']
            subject = msg['Subject'] or ""
            date_str = msg['Date']
            
            # Parse date
            from email.utils import parsedate_to_datetime
            received_date = parsedate_to_datetime(date_str)
            
            # Get email body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Identify business name from our prospect list
            business_name = self.identify_business_from_email(sender)
            if not business_name:
                return None  # Not from a prospect
            
            # Analyze response
            response_type = self.classify_response(body, subject)
            sentiment_score = self.analyze_sentiment(body)
            next_action = self.determine_next_action(response_type, sentiment_score)
            
            return EmailResponse(
                business_name=business_name,
                sender_email=sender,
                subject=subject,
                body=body[:500],  # Truncate for storage
                received_date=received_date,
                response_type=response_type,
                sentiment_score=sentiment_score,
                next_action=next_action,
                meeting_scheduled=False,
                notes=""
            )
            
        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return None
    
    def identify_business_from_email(self, sender_email: str) -> Optional[str]:
        """Identify which business the email is from based on domain"""
        # Load prospect data to match domains
        prospect_domains = {
            "hxpp.ca": "Hamilton X Packaging",
            "gsdunn.com": "G.S. Dunn Limited"
        }
        
        for domain, business in prospect_domains.items():
            if domain in sender_email.lower():
                return business
        
        return None
    
    def classify_response(self, body: str, subject: str) -> str:
        """Classify the type of response using keyword analysis"""
        body_lower = body.lower()
        subject_lower = subject.lower()
        
        # Unsubscribe indicators
        unsubscribe_keywords = ['unsubscribe', 'remove', 'stop', 'opt out', 'do not contact']
        if any(keyword in body_lower or keyword in subject_lower for keyword in unsubscribe_keywords):
            return 'unsubscribe'
        
        # Not interested indicators
        not_interested_keywords = ['not interested', 'no thank', 'not for sale', 'decline', 'pass']
        if any(keyword in body_lower for keyword in not_interested_keywords):
            return 'not_interested'
        
        # Meeting/call indicators
        meeting_keywords = ['meeting', 'call', 'discuss', 'talk', 'schedule', 'available']
        if any(keyword in body_lower for keyword in meeting_keywords):
            return 'meeting'
        
        # Information request indicators
        info_keywords = ['more information', 'details', 'tell me more', 'explain', 'clarify']
        if any(keyword in body_lower for keyword in info_keywords):
            return 'request_info'
        
        # Interest indicators
        interest_keywords = ['interested', 'curious', 'would like', 'sounds good', 'yes']
        if any(keyword in body_lower for keyword in interest_keywords):
            return 'interested'
        
        return 'interested'  # Default to interested for neutral responses
    
    def analyze_sentiment(self, body: str) -> int:
        """Simple sentiment analysis (1-10 scale)"""
        body_lower = body.lower()
        
        positive_words = ['interested', 'good', 'great', 'excellent', 'yes', 'sounds', 'like', 'appreciate']
        negative_words = ['not', 'no', 'never', 'stop', 'remove', 'decline', 'unsubscribe']
        
        positive_score = sum(1 for word in positive_words if word in body_lower)
        negative_score = sum(1 for word in negative_words if word in body_lower)
        
        # Base score of 5 (neutral), adjust based on keywords
        score = 5 + (positive_score * 2) - (negative_score * 2)
        return max(1, min(10, score))  # Clamp between 1-10
    
    def determine_next_action(self, response_type: str, sentiment_score: int) -> str:
        """Determine the next action based on response analysis"""
        if response_type == 'unsubscribe':
            return 'remove_from_list'
        elif response_type == 'not_interested':
            return 'mark_closed_lost'
        elif response_type == 'meeting':
            return 'schedule_meeting'
        elif response_type == 'request_info':
            return 'send_detailed_info'
        elif response_type == 'interested' and sentiment_score >= 7:
            return 'schedule_call'
        elif response_type == 'interested' and sentiment_score >= 5:
            return 'send_follow_up'
        else:
            return 'send_nurture_email'
    
    def create_follow_up_action(self, response: EmailResponse) -> FollowUpAction:
        """Create follow-up action based on response"""
        scheduled_date = datetime.now() + timedelta(days=2)  # Default 2 days
        
        if response.next_action == 'schedule_meeting':
            scheduled_date = datetime.now() + timedelta(hours=24)  # Next day
        elif response.next_action == 'send_detailed_info':
            scheduled_date = datetime.now() + timedelta(hours=4)  # Same day
        elif response.next_action == 'schedule_call':
            scheduled_date = datetime.now() + timedelta(days=1)  # Next day
        
        return FollowUpAction(
            business_name=response.business_name,
            action_type=response.next_action,
            scheduled_date=scheduled_date,
            template_name=f"{response.response_type}_followup",
            notes=f"Response sentiment: {response.sentiment_score}/10"
        )
    
    def process_responses(self, responses: List[EmailResponse]) -> None:
        """Process new responses and create follow-up actions"""
        for response in responses:
            # Check if unsubscribe
            if response.response_type == 'unsubscribe':
                self.unsubscribed.add(response.business_name)
                logger.info(f"Added {response.business_name} to unsubscribe list")
                continue
            
            # Add to responses
            self.responses.append(response)
            
            # Create follow-up action
            follow_up = self.create_follow_up_action(response)
            self.follow_ups.append(follow_up)
            
            logger.info(f"Processed response from {response.business_name}: {response.response_type}")
    
    def get_pending_follow_ups(self, days_ahead: int = 1) -> List[FollowUpAction]:
        """Get follow-up actions due in next N days"""
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        
        pending = [
            action for action in self.follow_ups
            if not action.completed 
            and action.scheduled_date <= cutoff_date
            and action.business_name not in self.unsubscribed
        ]
        
        return sorted(pending, key=lambda x: x.scheduled_date)
    
    def mark_follow_up_completed(self, business_name: str, action_type: str) -> None:
        """Mark a follow-up action as completed"""
        for action in self.follow_ups:
            if (action.business_name == business_name and 
                action.action_type == action_type and 
                not action.completed):
                action.completed = True
                logger.info(f"Marked {action_type} for {business_name} as completed")
                break
    
    def save_data(self, responses_file: str = "data/email_responses.json", 
                  follow_ups_file: str = "data/follow_up_actions.json") -> None:
        """Save tracking data to files"""
        try:
            # Save responses
            with open(responses_file, 'w') as file:
                json.dump([asdict(r) for r in self.responses], file, indent=2, default=str)
            
            # Save follow-ups
            with open(follow_ups_file, 'w') as file:
                json.dump([asdict(f) for f in self.follow_ups], file, indent=2, default=str)
            
            # Save unsubscribed list
            with open("data/unsubscribed.json", 'w') as file:
                json.dump(list(self.unsubscribed), file, indent=2)
            
            logger.info("Tracking data saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def load_data(self, responses_file: str = "data/email_responses.json", 
                  follow_ups_file: str = "data/follow_up_actions.json") -> None:
        """Load existing tracking data"""
        try:
            # Load responses
            try:
                with open(responses_file, 'r') as file:
                    data = json.load(file)
                    self.responses = []
                    for item in data:
                        item['received_date'] = datetime.fromisoformat(item['received_date'])
                        self.responses.append(EmailResponse(**item))
            except FileNotFoundError:
                self.responses = []
            
            # Load follow-ups
            try:
                with open(follow_ups_file, 'r') as file:
                    data = json.load(file)
                    self.follow_ups = []
                    for item in data:
                        item['scheduled_date'] = datetime.fromisoformat(item['scheduled_date'])
                        self.follow_ups.append(FollowUpAction(**item))
            except FileNotFoundError:
                self.follow_ups = []
            
            # Load unsubscribed
            try:
                with open("data/unsubscribed.json", 'r') as file:
                    self.unsubscribed = set(json.load(file))
            except FileNotFoundError:
                self.unsubscribed = set()
            
            logger.info("Tracking data loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def generate_response_report(self) -> str:
        """Generate summary report of email responses"""
        total_responses = len(self.responses)
        if total_responses == 0:
            return "No responses received yet."
        
        # Count by response type
        response_counts = {}
        sentiment_total = 0
        
        for response in self.responses:
            response_counts[response.response_type] = response_counts.get(response.response_type, 0) + 1
            sentiment_total += response.sentiment_score
        
        avg_sentiment = sentiment_total / total_responses
        unsubscribe_count = len(self.unsubscribed)
        pending_follow_ups = len(self.get_pending_follow_ups(7))  # Next 7 days
        
        report = f"""
📧 EMAIL RESPONSE TRACKING REPORT
{'='*40}

📊 Response Summary:
• Total Responses: {total_responses}
• Average Sentiment: {avg_sentiment:.1f}/10
• Unsubscribed: {unsubscribe_count}
• Pending Follow-ups: {pending_follow_ups}

📋 Response Breakdown:
"""
        
        for response_type, count in response_counts.items():
            percentage = (count / total_responses) * 100
            report += f"• {response_type.replace('_', ' ').title()}: {count} ({percentage:.1f}%)\n"
        
        return report

def main():
    """Main execution function for response tracking"""
    print("📧 Email Response Tracking System")
    print("=" * 40)
    
    tracker = EmailTracker()
    tracker.load_data()
    
    print("\nOptions:")
    print("1. Check for new responses")
    print("2. View pending follow-ups")
    print("3. Generate response report")
    print("4. Mark follow-up as completed")
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == "1":
        email_address = input("Enter email address: ").strip()
        password = input("Enter email password: ").strip()
        
        # Get date since last check
        days_back = int(input("Check responses from how many days back? (default 7): ") or "7")
        since_date = datetime.now() - timedelta(days=days_back)
        
        responses = tracker.fetch_new_responses(email_address, password, since_date)
        tracker.process_responses(responses)
        tracker.save_data()
        
        print(f"\n✅ Processed {len(responses)} new responses")
        
    elif choice == "2":
        pending = tracker.get_pending_follow_ups(7)
        if pending:
            print(f"\n📅 Pending Follow-ups ({len(pending)}):")
            for action in pending:
                print(f"• {action.business_name}: {action.action_type} (due {action.scheduled_date.strftime('%Y-%m-%d')})")
        else:
            print("\n✅ No pending follow-ups")
    
    elif choice == "3":
        report = tracker.generate_response_report()
        print(report)
    
    elif choice == "4":
        business_name = input("Business name: ").strip()
        action_type = input("Action type: ").strip()
        tracker.mark_follow_up_completed(business_name, action_type)
        tracker.save_data()
        print("✅ Follow-up marked as completed")
    
    print("\n📊 Response tracking completed!")

if __name__ == "__main__":
    main()