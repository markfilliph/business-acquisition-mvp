#!/bin/bash

# Enhanced Business Acquisition Lead Generation System
# Comprehensive Quick Start Script with Advanced Validation & Monitoring

echo "=========================================="
echo "🚀 Business Acquisition Lead Generation System"
echo "Enhanced Quick Start Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_feature() {
    echo -e "${PURPLE}🔧${NC} $1"
}

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        print_status "Python $PYTHON_VERSION found (meets minimum requirement 3.8+)"
    else
        print_error "Python $PYTHON_VERSION found but 3.8+ is required"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
print_status "Virtual environment activated"

# Install/upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
print_status "Pip upgraded"

# Install requirements
echo "Installing requirements..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt > /dev/null 2>&1
    print_status "Core requirements installed"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.template" ]; then
        echo "Creating .env file from template..."
        cp .env.template .env
        print_warning "Please edit .env file with your API keys"
        echo "Opening .env in editor..."
        ${EDITOR:-nano} .env
    else
        print_warning ".env.template not found - creating basic .env file"
        cat > .env << 'EOF'
# API Keys for Enhanced Lead Validation
HUNTER_API_KEY=your_hunter_api_key_here
NEVERBOUNCE_API_KEY=your_neverbounce_api_key_here
CLEARBIT_API_KEY=your_clearbit_api_key_here
APOLLO_API_KEY=your_apollo_api_key_here
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here
BUSINESS_REGISTRY_API_KEY=your_business_registry_api_key_here

# Database Configuration
DATABASE_URL=sqlite:///data/leads.db

# Email Configuration
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# Monitoring Configuration
ENABLE_MONITORING=true
MONITORING_INTERVAL=3600

# Lead Generation Settings
TARGET_LEADS_PER_RUN=5
MIN_REVENUE=1000000
MAX_REVENUE=1400000
TARGET_LOCATION=Hamilton, ON
EOF
        print_warning "Basic .env file created - please edit with your API keys"
        ${EDITOR:-nano} .env
    fi
else
    print_status ".env file exists"
fi

# Check for Google credentials
if [ ! -f "credentials.json" ]; then
    print_warning "Google Sheets credentials not found"
    echo "Please download credentials.json from Google Cloud Console"
    echo "Visit: https://console.cloud.google.com/apis/credentials"
    echo ""
    read -p "Press Enter when credentials.json is in place..."
fi

# Create necessary directories
echo "Creating enhanced directory structure..."
mkdir -p data reports logs cache templates models dashboard
mkdir -p data/validation data/scoring data/monitoring data/metrics
print_status "Enhanced directories created"

# Initialize databases
echo "Initializing databases..."
python3 -c "
import sqlite3
from pathlib import Path

# Create main directories
Path('data').mkdir(exist_ok=True)

# Initialize all databases
databases = [
    'data/leads.db',
    'data/lead_validation.db',
    'data/lead_scoring.db',
    'data/due_diligence.db',
    'data/intent_detection.db',
    'data/lead_monitoring.db',
    'data/metrics_tracking.db'
]

for db_path in databases:
    conn = sqlite3.connect(db_path)
    conn.close()
    print(f'Initialized {db_path}')
"
print_status "Databases initialized"

# Check MongoDB
echo "Checking MongoDB..."
if command -v mongod &> /dev/null; then
    print_status "MongoDB found"
    echo "Starting MongoDB (if not running)..."
    if ! pgrep -x "mongod" > /dev/null; then
        mongod --fork --logpath logs/mongodb.log --dbpath ~/data/db > /dev/null 2>&1 || true
    fi
else
    print_warning "MongoDB not found - using Docker instead"
    if command -v docker &> /dev/null; then
        echo "Starting MongoDB in Docker..."
        docker run -d --name mongodb -p 27017:27017 mongo:5.0 > /dev/null 2>&1 || true
        print_status "MongoDB started in Docker"
    else
        print_warning "Neither MongoDB nor Docker found - some features may be limited"
    fi
fi

# Check Redis (optional)
echo "Checking Redis (optional)..."
if command -v redis-cli &> /dev/null; then
    print_status "Redis found"
    if ! pgrep -x "redis-server" > /dev/null; then
        redis-server --daemonize yes > /dev/null 2>&1 || true
    fi
else
    print_warning "Redis not found - caching will use file-based cache"
fi

echo ""
echo "=========================================="
print_status "Enhanced Setup Complete!"
echo "=========================================="
echo ""

print_feature "NEW FEATURES AVAILABLE:"
echo "• Advanced Lead Validation with Multi-Source Verification"
echo "• ML-Powered Lead Scoring System"
echo "• Automated Due Diligence Checks"
echo "• Intent Signal Detection"
echo "• Real-Time Lead Monitoring"
echo "• Comprehensive Performance Metrics"
echo ""

