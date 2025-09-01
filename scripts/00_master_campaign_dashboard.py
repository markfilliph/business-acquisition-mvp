#!/usr/bin/env python3
"""
Campaign Dashboard - Master Control System
Centralized dashboard for managing the entire business acquisition campaign
"""

import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging
from dataclasses import asdict

# Import our modules - updated file names
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the renamed modules
try:
    from scripts.01_email_sender_system import EmailSender
except ImportError:
    # Fallback for when running directly
    exec(open('01_email_sender_system.py').read())
    
try:
    from scripts.02_response_tracker_system import EmailTracker
except ImportError:
    exec(open('02_response_tracker_system.py').read())
    
try:  
    from scripts.03_followup_automation_system import FollowUpAutomation
except ImportError:
    exec(open('03_followup_automation_system.py').read())
    
try:
    from scripts.04_meeting_pipeline_system import MeetingManager
except ImportError:
    exec(open('04_meeting_pipeline_system.py').read())

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CampaignDashboard:
    def __init__(self):
        self.email_sender = EmailSender()
        self.email_tracker = EmailTracker()
        self.follow_up_automation = FollowUpAutomation()
        self.meeting_manager = MeetingManager()
        
        # Load all data
        self.load_all_data()
    
    def load_all_data(self):
        """Load data from all systems"""
        try:
            # Load prospects from strict filtered verified database
            self.email_sender.load_prospects("data/strict_filtered_verified_prospects.csv")
            self.email_sender.load_email_templates()
            
            # Load tracking data
            self.email_tracker.load_data()
            self.follow_up_automation.load_sequences()
            self.meeting_manager.load_data()
            
            logger.info("All campaign data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading campaign data: {e}")
    
    def generate_campaign_overview(self) -> str:
        """Generate comprehensive campaign overview"""
        
        # Email campaign stats
        try:
            with open("data/email_sent_log.json", 'r') as file:
                sent_emails = json.load(file)
            total_sent = len([e for e in sent_emails if e['status'] == 'sent'])
            failed_sends = len([e for e in sent_emails if e['status'] == 'failed'])
        except FileNotFoundError:
            total_sent = 0
            failed_sends = 0
        
        # Response stats
        total_responses = len(self.email_tracker.responses)
        unsubscribed = len(self.email_tracker.unsubscribed)
        
        # Follow-up stats
        active_sequences = len([s for s in self.follow_up_automation.sequences 
                              if not s.completed and not s.responded and not s.unsubscribed])
        completed_sequences = len([s for s in self.follow_up_automation.sequences if s.completed])
        
        # Meeting stats
        scheduled_meetings = len([m for m in self.meeting_manager.meetings if m.status == 'scheduled'])
        completed_meetings = len([m for m in self.meeting_manager.meetings if m.status == 'completed'])
        
        # Pipeline stats
        pipeline_summary = self.meeting_manager.get_pipeline_summary()
        
        # Calculate response rate
        response_rate = (total_responses / total_sent * 100) if total_sent > 0 else 0
        
        # Calculate conversion metrics
        meeting_conversion = (scheduled_meetings / total_responses * 100) if total_responses > 0 else 0
        
        overview = f"""
🎯 BUSINESS ACQUISITION CAMPAIGN DASHBOARD
{'='*50}

📊 CAMPAIGN OVERVIEW
┌─────────────────────────────────────────────┐
│ Target Prospects: {len(self.email_sender.prospects):>2}                        │
│ Emails Sent: {total_sent:>6}                        │
│ Send Failures: {failed_sends:>4}                        │
│ Response Rate: {response_rate:>6.1f}%                     │
│ Unsubscribed: {unsubscribed:>5}                        │
└─────────────────────────────────────────────┘

📧 EMAIL CAMPAIGN STATUS
• Initial emails sent: {total_sent}
• Responses received: {total_responses}
• Active follow-up sequences: {active_sequences}
• Completed sequences: {completed_sequences}

🤝 MEETING & PIPELINE STATUS  
• Meetings scheduled: {scheduled_meetings}
• Meetings completed: {completed_meetings}
• Meeting conversion rate: {meeting_conversion:.1f}%
• Total pipeline deals: {pipeline_summary['total_deals']}
• Weighted pipeline value: ${pipeline_summary['total_value']:,.0f}

📈 PIPELINE BY STAGE"""
        
        if pipeline_summary['stages']:
            for stage, data in pipeline_summary['stages'].items():
                overview += f"\n• {stage.replace('_', ' ').title()}: {data['count']} deals (${data['value']:,.0f})"
        else:
            overview += "\n• No pipeline data yet"
        
        # Recent activity
        overview += f"\n\n🔔 RECENT ACTIVITY (Last 7 days)"
        
        # Recent responses
        recent_responses = [r for r in self.email_tracker.responses 
                          if r.received_date >= datetime.now() - timedelta(days=7)]
        if recent_responses:
            overview += f"\n📨 Recent responses: {len(recent_responses)}"
            for response in recent_responses[-3:]:  # Show last 3
                overview += f"\n  • {response.business_name}: {response.response_type}"
        
        # Upcoming meetings
        upcoming_meetings = self.meeting_manager.get_upcoming_meetings(7)
        if upcoming_meetings:
            overview += f"\n📅 Upcoming meetings: {len(upcoming_meetings)}"
            for meeting in upcoming_meetings:
                overview += f"\n  • {meeting.business_name}: {meeting.scheduled_date.strftime('%m/%d %H:%M')}"
        
        # Due follow-ups
        due_follow_ups = self.follow_up_automation.get_due_follow_ups()
        if due_follow_ups:
            overview += f"\n🔄 Follow-ups due: {len(due_follow_ups)}"
            for follow_up in due_follow_ups:
                overview += f"\n  • {follow_up.business_name}: {follow_up.next_send_date.strftime('%m/%d')}"
        
        return overview
    
    def get_prospect_details(self) -> List[Dict]:
        """Get detailed information about each prospect"""
        prospect_details = []
        
        for prospect in self.email_sender.prospects:
            # Find sent emails
            sent_status = "Not sent"
            try:
                with open("data/email_sent_log.json", 'r') as file:
                    sent_emails = json.load(file)
                
                prospect_emails = [e for e in sent_emails if e['business_name'] == prospect.business_name]
                if prospect_emails:
                    latest_email = max(prospect_emails, key=lambda x: x['timestamp'])
                    sent_status = f"{latest_email['status'].title()} ({latest_email['approach']})"
            except FileNotFoundError:
                pass
            
            # Find responses
            responses = [r for r in self.email_tracker.responses if r.business_name == prospect.business_name]
            response_status = "No response"
            if responses:
                latest_response = max(responses, key=lambda x: x.received_date)
                response_status = f"{latest_response.response_type} (Sentiment: {latest_response.sentiment_score}/10)"
            
            # Find meetings
            meetings = [m for m in self.meeting_manager.meetings if m.business_name == prospect.business_name]
            meeting_status = "No meetings"
            if meetings:
                upcoming = [m for m in meetings if m.status == 'scheduled']
                completed = [m for m in meetings if m.status == 'completed']
                if upcoming:
                    meeting_status = f"{len(upcoming)} scheduled"
                elif completed:
                    meeting_status = f"{len(completed)} completed"
            
            # Find pipeline status
            pipeline_entry = next((p for p in self.meeting_manager.pipeline if p.business_name == prospect.business_name), None)
            pipeline_status = "Not in pipeline"
            if pipeline_entry:
                pipeline_status = f"{pipeline_entry.current_stage} ({pipeline_entry.probability}%)"
            
            prospect_details.append({
                'business_name': prospect.business_name,
                'industry': prospect.industry,
                'revenue': prospect.revenue,
                'score': prospect.score,
                'email_status': sent_status,
                'response_status': response_status,
                'meeting_status': meeting_status,
                'pipeline_status': pipeline_status
            })
        
        return sorted(prospect_details, key=lambda x: x['score'], reverse=True)
    
    def identify_next_actions(self) -> List[str]:
        """Identify recommended next actions"""
        actions = []
        
        # Check for due follow-ups
        due_follow_ups = self.follow_up_automation.get_due_follow_ups()
        if due_follow_ups:
            actions.append(f"🔄 Send {len(due_follow_ups)} due follow-up emails")
        
        # Check for unprocessed responses
        # This would require checking email inbox, simplified here
        actions.append("📧 Check email for new responses")
        
        # Check for upcoming meetings
        upcoming_meetings = self.meeting_manager.get_upcoming_meetings(3)  # Next 3 days
        if upcoming_meetings:
            actions.append(f"📅 Prepare for {len(upcoming_meetings)} upcoming meetings")
        
        # Check for prospects without initial emails
        try:
            with open("data/email_sent_log.json", 'r') as file:
                sent_emails = json.load(file)
            
            sent_to = {e['business_name'] for e in sent_emails if e['status'] == 'sent'}
            not_contacted = [p for p in self.email_sender.prospects if p.business_name not in sent_to]
            
            if not_contacted:
                actions.append(f"📨 Send initial emails to {len(not_contacted)} prospects")
        
        except FileNotFoundError:
            actions.append(f"📨 Send initial emails to {len(self.email_sender.prospects)} prospects")
        
        # Check pipeline progression
        stalled_deals = []
        for deal in self.meeting_manager.pipeline:
            days_since_activity = (datetime.now() - deal.last_activity).days
            if days_since_activity > 7 and deal.current_stage not in ['closed_won', 'closed_lost']:
                stalled_deals.append(deal)
        
        if stalled_deals:
            actions.append(f"⚡ Follow up on {len(stalled_deals)} stalled pipeline deals")
        
        return actions
    
    def export_campaign_data(self, filename: str = None) -> str:
        """Export comprehensive campaign data to CSV"""
        if filename is None:
            filename = f"data/campaign_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        prospect_details = self.get_prospect_details()
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            if prospect_details:
                writer = csv.DictWriter(file, fieldnames=prospect_details[0].keys())
                writer.writeheader()
                writer.writerows(prospect_details)
        
        logger.info(f"Campaign data exported to {filename}")
        return filename
    
    def run_daily_tasks(self, sender_email: str = None, sender_password: str = None, dry_run: bool = True):
        """Run automated daily campaign tasks"""
        print("🚀 Running Daily Campaign Tasks")
        print("=" * 35)
        
        # 1. Check for due follow-ups
        due_follow_ups = self.follow_up_automation.get_due_follow_ups()
        if due_follow_ups:
            print(f"\n🔄 Processing {len(due_follow_ups)} due follow-ups...")
            if sender_email and sender_password:
                self.follow_up_automation.run_follow_up_campaign(sender_email, sender_password, dry_run)
            else:
                print("⚠️  Email credentials needed to send follow-ups")
        
        # 2. Check for responses (would need email credentials)
        if sender_email and sender_password:
            print("\n📧 Checking for new responses...")
            try:
                responses = self.email_tracker.fetch_new_responses(sender_email, sender_password, 
                                                                 datetime.now() - timedelta(days=1))
                if responses:
                    self.email_tracker.process_responses(responses)
                    self.email_tracker.save_data()
                    print(f"✅ Processed {len(responses)} new responses")
                else:
                    print("✅ No new responses")
            except Exception as e:
                print(f"⚠️  Error checking responses: {e}")
        
        # 3. Update follow-up sequences based on responses
        for response in self.email_tracker.responses:
            if response.response_type in ['interested', 'meeting']:
                self.follow_up_automation.update_sequence_status(response.business_name, 'responded')
            elif response.response_type == 'unsubscribe':
                self.follow_up_automation.update_sequence_status(response.business_name, 'unsubscribed')
        
        # 4. Generate summary
        print("\n📊 Daily Summary:")
        overview = self.generate_campaign_overview()
        print(overview)
        
        print("\n✅ Daily tasks completed!")

