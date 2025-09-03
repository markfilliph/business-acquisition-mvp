# Lead Generation Automation System

## Overview

The automation system provides enterprise-grade scheduling, monitoring, and alerting capabilities for the lead generation pipeline. It enables hands-off operation with comprehensive error handling and multi-channel notifications.

## Key Features

### 🤖 Automated Scheduling
- **Cron-based scheduling** with flexible expressions
- **Graceful shutdown** handling with SIGINT/SIGTERM
- **Concurrent execution limits** to prevent resource conflicts
- **Task timeout management** with configurable limits

### 🚨 Multi-Channel Alerting  
- **Email notifications** via SMTP with HTML formatting
- **Slack integration** with rich message formatting
- **Webhook delivery** with HMAC signature validation
- **Alert throttling** and deduplication

### 📊 Real-time Monitoring
- **Performance metrics** collection and trending
- **Health checks** with system status reporting
- **Error rate monitoring** with configurable thresholds
- **Lead quality tracking** with SLA alerting

### ⚡ Error Recovery
- **Circuit breakers** for external service failures
- **Exponential backoff** with jitter for retries
- **Task failure tracking** with detailed error logging
- **Automatic recovery** after service restoration

## Architecture

```
src/automation/
├── config.py          # Configuration management
├── scheduler.py        # Cron-based task scheduler  
├── monitoring.py       # Multi-channel alerting
└── runner.py          # Main automation orchestrator
```

### Core Components

#### AutomationScheduler
- Manages cron-based task execution
- Handles concurrent task limits
- Provides graceful shutdown
- Tracks task status and metrics

#### MonitoringService
- Sends multi-channel alerts
- Tracks performance metrics
- Performs health checks
- Analyzes performance trends

#### AutomatedLeadGenerator
- Main orchestration component
- Integrates scheduler and monitoring
- Manages pipeline execution
- Provides status reporting

## Configuration

### Environment Variables

```bash
# Automation Settings
AUTOMATION_ENV=production
SCHEDULE_ENABLED=true
SCHEDULE_CRON="0 9 * * *"  # Daily at 9 AM
MAX_LEADS_PER_RUN=50
MAX_CONCURRENT_RUNS=1
TIMEOUT_MINUTES=30

# Email Alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_RECIPIENTS=admin@company.com,manager@company.com

# Slack Alerts  
SLACK_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL=#lead-generation

# Webhook Alerts
WEBHOOK_URL=https://hooks.slack.com/services/...
WEBHOOK_SECRET=your-webhook-signing-secret

# Monitoring Thresholds
MAX_ERROR_RATE=0.2
MIN_QUALIFIED_LEADS=5
ALERT_THROTTLE_MINUTES=60
```

### Schedule Types

The system supports multiple scheduling approaches:

```python
# Cron expression (most flexible)
SCHEDULE_CRON="0 9 * * 1-5"  # Weekdays at 9 AM

# Predefined schedules
SCHEDULE_TYPE=daily    # Daily at configured time
SCHEDULE_TYPE=hourly   # Every hour
SCHEDULE_TYPE=weekly   # Weekly on configured day
```

## Usage

### Command Line Interface

```bash
# Start production automation
python scripts/run_automation.py

# Configuration validation
python scripts/run_automation.py --config-check

# System status check
python scripts/run_automation.py --status

# Single execution test
python scripts/run_automation.py --dry-run
```

### Programmatic Usage

```python
from src.automation.runner import AutomatedLeadGenerator

# Initialize automation system
automation = AutomatedLeadGenerator()

# Start automated execution
await automation.start()

# Get system status
status = automation.get_status()
print(f"System health: {status['system_health']}")
print(f"Execution count: {status['execution_count']}")

# Graceful shutdown
await automation.stop()
```

## Monitoring & Alerting

### Alert Types

1. **Pipeline Success**: Successful execution with qualified leads
2. **Pipeline Failure**: Execution failure with error details
3. **High Error Rate**: Error rate exceeds threshold
4. **Low Lead Quality**: Qualified leads below minimum
5. **System Health**: Resource or performance issues

### Alert Channels

