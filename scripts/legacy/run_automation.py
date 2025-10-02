#!/usr/bin/env python3
"""
Production automation script for the Lead Generation System.

Usage:
    python scripts/run_automation.py [--config-check] [--dry-run] [--status]

Environment Variables:
    AUTOMATION_ENV: production|development|testing
    SMTP_HOST: Email server hostname
    SMTP_USERNAME: Email username
    SMTP_PASSWORD: Email password  
    ALERT_RECIPIENTS: Comma-separated email addresses
    WEBHOOK_URL: Alert webhook URL
    SLACK_TOKEN: Slack bot token
    SLACK_CHANNEL: Slack channel for alerts
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.automation.runner import AutomatedLeadGenerator
from src.automation.config import automation_config
from src.utils.logging_config import setup_logging


def validate_configuration():
    """Validate automation configuration."""
    issues = []
    
    # Check basic config
    if not automation_config.schedule.enabled:
        issues.append("⚠️  Scheduling is disabled")
    
    # Check alert configuration
    if automation_config.alerts.enabled:
        if not automation_config.alerts.channels:
            issues.append("❌ No alert channels configured")
        
        # Email validation
        if any(ch.value == "email" for ch in automation_config.alerts.channels):
            if not all([
                automation_config.alerts.smtp_host,
                automation_config.alerts.smtp_username, 
                automation_config.alerts.smtp_password,
                automation_config.alerts.alert_recipients
            ]):
                issues.append("❌ Email alerting enabled but configuration incomplete")
        
        # Webhook validation
        if any(ch.value == "webhook" for ch in automation_config.alerts.channels):
            if not automation_config.alerts.webhook_url:
                issues.append("❌ Webhook alerting enabled but URL not configured")
        
        # Slack validation
        if any(ch.value == "slack" for ch in automation_config.alerts.channels):
            if not automation_config.alerts.slack_token:
                issues.append("❌ Slack alerting enabled but token not configured")
    
    return issues


async def check_system_status():
    """Check current system status."""
    print("🔍 AUTOMATION SYSTEM STATUS")
    print("=" * 50)
    
    try:
        automation = AutomatedLeadGenerator()
        status = automation.get_status()
        
        print(f"Environment: {status['configuration']['environment']}")
        print(f"Running: {status['is_running']}")
        print(f"Execution Count: {status['execution_count']}")
        print(f"Last Execution: {status['last_execution'] or 'Never'}")
        print(f"System Health: {status['system_health'].upper()}")
        print(f"Active Alerts: {status['active_alerts']}")
        
        # Configuration summary
        print("\n📋 CONFIGURATION")
        print("-" * 20)
        config = status['configuration']
        print(f"Schedule Enabled: {config['schedule_enabled']}")
        print(f"Max Leads/Run: {config['max_leads_per_run']}")
        print(f"Alert Channels: {', '.join(config['alert_channels'])}")
        
        # Scheduler stats
        if 'scheduler_stats' in status:
            stats = status['scheduler_stats']
            print(f"\n📊 EXECUTION STATS")
            print("-" * 20)
            print(f"Total Runs: {stats.get('total_runs', 0)}")
            print(f"Success Rate: {stats.get('error_rate', 0):.1%}")
            print(f"Active Tasks: {stats.get('active_tasks', 0)}")
            print(f"Running Tasks: {stats.get('running_tasks', 0)}")
        
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        return False
    
    return True


async def run_dry_run():
    """Run a single pipeline execution for testing."""
    print("🧪 DRY RUN MODE")
    print("=" * 50)
    
    try:
        from src.agents.orchestrator import LeadGenerationOrchestrator
        from src.core.config import config
        
        # Run single pipeline execution
        orchestrator = LeadGenerationOrchestrator(config)
        results = await orchestrator.run_full_pipeline(target_leads=10)
        
        print(f"✅ Dry run completed successfully!")
        print(f"   Discovered: {results.total_discovered} businesses")
        print(f"   Qualified: {results.total_qualified} leads") 
        print(f"   Success Rate: {results.success_rate:.1%}")
        print(f"   Duration: {results.duration_seconds:.1f} seconds")
        
        return True
        
    except Exception as e:
        print(f"❌ Dry run failed: {e}")
        return False


async def main():
    """Main automation entry point."""
    parser = argparse.ArgumentParser(description="Lead Generation Automation System")
    parser.add_argument("--config-check", action="store_true", 
                       help="Validate configuration and exit")
    parser.add_argument("--dry-run", action="store_true",
                       help="Run single pipeline execution for testing")
    parser.add_argument("--status", action="store_true",
                       help="Check system status and exit")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(automation_config.environment)
    
    print("🚀 LEAD GENERATION AUTOMATION SYSTEM")
    print("=" * 60)
    print(f"Environment: {automation_config.environment.upper()}")
    print(f"Configuration: {automation_config.is_production() and 'PRODUCTION' or 'DEVELOPMENT'}")
    print()
    
    # Configuration check
    if args.config_check or automation_config.is_production():
        print("🔧 CONFIGURATION VALIDATION")
        print("-" * 40)
        
        issues = validate_configuration()
        
        if issues:
            print("Configuration issues found:")
            for issue in issues:
                print(f"  {issue}")
            
            if automation_config.is_production():
                print("❌ Cannot start in production with configuration issues")
                sys.exit(1)
            else:
                print("⚠️  Continuing with configuration warnings (development mode)")
        else:
            print("✅ Configuration validation passed")
        
        print()
        
        if args.config_check:
            return
    
    # Status check
    if args.status:
        success = await check_system_status()
        sys.exit(0 if success else 1)
    
    # Dry run
    if args.dry_run:
        success = await run_dry_run()
        sys.exit(0 if success else 1)
    
    # Normal automation mode
    print("🏃 Starting automated lead generation...")
    print("Use Ctrl+C to stop gracefully")
    print()
    
    automation = AutomatedLeadGenerator()
    
    try:
        await automation.start()
    except KeyboardInterrupt:
        print("\n⏹️  Shutdown requested by user")
        await automation.stop()
        print("✅ Automation stopped gracefully")
    except Exception as e:
        print(f"\n❌ Automation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())