# Business Acquisition MVP

AI-powered business acquisition outreach system for finding and contacting potential acquisition targets in Hamilton, ON, Canada.

## Project Goal
Find 40-50 businesses in Hamilton, ON with $1-2M revenue, 15+ years old, single location. Research top 10 prospects and generate personalized email outreach.

## Tech Stack
- **Python 3.8+** - Core automation scripts
- **Google Sheets** - CRM and tracking (free tier)
- **Claude AI** - Research and email generation
- **Manual processes** - Email sending and response handling

## Setup

1. **Clone and setup environment:**
```bash
git clone https://github.com/mark.filliph/business-acquisition-mvp.git
cd business-acquisition-mvp
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-file.txt
```

2. **Google Sheets API Setup:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing
   - Enable Google Sheets API
   - Create Service Account credentials
   - Download JSON file as `credentials.json`

3. **Create CRM:**
```bash
python scripts/prospects_tracker.py
```

## Core Scripts

### `scripts/prospects_tracker.py`
Creates Google Sheets CRM with:
- **Prospects Sheet**: Main tracking with formulas
- **Email Templates Sheet**: Performance tracking  
- **Analytics Sheet**: Automated metrics dashboard

### `scripts/email_finder.py`
Discovers business email addresses through:
- Website scraping
- Email pattern generation
- Google search strategies
- Hunter.io planning

### `scripts/research_compiler.py`
Formats Claude AI research into:
- Google Sheets ready data
- Email template variables
- Meeting preparation briefs

## Workflow

✅ **Phase 1-3 Complete**: Discovery, research, and email templates ready
🚀 **Phase 4 Active**: Automated outreach and response management

### Current Phase: Email Campaign Execution

1. **Send Initial Emails**: `python scripts/email_sender.py` (dry-run first)
2. **Monitor Responses**: `python scripts/email_tracker.py` 
3. **Automated Follow-ups**: `python scripts/follow_up_automation.py`
4. **Meeting Management**: `python scripts/meeting_manager.py`
5. **Campaign Dashboard**: `python scripts/campaign_dashboard.py` (master control)

## File Structure
```
├── claude-instructions.md    # AI prompts for 8 phases
├── requirements-file.txt     # Python dependencies
├── tech-stack-doc.md        # Technology documentation
├── data/                    # CSV files and research outputs
├── templates/               # Email templates
├── scripts/                 # Automation scripts
└── docs/                    # Meeting briefs and reports
```

## Compliance
- CAN-SPAM compliant (unsubscribe, accurate sender info)
- CASL compliant (Canadian anti-spam legislation)
- Respectful outreach practices

## Success Metrics
- **Target**: 40-50 businesses researched
- **Goal**: 20% response rate, 2-3 meetings booked
- **KPIs**: Email open rate >40%, meeting conversion >20%

---
*Built for the "Buy Then Build" acquisition methodology*