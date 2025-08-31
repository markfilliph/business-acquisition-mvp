#!/usr/bin/env python3
"""
Business Acquisition CRM - Google Sheets Generator
Creates and manages the Google Sheets CRM structure for prospect tracking.
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path

class ProspectsTracker:
    def __init__(self, credentials_file=None):
        """Initialize the prospects tracker with Google Sheets authentication."""
        self.credentials_file = credentials_file
        self.gc = None
        self.spreadsheet = None
        
    def authenticate(self):
        """Authenticate with Google Sheets API."""
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        if self.credentials_file and os.path.exists(self.credentials_file):
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_file, scope)
        else:
            print("No credentials file found. Please set up Google Sheets API credentials.")
            print("Instructions:")
            print("1. Go to Google Cloud Console")
            print("2. Create a new project or select existing")
            print("3. Enable Google Sheets API")
            print("4. Create credentials (Service Account)")
            print("5. Download JSON file and save as 'credentials.json'")
            return False
            
        self.gc = gspread.authorize(creds)
        return True
    
    def create_crm_spreadsheet(self, name="Business Acquisition CRM"):
        """Create the main CRM spreadsheet with all required sheets."""
        if not self.gc:
            if not self.authenticate():
                return None
                
        # Create new spreadsheet
        self.spreadsheet = self.gc.create(name)
        
        # Create sheets
        self.create_prospects_sheet()
        self.create_email_templates_sheet()
        self.create_analytics_sheet()
        
        # Share with your email (replace with actual email)
        # self.spreadsheet.share('your-email@gmail.com', perm_type='user', role='writer')
        
        print(f"Created spreadsheet: {self.spreadsheet.url}")
        return self.spreadsheet.url
    
    def create_prospects_sheet(self):
        """Create the main prospects tracking sheet."""
        sheet = self.spreadsheet.sheet1
        sheet.update_title("Prospects")
        
        # Headers
        headers = [
            "Business Name", "Owner Name", "Email", "Phone", "Website",
            "Revenue Estimate", "Years in Business", "Acquisition Score",
            "Initial Email Sent", "Follow-up 1", "Follow-up 2",
            "Response Status", "Response Date", "Meeting Scheduled",
            "Notes", "Next Action", "Priority"
        ]
        
        sheet.update('A1:Q1', [headers])
        
        # Format headers
        sheet.format('A1:Q1', {
            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
        })
        
        # Add data validation for Response Status
        sheet.data_validation('L2:L1000', {
            'condition': {
                'type': 'ONE_OF_LIST',
                'values': ['No Reply', 'Cold', 'Warm', 'Hot', 'Not Interested', 'Meeting Booked']
            },
            'strict': True,
            'showCustomUi': True
        })
        
        # Add data validation for Priority
        sheet.data_validation('Q2:Q1000', {
            'condition': {
                'type': 'ONE_OF_LIST',
                'values': ['High', 'Medium', 'Low']
            },
            'strict': True,
            'showCustomUi': True
        })
        
        # Set column widths
        sheet.columns_auto_resize(0, 16)
        
    def create_email_templates_sheet(self):
        """Create email templates tracking sheet."""
        sheet = self.spreadsheet.add_worksheet(title="Email Templates", rows=100, cols=10)
        
        headers = [
            "Business Name", "Template Used", "Subject Line", "Sent Date",
            "Opened", "Replied", "Template Type", "Performance Score", "Notes"
        ]
        
        sheet.update('A1:I1', [headers])
        
        # Format headers
        sheet.format('A1:I1', {
            'backgroundColor': {'red': 0.9, 'green': 0.6, 'blue': 0.2},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
        })
        
        # Data validation for Template Type
        sheet.data_validation('G2:G1000', {
            'condition': {
                'type': 'ONE_OF_LIST',
                'values': ['Legacy Preservation', 'Growth Partnership', 'Direct Approach']
            },
            'strict': True,
            'showCustomUi': True
        })
        
    def create_analytics_sheet(self):
        """Create analytics dashboard sheet."""
        sheet = self.spreadsheet.add_worksheet(title="Analytics", rows=50, cols=10)
        
        # Key metrics section
        metrics_data = [
            ["Metric", "Value", "Target", "Status"],
            ["Total Prospects", "=COUNTA(Prospects!A:A)-1", "50", ""],
            ["Emails Sent", "=COUNTIF(Prospects!I:I,\">0\")", "40", ""],
            ["Response Rate", "=IF(B3>0,COUNTIF(Prospects!L:L,\"<>No Reply\")/B3,0)", "20%", ""],
            ["Meeting Rate", "=IF(B3>0,COUNTIF(Prospects!N:N,\"<>\")/B3,0)", "5%", ""],
            ["Open Rate", "=IF(COUNTA('Email Templates'!E:E)>1,COUNTIF('Email Templates'!E:E,TRUE)/(COUNTA('Email Templates'!E:E)-1),0)", "40%", ""],
        ]
        
        sheet.update('A1:D6', metrics_data)
        
        # Format metrics section
        sheet.format('A1:D1', {
            'backgroundColor': {'red': 0.6, 'green': 0.8, 'blue': 0.6},
            'textFormat': {'bold': True}
        })
        
        # Response status breakdown
        status_data = [
            ["", ""],
            ["Response Breakdown", ""],
            ["Status", "Count"],
            ["No Reply", "=COUNTIF(Prospects!L:L,\"No Reply\")"],
            ["Cold", "=COUNTIF(Prospects!L:L,\"Cold\")"],
            ["Warm", "=COUNTIF(Prospects!L:L,\"Warm\")"],
            ["Hot", "=COUNTIF(Prospects!L:L,\"Hot\")"],
            ["Not Interested", "=COUNTIF(Prospects!L:L,\"Not Interested\")"],
            ["Meeting Booked", "=COUNTIF(Prospects!L:L,\"Meeting Booked\")"],
        ]
        
        sheet.update('A8:B16', status_data)
        
        # Template performance
        template_data = [
            ["", ""],
            ["Template Performance", ""],
            ["Template Type", "Usage", "Response Rate"],
            ["Legacy Preservation", "=COUNTIF('Email Templates'!G:G,\"Legacy Preservation\")", ""],
            ["Growth Partnership", "=COUNTIF('Email Templates'!G:G,\"Growth Partnership\")", ""],
            ["Direct Approach", "=COUNTIF('Email Templates'!G:G,\"Direct Approach\")", ""],
        ]
        
        sheet.update('A18:C23', template_data)
        
    def add_prospect(self, business_data):
        """Add a new prospect to the tracking sheet."""
        if not self.spreadsheet:
            print("No spreadsheet connected. Create one first.")
            return False
            
        prospects_sheet = self.spreadsheet.worksheet("Prospects")
        
        # Find next empty row
        next_row = len(prospects_sheet.get_all_values()) + 1
        
        # Prepare data row
        row_data = [
            business_data.get('business_name', ''),
            business_data.get('owner_name', ''),
            business_data.get('email', ''),
            business_data.get('phone', ''),
            business_data.get('website', ''),
            business_data.get('revenue_estimate', ''),
            business_data.get('years_in_business', ''),
            business_data.get('acquisition_score', ''),
            business_data.get('initial_email_sent', ''),
            business_data.get('followup_1', ''),
            business_data.get('followup_2', ''),
            business_data.get('response_status', 'No Reply'),
            business_data.get('response_date', ''),
            business_data.get('meeting_scheduled', ''),
            business_data.get('notes', ''),
            business_data.get('next_action', ''),
            business_data.get('priority', 'Medium')
        ]
        
        prospects_sheet.update(f'A{next_row}:Q{next_row}', [row_data])
        print(f"Added prospect: {business_data.get('business_name', 'Unknown')}")
        
    def update_email_sent(self, business_name, template_type, subject_line):
        """Update when an email is sent."""
        if not self.spreadsheet:
            return False
            
        # Update prospects sheet
        prospects_sheet = self.spreadsheet.worksheet("Prospects")
        prospects_data = prospects_sheet.get_all_values()
        
        for i, row in enumerate(prospects_data[1:], 2):  # Skip header
            if row[0] == business_name:  # Business Name column
                prospects_sheet.update(f'I{i}', datetime.now().strftime('%Y-%m-%d'))
                break
        
        # Add to email templates sheet
        templates_sheet = self.spreadsheet.worksheet("Email Templates")
        next_row = len(templates_sheet.get_all_values()) + 1
        
        template_data = [
            business_name,
            template_type,
            subject_line,
            datetime.now().strftime('%Y-%m-%d'),
            False,  # Opened
            False,  # Replied
            template_type,
            "",  # Performance Score
            ""   # Notes
        ]
        
        templates_sheet.update(f'A{next_row}:I{next_row}', [template_data])
        
    def generate_sample_data(self):
        """Generate sample data for testing."""
        sample_prospects = [
            {
                'business_name': 'Hamilton Manufacturing Co.',
                'owner_name': 'John Smith',
                'email': 'john@hamiltonmfg.com',
                'phone': '(905) 555-0123',
                'website': 'hamiltonmfg.com',
                'revenue_estimate': '$1.5M',
                'years_in_business': '22',
                'acquisition_score': '85',
                'priority': 'High',
                'notes': 'Family-owned, aging owner, strong financials'
            },
            {
                'business_name': 'Steeltown Distributors',
                'owner_name': 'Mary Johnson',
                'email': 'mary@steeltowndist.ca',
                'phone': '(905) 555-0456',
                'website': 'steeltowndistributors.ca',
                'revenue_estimate': '$1.2M',
                'years_in_business': '18',
                'acquisition_score': '78',
                'priority': 'Medium',
                'notes': 'Industrial supplies, solid client base'
            }
        ]
        
        for prospect in sample_prospects:
            self.add_prospect(prospect)
            
    def connect_to_existing(self, spreadsheet_url):
        """Connect to an existing spreadsheet."""
        if not self.gc:
            if not self.authenticate():
                return False
                
        try:
            self.spreadsheet = self.gc.open_by_url(spreadsheet_url)
            print(f"Connected to existing spreadsheet: {self.spreadsheet.title}")
            return True
        except Exception as e:
            print(f"Error connecting to spreadsheet: {e}")
            return False

def main():
    """Main function to demonstrate usage."""
    print("Business Acquisition CRM - Prospects Tracker")
    print("=" * 50)
    
    tracker = ProspectsTracker()
    
    print("\nOptions:")
    print("1. Create new CRM spreadsheet")
    print("2. Connect to existing spreadsheet")
    print("3. Generate sample data")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        if tracker.authenticate():
            url = tracker.create_crm_spreadsheet()
            if url:
                print(f"\nSuccess! Spreadsheet created: {url}")
                print("Remember to share this spreadsheet with your team.")
                
                # Ask if user wants to add sample data
                add_sample = input("\nAdd sample data for testing? (y/n): ").strip().lower()
                if add_sample == 'y':
                    tracker.generate_sample_data()
                    print("Sample data added!")
        
    elif choice == "2":
        url = input("Enter spreadsheet URL: ").strip()
        if tracker.connect_to_existing(url):
            print("Connected successfully!")
            
    elif choice == "3":
        url = input("Enter spreadsheet URL: ").strip()
        if tracker.connect_to_existing(url):
            tracker.generate_sample_data()
            print("Sample data added!")
    
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()