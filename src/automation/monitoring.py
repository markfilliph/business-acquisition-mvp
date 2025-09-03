"""
Production monitoring and alerting system for automated lead generation.
"""
import asyncio
import smtplib
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import structlog
import aiohttp

from .config import AutomationConfig, AlertChannel
from ..core.exceptions import MonitoringError


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning" 
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a monitoring alert."""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    source: str
    metadata: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class MetricSnapshot:
    """System metrics snapshot."""
    timestamp: datetime
    total_runs: int
    successful_runs: int
    failed_runs: int
    error_rate: float
    avg_runtime_seconds: float
    qualified_leads_generated: int
    active_tasks: int
    system_health: str  # healthy, degraded, critical


class MonitoringService:
    """
    Production monitoring service with alerting capabilities.
    
    Features:
    - Real-time metrics collection
    - Multi-channel alerting (Email, Slack, Webhook)
    - Alert deduplication and throttling
    - Health checks and SLA monitoring
    - Performance trend analysis
    """
    
    def __init__(self, config: AutomationConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        
        # Alert management
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # Metrics storage
        self.metrics_history: List[MetricSnapshot] = []
        self.current_metrics = MetricSnapshot(
            timestamp=datetime.now(),
            total_runs=0,
            successful_runs=0,
            failed_runs=0,
            error_rate=0.0,
            avg_runtime_seconds=0.0,
            qualified_leads_generated=0,
            active_tasks=0,
            system_health="healthy"
        )
        
        # Alerting state
        self.last_alert_times: Dict[str, datetime] = {}
        self.alert_throttle_minutes = 15
        
    async def update_metrics(self, metrics: Dict[str, Any]):
        """Update current metrics from scheduler and pipeline."""
        try:
            # Update current metrics
            self.current_metrics = MetricSnapshot(
                timestamp=datetime.now(),
                total_runs=metrics.get('total_runs', 0),
                successful_runs=metrics.get('successful_runs', 0), 
                failed_runs=metrics.get('failed_runs', 0),
                error_rate=metrics.get('error_rate', 0.0),
                avg_runtime_seconds=metrics.get('avg_runtime_seconds', 0.0),
                qualified_leads_generated=metrics.get('qualified_leads', 0),
                active_tasks=metrics.get('active_tasks', 0),
                system_health=self._calculate_system_health(metrics)
            )
            
            # Store historical data
            self.metrics_history.append(self.current_metrics)
            
            # Trim history to last 24 hours
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.metrics_history = [
                m for m in self.metrics_history if m.timestamp > cutoff_time
            ]
            
            # Check for alert conditions
            await self._check_alert_conditions()
            
        except Exception as e:
            self.logger.error("metrics_update_failed", error=str(e))
    
    def _calculate_system_health(self, metrics: Dict[str, Any]) -> str:
        """Calculate overall system health status."""
        error_rate = metrics.get('error_rate', 0.0)
        qualified_leads = metrics.get('qualified_leads', 0)
        
        if error_rate > 0.5:  # 50% error rate
            return "critical"
        elif error_rate > 0.2 or qualified_leads < self.config.alerts.min_qualified_leads:
            return "degraded" 
        else:
            return "healthy"
    
    async def _check_alert_conditions(self):
        """Check current metrics against alert thresholds."""
        if not self.config.alerts.enabled:
            return
            
        alerts_to_fire = []
        
        # Check error rate
        if self.current_metrics.error_rate > self.config.alerts.max_error_rate:
            alerts_to_fire.append({
                'id': 'high_error_rate',
                'title': 'High Error Rate Detected',
                'message': f'Error rate is {self.current_metrics.error_rate:.1%}, exceeding threshold of {self.config.alerts.max_error_rate:.1%}',
                'severity': AlertSeverity.ERROR if self.current_metrics.error_rate < 0.5 else AlertSeverity.CRITICAL,
                'source': 'monitoring'
            })
        
        # Check qualified leads threshold
        if self.current_metrics.qualified_leads_generated < self.config.alerts.min_qualified_leads:
            alerts_to_fire.append({
                'id': 'low_qualified_leads',
                'title': 'Low Qualified Leads Generated',
                'message': f'Only {self.current_metrics.qualified_leads_generated} qualified leads generated, minimum is {self.config.alerts.min_qualified_leads}',
                'severity': AlertSeverity.WARNING,
                'source': 'monitoring'
            })
        
        # Check runtime performance
        if self.current_metrics.avg_runtime_seconds > self.config.alerts.max_runtime_minutes * 60:
            alerts_to_fire.append({
                'id': 'slow_performance',
                'title': 'Slow Pipeline Performance',
                'message': f'Average runtime is {self.current_metrics.avg_runtime_seconds/60:.1f} minutes, exceeding {self.config.alerts.max_runtime_minutes} minutes',
                'severity': AlertSeverity.WARNING,
                'source': 'monitoring'
            })
        
        # Fire alerts
        for alert_data in alerts_to_fire:
            await self._fire_alert(**alert_data)
    
    async def _fire_alert(
        self,
        id: str,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Fire an alert through configured channels."""
        
        # Check alert throttling
        if self._is_alert_throttled(id):
            return
            
        # Create alert
        alert = Alert(
            id=id,
            title=title,
            message=message,
            severity=severity,
            timestamp=datetime.now(),
            source=source,
            metadata=metadata or {}
        )
        
        # Store alert
        self.active_alerts[id] = alert
        self.alert_history.append(alert)
        self.last_alert_times[id] = alert.timestamp
        
        # Log the alert
        self.logger.warning("alert_fired",
                          alert_id=id,
                          title=title,
                          severity=severity.value,
                          source=source)
        
        # Send through configured channels
        for channel in self.config.alerts.channels:
            try:
                if channel == AlertChannel.EMAIL:
                    await self._send_email_alert(alert)
                elif channel == AlertChannel.WEBHOOK:
                    await self._send_webhook_alert(alert)
                elif channel == AlertChannel.SLACK:
                    await self._send_slack_alert(alert)
                elif channel == AlertChannel.LOG:
                    pass  # Already logged above
                    
            except Exception as e:
                self.logger.error("alert_delivery_failed",
                                channel=channel.value,
                                alert_id=id,
                                error=str(e))
    
    def _is_alert_throttled(self, alert_id: str) -> bool:
        """Check if alert is throttled."""
        if alert_id not in self.last_alert_times:
            return False
            
        last_alert_time = self.last_alert_times[alert_id]
        throttle_until = last_alert_time + timedelta(minutes=self.alert_throttle_minutes)
        
        return datetime.now() < throttle_until
    
    async def _send_email_alert(self, alert: Alert):
        """Send alert via email."""
        if not all([
            self.config.alerts.smtp_host,
            self.config.alerts.smtp_username,
            self.config.alerts.smtp_password,
            self.config.alerts.alert_recipients
        ]):
            self.logger.warning("email_alert_config_incomplete")
            return
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = self.config.alerts.smtp_username
        msg['To'] = ", ".join(self.config.alerts.alert_recipients)
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
        
        # Email body
        body = f"""
Alert Details:
--------------
Title: {alert.title}
Severity: {alert.severity.value.upper()}
Source: {alert.source}
Timestamp: {alert.timestamp.isoformat()}
        
Message:
{alert.message}

Current System Metrics:
-----------------------
Total Runs: {self.current_metrics.total_runs}
Success Rate: {(self.current_metrics.successful_runs / max(1, self.current_metrics.total_runs)):.1%}
Error Rate: {self.current_metrics.error_rate:.1%}
Qualified Leads: {self.current_metrics.qualified_leads_generated}
System Health: {self.current_metrics.system_health.upper()}

This is an automated alert from the Lead Generation System.
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        try:
            with smtplib.SMTP(self.config.alerts.smtp_host, self.config.alerts.smtp_port) as server:
                server.starttls()
                server.login(self.config.alerts.smtp_username, self.config.alerts.smtp_password)
                server.send_message(msg)
                
            self.logger.info("email_alert_sent", alert_id=alert.id)
            
        except Exception as e:
            raise MonitoringError(f"Failed to send email alert: {e}")
    
    async def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook."""
        if not self.config.alerts.webhook_url:
            return
            
        payload = {
            'alert': asdict(alert),
            'metrics': asdict(self.current_metrics),
            'timestamp': alert.timestamp.isoformat()
        }
        
        headers = {'Content-Type': 'application/json'}
        
        # Add HMAC signature if secret is configured
        if self.config.alerts.webhook_secret:
            signature = hmac.new(
                self.config.alerts.webhook_secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            headers['X-Signature-SHA256'] = f"sha256={signature}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.alerts.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response.raise_for_status()
                    
            self.logger.info("webhook_alert_sent", alert_id=alert.id)
            
        except Exception as e:
            raise MonitoringError(f"Failed to send webhook alert: {e}")
    
    async def _send_slack_alert(self, alert: Alert):
        """Send alert via Slack."""
        if not self.config.alerts.slack_token:
            return
            
        # Slack color coding
        color_map = {
            AlertSeverity.INFO: "good",
            AlertSeverity.WARNING: "warning", 
            AlertSeverity.ERROR: "danger",
            AlertSeverity.CRITICAL: "danger"
        }
        
        payload = {
            "channel": self.config.alerts.slack_channel,
            "username": "Lead Generation Bot",
            "icon_emoji": ":warning:",
            "attachments": [{
                "color": color_map.get(alert.severity, "danger"),
                "title": alert.title,
                "text": alert.message,
                "fields": [
                    {
                        "title": "Severity",
                        "value": alert.severity.value.upper(),
                        "short": True
                    },
                    {
                        "title": "Source", 
                        "value": alert.source,
                        "short": True
                    },
                    {
                        "title": "System Health",
                        "value": self.current_metrics.system_health.upper(),
                        "short": True
                    },
                    {
                        "title": "Error Rate",
                        "value": f"{self.current_metrics.error_rate:.1%}",
                        "short": True
                    }
                ],
                "timestamp": int(alert.timestamp.timestamp())
            }]
        }
        
        headers = {
            "Authorization": f"Bearer {self.config.alerts.slack_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://slack.com/api/chat.postMessage",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response.raise_for_status()
                    
            self.logger.info("slack_alert_sent", alert_id=alert.id)
            
        except Exception as e:
            raise MonitoringError(f"Failed to send Slack alert: {e}")
    
    def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now()
            del self.active_alerts[alert_id]
            
            self.logger.info("alert_resolved", alert_id=alert_id)
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [a for a in self.alert_history if a.timestamp > cutoff_time]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        return asdict(self.current_metrics)
    
    def get_performance_trend(self, hours: int = 6) -> Dict[str, Any]:
        """Get performance trend analysis."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        if len(recent_metrics) < 2:
            return {"trend": "insufficient_data"}
        
        # Calculate trends
        error_rates = [m.error_rate for m in recent_metrics]
        runtimes = [m.avg_runtime_seconds for m in recent_metrics]
        
        error_trend = "stable"
        if len(error_rates) > 1:
            if error_rates[-1] > error_rates[0] * 1.2:
                error_trend = "increasing"
            elif error_rates[-1] < error_rates[0] * 0.8:
                error_trend = "decreasing"
        
        runtime_trend = "stable"
        if len(runtimes) > 1:
            if runtimes[-1] > runtimes[0] * 1.2:
                runtime_trend = "increasing"
            elif runtimes[-1] < runtimes[0] * 0.8:
                runtime_trend = "decreasing"
        
        return {
            "period_hours": hours,
            "data_points": len(recent_metrics),
            "error_rate_trend": error_trend,
            "runtime_trend": runtime_trend,
            "current_error_rate": error_rates[-1] if error_rates else 0,
            "avg_runtime_seconds": runtimes[-1] if runtimes else 0,
            "system_health": recent_metrics[-1].system_health
        }