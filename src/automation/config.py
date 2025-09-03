"""
Automation configuration with environment-specific settings.
"""
import os
from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Optional
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


class ScheduleType(Enum):
    """Automation schedule types."""
    HOURLY = "hourly"
    DAILY = "daily" 
    WEEKLY = "weekly"
    CRON = "cron"


class AlertChannel(Enum):
    """Alert delivery channels."""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


@dataclass
class AutomationSchedule:
    """Automation schedule configuration."""
    enabled: bool = True
    schedule_type: ScheduleType = ScheduleType.DAILY
    
    # Time-based scheduling
    run_time: time = time(9, 0)  # 9:00 AM
    interval_hours: int = 24
    
    # Cron expression (if schedule_type == CRON)
    cron_expression: Optional[str] = None
    
    # Execution limits
    max_leads_per_run: int = 50
    max_concurrent_runs: int = 1
    timeout_minutes: int = 30


@dataclass 
class AlertConfig:
    """Alert and monitoring configuration."""
    enabled: bool = True
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.LOG])
    
    # Alert thresholds  
    min_qualified_leads: int = 3
    max_error_rate: float = 0.1  # 10%
    max_runtime_minutes: int = 15
    
    # Email configuration
    smtp_host: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_username: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_USERNAME"))
    smtp_password: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))
    alert_recipients: List[str] = field(default_factory=lambda: 
        os.getenv("ALERT_RECIPIENTS", "").split(",") if os.getenv("ALERT_RECIPIENTS") else [])
    
    # Webhook configuration  
    webhook_url: Optional[str] = field(default_factory=lambda: os.getenv("WEBHOOK_URL"))
    webhook_secret: Optional[str] = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET"))
    
    # Slack configuration
    slack_token: Optional[str] = field(default_factory=lambda: os.getenv("SLACK_TOKEN"))
    slack_channel: str = field(default_factory=lambda: os.getenv("SLACK_CHANNEL", "#leads"))


@dataclass
class RetryConfig:
    """Error handling and retry configuration."""
    max_retries: int = 3
    backoff_factor: float = 2.0  # Exponential backoff
    retry_exceptions: List[str] = field(default_factory=lambda: [
        "ConnectionError",
        "TimeoutError", 
        "HTTPError",
        "DatabaseError"
    ])
    
    # Circuit breaker settings
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 300  # 5 minutes
    half_open_max_calls: int = 3


@dataclass
class AutomationConfig:
    """Master automation configuration."""
    environment: str = field(default_factory=lambda: os.getenv("AUTOMATION_ENV", "development"))
    
    # Core automation settings
    schedule: AutomationSchedule = field(default_factory=AutomationSchedule)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    
    # Data persistence
    results_retention_days: int = 30
    export_results: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["csv", "json"])
    
    # Performance settings
    batch_size: int = 10
    rate_limit_requests_per_minute: int = 30
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.environment == "production":
            # Production safety checks
            if self.schedule.max_concurrent_runs > 1:
                self.schedule.max_concurrent_runs = 1
                
            if self.schedule.timeout_minutes > 60:
                self.schedule.timeout_minutes = 60
                
            # Ensure alerts are enabled in production
            self.alerts.enabled = True
            
        elif self.environment == "development":
            # Development optimizations
            self.schedule.max_leads_per_run = 20  # Smaller batches
            self.alerts.channels = [AlertChannel.LOG]  # Log only
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"


# Global automation configuration instance
automation_config = AutomationConfig()