# Enhanced Menu
while true; do
    echo "🎯 What would you like to do?"
    echo ""
    echo "📊 CORE OPERATIONS:"
    echo "1) Run Enhanced Pipeline (5 High-Quality Leads)"
    echo "2) Run Quick Test (2 leads with full validation)"
    echo "3) Validate Existing Leads (Multi-Source)"
    echo "4) Export Hot Leads with Scores"
    echo ""
    echo "🔍 ADVANCED FEATURES:"
    echo "5) Run Lead Scoring Analysis"
    echo "6) Perform Due Diligence Check"
    echo "7) Detect Intent Signals"
    echo "8) Start Real-Time Monitoring"
    echo "9) Generate Performance Report"
    echo ""
    echo "📧 OUTREACH & TESTING:"
    echo "10) Send Test Email"
    echo "11) Test Contact Enrichment"
    echo "12) Run System Health Check"
    echo ""
    echo "🚀 AUTOMATION:"
    echo "13) Start Automated Scheduler"
    echo "14) Launch Performance Dashboard"
    echo "15) Run Integration Tests"
    echo ""
    echo "0) Exit"
    echo ""

    read -p "Enter your choice [0-15]: " choice

    case $choice in
        1)
            echo "🚀 Starting enhanced pipeline with full validation..."
            python3 scripts/run_pipeline.py --target-leads 5 --enhanced-validation --with-scoring
            ;;
        2)
            echo "🧪 Running quick test with comprehensive validation..."
            python3 scripts/run_pipeline.py --target-leads 2 --enhanced-validation --with-scoring --with-due-diligence
            ;;
        3)
            echo "🔍 Validating existing leads with multi-source verification..."
            python3 scripts/run_pipeline.py --validate-only --enhanced-validation
            ;;
        4)
            echo "📊 Exporting hot leads with comprehensive scoring..."
            python3 scripts/run_pipeline.py --export-only --include-scores --include-metrics
            ;;
        5)
            echo "🎯 Running lead scoring analysis..."
            python3 -c "
from scripts.lead_scorer import LeadScorer
from scripts.services.data_service import DataService

scorer = LeadScorer()
data_service = DataService()

# Get recent leads
businesses = data_service.get_recent_businesses(limit=10)
if businesses:
    for business in businesses:
        score = scorer.score_lead(business)
        print(f'Business: {score.business_name}')
        print(f'Score: {score.total_score:.1f}/100')
        print(f'Priority: {score.priority_level}')
        print(f'Recommendation: {score.recommended_action}')
        print('-' * 50)
else:
    print('No businesses found. Run lead generation first.')
"
            ;;
        6)
            echo "🔍 Performing due diligence check..."
            python3 -c "
from scripts.due_diligence import DueDiligenceAutomation
from scripts.services.data_service import DataService

dd = DueDiligenceAutomation()
data_service = DataService()

businesses = data_service.get_recent_businesses(limit=5)
if businesses:
    for business in businesses:
        report = dd.perform_checks(business)
        print(f'Business: {report.business_name}')
        print(f'Risk Score: {report.overall_risk_score:.2f}')
        print(f'Red Flags: {len(report.red_flags)}')
        for flag in report.red_flags:
            print(f'  - {flag}')
        print(f'Recommendations:')
        for rec in report.recommendations:
            print(f'  - {rec}')
        print('-' * 50)
else:
    print('No businesses found. Run lead generation first.')
"
            ;;
        7)
            echo "🎯 Detecting intent signals..."
            python3 -c "
from scripts.intent_detector import IntentDetector
from scripts.services.data_service import DataService

detector = IntentDetector()
data_service = DataService()

businesses = data_service.get_recent_businesses(limit=5)
if businesses:
    for business in businesses:
        analysis = detector.detect_intent(business)
        print(f'Business: {analysis.business_name}')
        print(f'Intent Score: {analysis.overall_intent_score:.2f}')
        print(f'Buying Probability: {analysis.buying_probability:.2f}')
        print(f'Urgency: {analysis.urgency_level}')
        print(f'Approach: {analysis.recommended_approach}')
        print('Detected Signals:')
        for signal in analysis.detected_signals:
            print(f'  - {signal.signal_type}: {signal.confidence:.2f}')
        print('-' * 50)
else:
    print('No businesses found. Run lead generation first.')
"
            ;;
        8)
            echo "📡 Starting real-time monitoring..."
            python3 -c "
from scripts.lead_monitor import LeadMonitor
from scripts.services.data_service import DataService

monitor = LeadMonitor()
data_service = DataService()

# Add recent businesses to monitoring
businesses = data_service.get_recent_businesses(limit=10)
for business in businesses:
    monitor.add_business_to_monitoring(business, priority='medium')

print(f'Added {len(businesses)} businesses to monitoring')
print('Starting monitoring in background...')
monitor.start_monitoring()
print('Monitoring started! Press Ctrl+C to stop.')

