#!/usr/bin/env python3
"""
Meeting Management and Response Analysis System
Analyzes responses, schedules meetings, and manages the acquisition pipeline
"""

import json
import csv
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Meeting:
    business_name: str
    contact_name: str
    contact_email: str
    meeting_type: str  # 'discovery', 'valuation', 'negotiation', 'closing'
    scheduled_date: datetime
    meeting_platform: str  # 'zoom', 'teams', 'phone', 'in_person'
    status: str  # 'scheduled', 'completed', 'cancelled', 'no_show'
    notes: str = ""
    next_steps: str = ""
    deal_stage: str = "discovery"  # 'discovery', 'qualification', 'proposal', 'negotiation', 'closing'
    estimated_value: int = 0

@dataclass
class DealPipeline:
    business_name: str
    current_stage: str  # 'lead', 'qualified', 'proposal', 'negotiation', 'closing', 'closed_won', 'closed_lost'
    probability: int  # 1-100%
    estimated_value: int
    last_activity: datetime
    next_action: str
    owner_motivation: str = ""  # 'succession', 'retirement', 'growth', 'financial'
    key_concerns: List[str] = None
    competitive_advantages: List[str] = None

class MeetingManager:
    def __init__(self, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.meetings: List[Meeting] = []
        self.pipeline: List[DealPipeline] = []
        self.meeting_templates = self.load_meeting_templates()
        
    def load_meeting_templates(self) -> Dict[str, Dict[str, str]]:
        """Load email templates for meeting scheduling"""
        return {
            "discovery_meeting": {
                "subject": "Brief discovery call - {business_name}",
                "body": """Dear {contact_name},

Thank you for your response regarding {business_name}. I appreciate your interest in exploring potential opportunities.

I'd like to schedule a brief 30-minute discovery call to:
• Better understand your business goals and timeline
• Learn about your current operations and any challenges
• Discuss how similar businesses have approached their growth planning
• Determine if there's a mutual fit worth exploring further

This is purely an informational conversation with no commitments from either side. Many business owners find it valuable to understand their options, even if they're not actively looking to make changes.

Would any of these times work for a call this week or next?
• {time_option_1}
• {time_option_2}
• {time_option_3}

If none of these work, please let me know what would be better for your schedule.

The call can be via phone, Zoom, or Teams - whatever is most convenient for you.

Best regards,
Mark Fillingham
Acquisition Advisory Services
Direct: (555) 123-4567
Email: mark@acquisitionadvisory.com"""
            },
            "valuation_meeting": {
                "subject": "Business valuation discussion - {business_name}",
                "body": """Dear {contact_name},

Following our initial conversation about {business_name}, I'd like to schedule a more detailed discussion about business valuation and potential transaction structures.

This 45-minute meeting would cover:
• Professional business valuation methodology
• Market multiples for similar businesses in your industry
• Various transaction structures (full sale, partial sale, growth partnership)
• Timeline considerations and process overview
• Next steps if you decide to move forward

I'll prepare a preliminary market analysis specific to {business_name} to share during our call.

Would any of these times work for a call this week?
• {time_option_1}
• {time_option_2}
• {time_option_3}

Please let me know if you'd prefer a different time or if you have any questions beforehand.

Best regards,
Mark Fillingham
Acquisition Advisory Services"""
            },
            "meeting_confirmation": {
                "subject": "Confirmed: Meeting with {business_name} - {meeting_date}",
                "body": """Dear {contact_name},

This confirms our meeting scheduled for:

📅 Date: {meeting_date}
🕐 Time: {meeting_time}
💻 Platform: {meeting_platform}
📞 Dial-in: {meeting_details}

Meeting Agenda ({meeting_duration} minutes):
{meeting_agenda}

Materials I'll share:
• Industry valuation benchmarks
• Transaction structure options
• Timeline and process overview

Please let me know if you need to reschedule or have any questions beforehand.

Looking forward to our conversation.

Best regards,
Mark Fillingham
Acquisition Advisory Services
Direct: (555) 123-4567"""
            }
        }
    
    def analyze_response_for_meeting(self, response_text: str, business_name: str) -> Dict[str, any]:
        """Analyze response to determine meeting readiness and type"""
        response_lower = response_text.lower()
        
        # Determine interest level
        high_interest_keywords = ['meeting', 'call', 'discuss', 'interested', 'tell me more', 'learn more']
        medium_interest_keywords = ['curious', 'information', 'details', 'explain', 'understand']
        meeting_keywords = ['schedule', 'available', 'time', 'when', 'calendar']
        
        interest_level = 0
        for keyword in high_interest_keywords:
            if keyword in response_lower:
                interest_level = max(interest_level, 8)
        
        for keyword in medium_interest_keywords:
            if keyword in response_lower:
                interest_level = max(interest_level, 6)
        
        for keyword in meeting_keywords:
            if keyword in response_lower:
                interest_level = max(interest_level, 9)
        
        # Determine meeting type based on response content
        if any(word in response_lower for word in ['valuation', 'worth', 'value', 'price']):
            meeting_type = 'valuation'
        elif any(word in response_lower for word in ['process', 'how it works', 'next steps']):
            meeting_type = 'discovery'
        else:
            meeting_type = 'discovery'  # Default
        
        # Identify potential concerns
        concerns = []
        if 'confidential' in response_lower:
            concerns.append('confidentiality')
        if 'employee' in response_lower:
            concerns.append('employee_retention')
        if 'customer' in response_lower:
            concerns.append('customer_relationships')
        if 'family' in response_lower or 'legacy' in response_lower:
            concerns.append('legacy_preservation')
        
        # Identify motivation indicators
        motivation = ""
        if any(word in response_lower for word in ['retire', 'retirement']):
            motivation = 'retirement'
        elif any(word in response_lower for word in ['succession', 'next generation']):
            motivation = 'succession'
        elif any(word in response_lower for word in ['grow', 'expansion', 'scale']):
            motivation = 'growth'
        elif any(word in response_lower for word in ['capital', 'investment', 'financial']):
            motivation = 'financial'
        
        return {
            'interest_level': interest_level,
            'meeting_type': meeting_type,
            'concerns': concerns,
            'motivation': motivation,
            'meeting_ready': interest_level >= 7
        }
    
    def create_meeting_proposal_email(self, business_name: str, contact_name: str,
                                    meeting_type: str = 'discovery') -> str:
        """Create meeting proposal email"""
        template = self.meeting_templates.get(f"{meeting_type}_meeting")
        if not template:
            template = self.meeting_templates["discovery_meeting"]
        
        # Generate time options (business hours, next week)
        base_date = datetime.now() + timedelta(days=2)
        time_options = []
        
        for i in range(3):
            option_date = base_date + timedelta(days=i * 2)
            # Ensure business days (Monday-Friday)
            while option_date.weekday() >= 5:
                option_date += timedelta(days=1)
            
            time_str = option_date.strftime("%A, %B %d at 2:00 PM EST")
            time_options.append(time_str)
        
        # Format email
        email_body = template["body"].format(
            contact_name=contact_name,
            business_name=business_name,
            time_option_1=time_options[0],
            time_option_2=time_options[1],
            time_option_3=time_options[2]
        )
        
        email_subject = template["subject"].format(business_name=business_name)
        
        return email_subject, email_body
    
    def schedule_meeting(self, business_name: str, contact_name: str, contact_email: str,
                        meeting_datetime: datetime, meeting_type: str = 'discovery',
                        platform: str = 'zoom') -> Meeting:
        """Schedule a new meeting"""
        meeting = Meeting(
            business_name=business_name,
            contact_name=contact_name,
            contact_email=contact_email,
            meeting_type=meeting_type,
            scheduled_date=meeting_datetime,
            meeting_platform=platform,
            status='scheduled',
            deal_stage='discovery'
        )
        
        self.meetings.append(meeting)
        logger.info(f"Scheduled {meeting_type} meeting with {business_name} for {meeting_datetime}")
        
        # Update or create pipeline entry
        self.update_pipeline(business_name, 'qualified', probability=30, 
                           next_action=f"Complete {meeting_type} meeting",
                           last_activity=datetime.now())
        
        return meeting
    
    def send_meeting_confirmation(self, meeting: Meeting, sender_email: str,
                                sender_password: str, dry_run: bool = True) -> bool:
        """Send meeting confirmation email"""
        try:
            template = self.meeting_templates["meeting_confirmation"]
            
            # Format meeting details
            meeting_agenda = {
                'discovery': '• Business overview and goals\n• Current challenges and opportunities\n• Potential transaction structures\n• Next steps discussion',
                'valuation': '• Detailed business valuation\n• Market comparisons\n• Transaction options\n• Process and timeline',
                'negotiation': '• Terms discussion\n• Structure finalization\n• Timeline confirmation\n• Documentation review'
            }.get(meeting.meeting_type, '• Discussion agenda')
            
            meeting_details = "Zoom link will be provided 24 hours before meeting"
            if meeting.meeting_platform == 'phone':
                meeting_details = "Phone number will be provided before call"
            
            email_body = template["body"].format(
                contact_name=meeting.contact_name,
                business_name=meeting.business_name,
                meeting_date=meeting.scheduled_date.strftime("%A, %B %d, %Y"),
                meeting_time=meeting.scheduled_date.strftime("%I:%M %p EST"),
                meeting_platform=meeting.meeting_platform.title(),
                meeting_details=meeting_details,
                meeting_duration={"discovery": "30", "valuation": "45", "negotiation": "60"}.get(meeting.meeting_type, "30"),
                meeting_agenda=meeting_agenda
            )
            
            email_subject = template["subject"].format(
                business_name=meeting.business_name,
                meeting_date=meeting.scheduled_date.strftime("%B %d")
            )
            
            if dry_run:
                logger.info(f"[DRY RUN] Would send meeting confirmation to {meeting.business_name}")
                logger.info(f"Subject: {email_subject}")
                return True
            
            # Send email
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = meeting.contact_email
            msg['Subject'] = email_subject
            msg.attach(MIMEText(email_body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, meeting.contact_email, msg.as_string())
            server.quit()
            
            logger.info(f"Meeting confirmation sent to {meeting.business_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send meeting confirmation: {e}")
            return False
    
    def update_pipeline(self, business_name: str, stage: str, probability: int = None,
                       estimated_value: int = None, next_action: str = None,
                       last_activity: datetime = None, **kwargs) -> None:
        """Update deal pipeline entry"""
        # Find existing pipeline entry
        pipeline_entry = next((p for p in self.pipeline if p.business_name == business_name), None)
        
        if pipeline_entry:
            # Update existing
            pipeline_entry.current_stage = stage
            if probability is not None:
                pipeline_entry.probability = probability
            if estimated_value is not None:
                pipeline_entry.estimated_value = estimated_value
            if next_action:
                pipeline_entry.next_action = next_action
            if last_activity:
                pipeline_entry.last_activity = last_activity
            
            # Update additional fields
            for key, value in kwargs.items():
                if hasattr(pipeline_entry, key):
                    setattr(pipeline_entry, key, value)
        
        else:
            # Create new pipeline entry
            if last_activity is None:
                last_activity = datetime.now()
            
            pipeline_entry = DealPipeline(
                business_name=business_name,
                current_stage=stage,
                probability=probability or 10,
                estimated_value=estimated_value or 1200000,  # Default $1.2M based on target criteria
                last_activity=last_activity,
                next_action=next_action or "Schedule initial meeting",
                key_concerns=kwargs.get('key_concerns', []),
                competitive_advantages=kwargs.get('competitive_advantages', []),
                owner_motivation=kwargs.get('owner_motivation', ''),
            )
            
            self.pipeline.append(pipeline_entry)
        
        logger.info(f"Pipeline updated: {business_name} -> {stage} ({probability}%)")
    
    def complete_meeting(self, business_name: str, outcome: str, notes: str,
                        next_steps: str, estimated_value: int = None) -> None:
        """Mark meeting as completed and update pipeline"""
        # Find meeting
        meeting = next((m for m in self.meetings 
                       if m.business_name == business_name and m.status == 'scheduled'), None)
        
        if meeting:
            meeting.status = 'completed'
            meeting.notes = notes
            meeting.next_steps = next_steps
            if estimated_value:
                meeting.estimated_value = estimated_value
        
        # Update pipeline based on outcome
        stage_mapping = {
            'very_interested': ('proposal', 70),
            'interested': ('qualification', 50),
            'maybe': ('qualified', 30),
            'not_interested': ('closed_lost', 0),
            'need_more_info': ('qualified', 40)
        }
        
        if outcome in stage_mapping:
            stage, probability = stage_mapping[outcome]
            self.update_pipeline(
                business_name, stage, probability=probability,
                estimated_value=estimated_value,
                next_action=next_steps,
                last_activity=datetime.now()
            )
        
        logger.info(f"Meeting completed for {business_name}: {outcome}")
    
    def get_upcoming_meetings(self, days_ahead: int = 7) -> List[Meeting]:
        """Get meetings scheduled in the next N days"""
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        
        upcoming = [
            meeting for meeting in self.meetings
            if meeting.status == 'scheduled' and meeting.scheduled_date <= cutoff_date
        ]
        
        return sorted(upcoming, key=lambda x: x.scheduled_date)
    
    def get_pipeline_summary(self) -> Dict[str, any]:
        """Generate pipeline summary statistics"""
        if not self.pipeline:
            return {"total_deals": 0, "total_value": 0, "stages": {}}
        
        total_deals = len(self.pipeline)
        total_value = sum(deal.estimated_value * (deal.probability / 100) for deal in self.pipeline)
        
        # Count by stage
        stages = {}
        for deal in self.pipeline:
            stage = deal.current_stage
            if stage not in stages:
                stages[stage] = {'count': 0, 'value': 0, 'probability': 0}
            
            stages[stage]['count'] += 1
            stages[stage]['value'] += deal.estimated_value
            stages[stage]['probability'] += deal.probability
        
        # Calculate average probability per stage
        for stage_data in stages.values():
            if stage_data['count'] > 0:
                stage_data['avg_probability'] = stage_data['probability'] / stage_data['count']
        
        return {
            'total_deals': total_deals,
            'total_value': total_value,
            'stages': stages
        }
    
    def save_data(self, meetings_file: str = "data/meetings.json",
                  pipeline_file: str = "data/deal_pipeline.json") -> None:
        """Save meeting and pipeline data"""
        try:
            # Save meetings
            with open(meetings_file, 'w') as file:
                json.dump([asdict(m) for m in self.meetings], file, indent=2, default=str)
            
            # Save pipeline
            with open(pipeline_file, 'w') as file:
                json.dump([asdict(p) for p in self.pipeline], file, indent=2, default=str)
            
            logger.info("Meeting and pipeline data saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def load_data(self, meetings_file: str = "data/meetings.json",
                  pipeline_file: str = "data/deal_pipeline.json") -> None:
        """Load meeting and pipeline data"""
        try:
            # Load meetings
            try:
                with open(meetings_file, 'r') as file:
                    data = json.load(file)
                    self.meetings = []
                    for item in data:
                        item['scheduled_date'] = datetime.fromisoformat(item['scheduled_date'])
                        self.meetings.append(Meeting(**item))
            except FileNotFoundError:
                self.meetings = []
            
            # Load pipeline
            try:
                with open(pipeline_file, 'r') as file:
                    data = json.load(file)
                    self.pipeline = []
                    for item in data:
                        item['last_activity'] = datetime.fromisoformat(item['last_activity'])
                        if item.get('key_concerns') is None:
                            item['key_concerns'] = []
                        if item.get('competitive_advantages') is None:
                            item['competitive_advantages'] = []
                        self.pipeline.append(DealPipeline(**item))
            except FileNotFoundError:
                self.pipeline = []
            
            logger.info("Meeting and pipeline data loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")

def main():
    """Main execution function"""
    print("🤝 Meeting Management & Pipeline System")
    print("=" * 40)
    
    manager = MeetingManager()
    manager.load_data()
    
    print("\nOptions:")
    print("1. Analyze response for meeting readiness")
    print("2. Schedule new meeting")
    print("3. View upcoming meetings")
    print("4. Complete meeting and update pipeline")
    print("5. View pipeline summary")
    print("6. Send meeting confirmation")
    
    choice = input("Select option (1-6): ").strip()
    
    if choice == "1":
        response_text = input("Enter response text: ").strip()
        business_name = input("Business name: ").strip()
        
        analysis = manager.analyze_response_for_meeting(response_text, business_name)
        
        print(f"\n📊 Response Analysis:")
        print(f"• Interest Level: {analysis['interest_level']}/10")
        print(f"• Meeting Ready: {'Yes' if analysis['meeting_ready'] else 'No'}")
        print(f"• Suggested Meeting Type: {analysis['meeting_type']}")
        print(f"• Motivation: {analysis['motivation'] or 'Unknown'}")
        print(f"• Concerns: {', '.join(analysis['concerns']) or 'None identified'}")
        
        if analysis['meeting_ready']:
            create_proposal = input("\nGenerate meeting proposal email? (y/n): ").strip().lower() == 'y'
            if create_proposal:
                contact_name = input("Contact name: ").strip()
                subject, body = manager.create_meeting_proposal_email(
                    business_name, contact_name, analysis['meeting_type']
                )
                print(f"\n📧 Email Proposal:")
                print(f"Subject: {subject}")
                print(f"\n{body}")
    
    elif choice == "2":
        business_name = input("Business name: ").strip()
        contact_name = input("Contact name: ").strip()
        contact_email = input("Contact email: ").strip()
        
        print("\nMeeting types: discovery, valuation, negotiation")
        meeting_type = input("Meeting type (default: discovery): ").strip() or "discovery"
        
        # Get meeting date
        date_str = input("Meeting date (YYYY-MM-DD HH:MM): ").strip()
        meeting_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        
        platform = input("Platform (zoom/teams/phone/in_person): ").strip() or "zoom"
        
        meeting = manager.schedule_meeting(
            business_name, contact_name, contact_email,
            meeting_date, meeting_type, platform
        )
        
        manager.save_data()
        print(f"✅ Meeting scheduled: {meeting.business_name} on {meeting.scheduled_date}")
    
    elif choice == "3":
        upcoming = manager.get_upcoming_meetings(14)  # Next 2 weeks
        
        if upcoming:
            print(f"\n📅 Upcoming Meetings ({len(upcoming)}):")
            for meeting in upcoming:
                print(f"• {meeting.business_name}: {meeting.meeting_type} on {meeting.scheduled_date.strftime('%Y-%m-%d %H:%M')} ({meeting.meeting_platform})")
        else:
            print("\n✅ No upcoming meetings")
    
    elif choice == "4":
        business_name = input("Business name: ").strip()
        
        print("\nOutcome options: very_interested, interested, maybe, not_interested, need_more_info")
        outcome = input("Meeting outcome: ").strip()
        notes = input("Meeting notes: ").strip()
        next_steps = input("Next steps: ").strip()
        
        estimated_value_str = input("Estimated deal value (optional): ").strip()
        estimated_value = int(estimated_value_str) if estimated_value_str else None
        
        manager.complete_meeting(business_name, outcome, notes, next_steps, estimated_value)
        manager.save_data()
        
        print(f"✅ Meeting completed and pipeline updated for {business_name}")
    
    elif choice == "5":
        summary = manager.get_pipeline_summary()
        
        print(f"\n📈 DEAL PIPELINE SUMMARY")
        print(f"{'='*30}")
        print(f"• Total Deals: {summary['total_deals']}")
        print(f"• Weighted Value: ${summary['total_value']:,.0f}")
        
        if summary['stages']:
            print(f"\n📊 By Stage:")
            for stage, data in summary['stages'].items():
                print(f"• {stage.replace('_', ' ').title()}: {data['count']} deals, ${data['value']:,.0f} value, {data.get('avg_probability', 0):.0f}% avg probability")
    
    elif choice == "6":
        business_name = input("Business name: ").strip()
        meeting = next((m for m in manager.meetings if m.business_name == business_name and m.status == 'scheduled'), None)
        
        if meeting:
            sender_email = input("Sender email: ").strip()
            dry_run = input("Send in dry-run mode? (y/n): ").strip().lower() == 'y'
            
            if not dry_run:
                sender_password = input("Sender password: ").strip()
            else:
                sender_password = ""
            
            success = manager.send_meeting_confirmation(meeting, sender_email, sender_password, dry_run)
            if success:
                print("✅ Meeting confirmation sent")
        else:
            print("❌ No scheduled meeting found for that business")
    
    print("\n🤝 Meeting management completed!")

if __name__ == "__main__":
    main()