def main():
    """Main dashboard interface"""
    print("🎯 BUSINESS ACQUISITION CAMPAIGN DASHBOARD")
    print("=" * 50)
    
    dashboard = CampaignDashboard()
    
    while True:
        print("\n🎛️  DASHBOARD OPTIONS:")
        print("1. View campaign overview")
        print("2. View prospect details")  
        print("3. View next actions")
        print("4. Run daily tasks")
        print("5. Export campaign data")
        print("6. Quick stats")
        print("0. Exit")
        
        choice = input("\nSelect option (0-6): ").strip()
        
        if choice == "0":
            break
        
        elif choice == "1":
            overview = dashboard.generate_campaign_overview()
            print(overview)
        
        elif choice == "2":
            details = dashboard.get_prospect_details()
            print(f"\n📋 PROSPECT DETAILS ({len(details)} prospects)")
            print("-" * 70)
            
            for prospect in details:
                print(f"\n🏢 {prospect['business_name']} (Score: {prospect['score']})")
                print(f"   Industry: {prospect['industry']} | Revenue: {prospect['revenue']}")
                print(f"   Email: {prospect['email_status']}")
                print(f"   Response: {prospect['response_status']}")
                print(f"   Meetings: {prospect['meeting_status']}")
                print(f"   Pipeline: {prospect['pipeline_status']}")
        
        elif choice == "3":
            actions = dashboard.identify_next_actions()
            print(f"\n✨ RECOMMENDED NEXT ACTIONS ({len(actions)})")
            print("-" * 40)
            for i, action in enumerate(actions, 1):
                print(f"{i}. {action}")
        
        elif choice == "4":
            print("\n🤖 Daily Task Automation")
            sender_email = input("Enter email (or press Enter to skip email tasks): ").strip()
            
            if sender_email:
                dry_run = input("Run in dry-run mode? (y/n): ").strip().lower() == 'y'
                if not dry_run:
                    sender_password = input("Enter email password: ").strip()
                else:
                    sender_password = sender_email  # Placeholder for dry run
                
                dashboard.run_daily_tasks(sender_email, sender_password, dry_run)
            else:
                dashboard.run_daily_tasks()
        
        elif choice == "5":
            filename = dashboard.export_campaign_data()
            print(f"✅ Campaign data exported to {filename}")
        
        elif choice == "6":
            # Quick stats
            print(f"\n⚡ QUICK STATS")
            print(f"• Prospects: {len(dashboard.email_sender.prospects)}")
            print(f"• Responses: {len(dashboard.email_tracker.responses)}")
            print(f"• Meetings: {len(dashboard.meeting_manager.meetings)}")
            print(f"• Pipeline deals: {len(dashboard.meeting_manager.pipeline)}")
            
            pipeline_value = sum(deal.estimated_value * (deal.probability / 100) 
                               for deal in dashboard.meeting_manager.pipeline)
            print(f"• Weighted pipeline: ${pipeline_value:,.0f}")
        
        else:
            print("❌ Invalid option. Please try again.")
    
    print("\n👋 Dashboard session ended. Good luck with your campaign!")

if __name__ == "__main__":
    main()