try:
    import time
    while True:
        time.sleep(60)
        recent_alerts = monitor.get_recent_alerts(hours=1)
        if recent_alerts:
            print(f'New alerts: {len(recent_alerts)}')
            for alert in recent_alerts[-3:]:  # Show last 3
                print(f'  - {alert.alert_type}: {alert.message}')
except KeyboardInterrupt:
    monitor.stop_monitoring()
    print('Monitoring stopped.')
"
            ;;
        9)
            echo "📈 Generating performance report..."
            python3 -c "
from scripts.metrics_tracker import LeadQualityMetrics

tracker = LeadQualityMetrics()

# Calculate current metrics
metrics = tracker.calculate_metrics(30)
trends = tracker.get_performance_trends(90)
source_report = tracker.get_source_performance_report()

print('PERFORMANCE REPORT (Last 30 Days)')
print('=' * 50)
print(f'Total Leads Processed: {metrics.total_leads_processed}')
print(f'Hot Leads Generated: {metrics.hot_leads_generated}')
print(f'Verification Rate: {metrics.verification_rate:.1%}')
print(f'False Positive Rate: {metrics.false_positive_rate:.1%}')
print(f'Data Completeness: {metrics.data_completeness:.1%}')
print(f'Conversion to Meeting: {metrics.conversion_to_meeting:.1%}')
print(f'Avg Validation Time: {metrics.time_to_validate:.1f} seconds')

print('\nSOURCE PERFORMANCE:')
for source in source_report['sources'][:5]:
    print(f'  {source[\"source\"]}: {source[\"reliability_score\"]:.1%} reliability')

print('\nTREND ANALYSIS:')
for trend in trends:
    print(f'  {trend.metric_name}: {trend.trend_direction} ({trend.improvement_percentage:+.1f}%)')
"
            ;;
        10)
            echo "📧 Sending test email..."
            read -p "Enter recipient email: " email
            python3 -c "
from scripts.email_automation import EmailAutomation
automation = EmailAutomation()
result = automation.send_test_email('$email', 'retirement_initial')
print('Email sent successfully!' if result else 'Email failed')
"
            ;;
        11)
            echo "🔍 Testing contact enrichment..."
            read -p "Enter email to test: " test_email
            python3 -c "
from scripts.contact_enrichment import ContactEnrichment

enricher = ContactEnrichment()
result = enricher.enrich_contact('$test_email')

print(f'Email: $test_email')
print(f'Valid: {result.email_valid}')
print(f'Person Exists: {result.person_exists}')
print(f'Role Confirmed: {result.role_confirmed}')
print(f'Recent Activity: {result.recent_activity}')
print(f'Confidence Score: {result.confidence_score:.2f}')
print(f'Sources Used: {result.validation_sources}')
"
            ;;
        12)
            echo "🔧 Running system health check..."
            python3 -c "
import os
import sqlite3
from pathlib import Path

print('SYSTEM HEALTH CHECK')
print('=' * 30)

# Check databases
databases = [
    'data/leads.db',
    'data/lead_validation.db',
    'data/lead_scoring.db',
    'data/due_diligence.db',
    'data/intent_detection.db',
    'data/lead_monitoring.db',
    'data/metrics_tracking.db'
]

print('Database Status:')
for db in databases:
    if Path(db).exists():
        try:
            conn = sqlite3.connect(db)
            conn.close()
            print(f'  ✓ {db}')
        except:
            print(f'  ✗ {db} (corrupted)')
    else:
        print(f'  ✗ {db} (missing)')

# Check API keys
print('\nAPI Configuration:')
api_keys = ['HUNTER_API_KEY', 'CLEARBIT_API_KEY', 'APOLLO_API_KEY', 'NEVERBOUNCE_API_KEY']
for key in api_keys:
    if os.getenv(key):
        print(f'  ✓ {key} configured')
    else:
        print(f'  ✗ {key} missing')

# Check directories
print('\nDirectory Structure:')
dirs = ['data', 'logs', 'cache', 'models', 'reports']
for dir_name in dirs:
    if Path(dir_name).exists():
        print(f'  ✓ {dir_name}/')
    else:
        print(f'  ✗ {dir_name}/ missing')

print('\nSystem Status: Ready for enhanced lead generation!')
"
            ;;
        13)
            echo "🤖 Starting automated scheduler..."
            python3 scripts/scheduler.py
            ;;
        14)
            echo "📊 Launching performance dashboard..."
            echo "Dashboard will be available at http://localhost:8080"
            python3 -m http.server 8080 --directory dashboard &
            echo "Dashboard started in background (PID: $!)"
            ;;
        15)
            echo "🧪 Running integration tests..."
            python3 -m pytest tests/ -v --tb=short
            ;;
        0)
            echo "👋 Thank you for using the Enhanced Lead Generation System!"
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            ;;
    esac

    echo ""
    echo "Press Enter to continue..."
    read
    clear
done