#### Email Alerts
- HTML formatted messages
- Detailed metrics and error information  
- Configurable recipient lists
- Automatic retry on delivery failure

#### Slack Alerts
- Rich message formatting with blocks
- Color-coded by severity level
- Direct links to system logs
- Channel-specific delivery

#### Webhook Alerts  
- JSON payload with full context
- HMAC signature validation
- Configurable retry policies
- Custom endpoint integration

### Performance Metrics

The system tracks comprehensive metrics:

```python
# Execution Metrics
total_runs: int
successful_runs: int  
failed_runs: int
error_rate: float
avg_runtime_seconds: float

# Business Metrics
qualified_leads_generated: int
total_leads_discovered: int
lead_quality_score: float

# System Metrics  
active_tasks: int
system_health: str
memory_usage_mb: float
```

## Production Deployment

### Docker Integration

```yaml
# docker-compose.yml
services:
  automation:
    build: .
    environment:
      - AUTOMATION_ENV=production
      - SCHEDULE_ENABLED=true
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

### Process Management

```bash
# Systemd service (Linux)
sudo cp automation.service /etc/systemd/system/
sudo systemctl enable automation
sudo systemctl start automation

# Check status
sudo systemctl status automation
```

### Health Checks

```bash
# Kubernetes readiness probe
http://localhost:8080/health

# Docker health check
HEALTHCHECK --interval=30s --timeout=10s \
  CMD python -c "from src.automation.runner import AutomatedLeadGenerator; print('healthy')"
```

## Security Considerations

### Secrets Management
- Environment variables for sensitive data
- No secrets in logs or error messages
- Secure webhook signature validation
- Encrypted SMTP authentication

### Access Control
- Production environment validation
- Configuration safety checks
- Resource usage limits
- Network security compliance

### Audit Logging
- Comprehensive execution tracking
- Error logging with context
- Performance metrics retention
- Alert delivery confirmation

## Testing

### Unit Tests

```bash
# Run automation tests
pytest tests/test_automation.py -v

# Test specific components
pytest tests/test_automation.py::TestAutomationScheduler -v
pytest tests/test_automation.py::TestMonitoringService -v
```

### Integration Tests

```bash
# End-to-end automation test
pytest tests/test_automation.py::test_end_to_end_automation -v

# Mock external dependencies
pytest --mock-slack --mock-email tests/test_automation.py
```

### Load Testing

```bash
# Concurrent execution test
pytest tests/test_automation.py::test_concurrent_execution -v

# Performance benchmarks
pytest tests/test_automation.py::test_performance_metrics -v
```

## Troubleshooting

### Common Issues

#### Configuration Errors
```bash
# Validate configuration
python scripts/run_automation.py --config-check

# Check environment variables
python -c "from src.automation.config import automation_config; print(automation_config)"
```

#### Alert Delivery Failures
```bash
# Test email configuration
python -c "
from src.automation.monitoring import MonitoringService
service = MonitoringService()
await service._test_email_config()
"

# Test Slack integration  
python -c "
from src.automation.monitoring import MonitoringService
service = MonitoringService()  
await service._test_slack_config()
"
```

#### Scheduling Issues
```bash
# Verify cron expression
python -c "
from croniter import croniter
from datetime import datetime
cron = croniter('0 9 * * *', datetime.now())
print('Next runs:')
for i in range(5):
    print(cron.get_next(datetime))
"
```

### Performance Optimization

1. **Adjust concurrency limits** based on system resources
2. **Configure timeout values** for long-running operations  
3. **Tune alert thresholds** to reduce noise
4. **Monitor resource usage** and scale appropriately

### Error Recovery

The system includes automatic recovery mechanisms:

- **Circuit breakers** prevent cascading failures
- **Exponential backoff** reduces load during outages
- **Health checks** detect and report system issues
- **Graceful degradation** maintains core functionality

## Future Enhancements

### Planned Features
- Web-based dashboard for monitoring
- Advanced scheduling with dependencies
- Multi-tenant configuration support
- Enhanced analytics and reporting
- Integration with external monitoring tools

### Extensibility Points
- Custom alert channel implementations
- Pluggable scheduling backends
- Configurable metric collectors
- External configuration providers