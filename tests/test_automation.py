"""
Tests for the automation system.
"""
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from src.automation.config import AutomationConfig, ScheduleType, AlertChannel
from src.automation.scheduler import AutomationScheduler, ScheduledTask, TaskStatus
from src.automation.monitoring import MonitoringService, AlertSeverity
from src.automation.runner import AutomatedLeadGenerator


@pytest.fixture
def test_config():
    """Create test automation configuration."""
    config = AutomationConfig()
    config.environment = "testing"
    config.schedule.enabled = True
    config.schedule.timeout_minutes = 1  # Short timeout for tests
    config.alerts.enabled = True
    config.alerts.channels = [AlertChannel.LOG]
    return config


@pytest.fixture
def scheduler(test_config):
    """Create test scheduler."""
    return AutomationScheduler(test_config)


@pytest.fixture
def monitoring(test_config):
    """Create test monitoring service."""
    return MonitoringService(test_config)


class TestAutomationScheduler:
    """Test automation scheduler functionality."""
    
    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initializes correctly."""
        assert scheduler.config.environment == "testing"
        assert len(scheduler.tasks) == 0
        assert len(scheduler.running_tasks) == 0
    
    def test_add_task(self, scheduler):
        """Test adding tasks to scheduler."""
        async def dummy_task():
            return "completed"
        
        task = scheduler.add_task(
            task_id="test_task",
            name="Test Task",
            function=dummy_task,
            schedule="0 9 * * *"  # Daily at 9 AM
        )
        
        assert task.task_id == "test_task"
        assert task.name == "Test Task"
        assert task.enabled
        assert task.next_run is not None
        assert "test_task" in scheduler.tasks
    
    def test_invalid_schedule(self, scheduler):
        """Test handling of invalid cron expressions."""
        async def dummy_task():
            return "completed"
        
        with pytest.raises(Exception):  # Should raise AutomationError
            scheduler.add_task(
                task_id="invalid_task",
                name="Invalid Task", 
                function=dummy_task,
                schedule="invalid cron"
            )
    
    def test_duplicate_task_id(self, scheduler):
        """Test handling of duplicate task IDs."""
        async def dummy_task():
            return "completed"
        
        # Add first task
        scheduler.add_task(
            task_id="duplicate_test",
            name="First Task",
            function=dummy_task,
            schedule="hourly"
        )
        
        # Try to add duplicate
        with pytest.raises(Exception):  # Should raise AutomationError
            scheduler.add_task(
                task_id="duplicate_test",
                name="Second Task",
                function=dummy_task,
                schedule="daily"
            )
    
    @pytest.mark.asyncio
    async def test_task_execution(self, scheduler):
        """Test task execution with success."""
        execution_count = 0
        
        async def test_task():
            nonlocal execution_count
            execution_count += 1
            return "success"
        
        # Add task with immediate execution
        task = scheduler.add_task(
            task_id="exec_test",
            name="Execution Test",
            function=test_task,
            schedule="* * * * *"  # Every minute
        )
        
        # Manually trigger execution
        task.next_run = datetime.now() - timedelta(seconds=1)
        await scheduler._execute_task(task)
        
        assert execution_count == 1
        assert task.status == TaskStatus.COMPLETED
        assert task.run_count == 1
        assert task.last_error is None
    
    @pytest.mark.asyncio
    async def test_task_failure(self, scheduler):
        """Test task execution with failure."""
        async def failing_task():
            raise ValueError("Test failure")
        
        task = scheduler.add_task(
            task_id="fail_test",
            name="Failing Test",
            function=failing_task,
            schedule="* * * * *"
        )
        
        # Manually trigger execution
        task.next_run = datetime.now() - timedelta(seconds=1)
        await scheduler._execute_task(task)
        
        assert task.status == TaskStatus.FAILED
        assert task.error_count == 1
        assert "Test failure" in task.last_error
    
    @pytest.mark.asyncio
    async def test_task_timeout(self, scheduler):
        """Test task timeout handling."""
        async def slow_task():
            await asyncio.sleep(10)  # Longer than timeout
            return "completed"
        
        task = scheduler.add_task(
            task_id="timeout_test",
            name="Timeout Test", 
            function=slow_task,
            schedule="* * * * *"
        )
        
        # Manually trigger execution
        task.next_run = datetime.now() - timedelta(seconds=1)
        await scheduler._execute_task(task)
        
        assert task.status == TaskStatus.FAILED
        assert "timeout" in task.last_error.lower()


class TestMonitoringService:
    """Test monitoring and alerting functionality."""
    
    def test_monitoring_initialization(self, monitoring):
        """Test monitoring service initializes correctly."""
        assert monitoring.config.environment == "testing"
        assert len(monitoring.active_alerts) == 0
        assert monitoring.current_metrics.system_health == "healthy"
    
    @pytest.mark.asyncio
    async def test_metrics_update(self, monitoring):
        """Test metrics update functionality."""
        test_metrics = {
            'total_runs': 10,
            'successful_runs': 8,
            'failed_runs': 2,
            'error_rate': 0.2,
            'avg_runtime_seconds': 45.5,
            'qualified_leads': 5,
            'active_tasks': 2
        }
        
        await monitoring.update_metrics(test_metrics)
        
        assert monitoring.current_metrics.total_runs == 10
        assert monitoring.current_metrics.successful_runs == 8
        assert monitoring.current_metrics.error_rate == 0.2
        assert monitoring.current_metrics.qualified_leads_generated == 5
        assert monitoring.current_metrics.system_health == "healthy"
    
    @pytest.mark.asyncio
    async def test_high_error_rate_alert(self, monitoring):
        """Test alert firing for high error rate."""
        # Set low threshold for testing
        monitoring.config.alerts.max_error_rate = 0.1
        
        test_metrics = {
            'total_runs': 10,
            'successful_runs': 5,
            'failed_runs': 5,
            'error_rate': 0.5,  # 50% error rate
            'qualified_leads': 3
        }
        
        await monitoring.update_metrics(test_metrics)
        
        # Check if alert was fired
        assert len(monitoring.active_alerts) > 0
        alert = list(monitoring.active_alerts.values())[0]
        assert alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]
        assert "error rate" in alert.title.lower()
    
    @pytest.mark.asyncio  
    async def test_low_qualified_leads_alert(self, monitoring):
        """Test alert firing for low qualified leads."""
        monitoring.config.alerts.min_qualified_leads = 5
        
        test_metrics = {
            'total_runs': 5,
            'successful_runs': 5,
            'failed_runs': 0,
            'error_rate': 0.0,
            'qualified_leads': 2  # Below threshold
        }
        
        await monitoring.update_metrics(test_metrics)
        
        # Check if alert was fired
        assert len(monitoring.active_alerts) > 0
        alert_found = any("qualified leads" in alert.title.lower() 
                         for alert in monitoring.active_alerts.values())
        assert alert_found
    
    def test_alert_resolution(self, monitoring):
        """Test alert resolution functionality."""
        # Create a test alert
        alert_id = "test_alert"
        monitoring.active_alerts[alert_id] = monitoring.Alert(
            id=alert_id,
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            timestamp=datetime.now(),
            source="test",
            metadata={}
        )
        
        assert len(monitoring.active_alerts) == 1
        
        # Resolve the alert
        monitoring.resolve_alert(alert_id)
        
        assert len(monitoring.active_alerts) == 0
    
    def test_performance_trend_analysis(self, monitoring):
        """Test performance trend calculation."""
        # Add some historical metrics
        base_time = datetime.now() - timedelta(hours=1)
        
        for i in range(5):
            metric = monitoring.MetricSnapshot(
                timestamp=base_time + timedelta(minutes=i * 10),
                total_runs=i + 1,
                successful_runs=i,
                failed_runs=1 if i > 0 else 0,
                error_rate=0.1 * i,
                avg_runtime_seconds=30 + i * 5,
                qualified_leads_generated=i * 2,
                active_tasks=1,
                system_health="healthy"
            )
            monitoring.metrics_history.append(metric)
        
        trend = monitoring.get_performance_trend(hours=2)
        
        assert trend["data_points"] == 5
        assert "error_rate_trend" in trend
        assert "runtime_trend" in trend
        assert trend["current_error_rate"] >= 0


class TestAutomatedLeadGenerator:
    """Test the main automation runner."""
    
    @pytest.mark.asyncio
    async def test_automation_initialization(self):
        """Test automation system initialization."""
        automation = AutomatedLeadGenerator()
        
        assert automation.scheduler is not None
        assert automation.monitoring is not None
        assert automation.orchestrator is not None
        assert automation.execution_count == 0
    
    def test_get_status(self):
        """Test status reporting."""
        automation = AutomatedLeadGenerator()
        status = automation.get_status()
        
        assert "is_running" in status
        assert "execution_count" in status
        assert "configuration" in status
        assert "system_health" in status
        
        config = status["configuration"]
        assert "environment" in config
        assert "schedule_enabled" in config
        assert "max_leads_per_run" in config
    
    @pytest.mark.asyncio
    async def test_schedule_expression_generation(self):
        """Test schedule expression generation."""
        automation = AutomatedLeadGenerator()
        
        # Test different schedule types
        automation.config.schedule.cron_expression = "0 10 * * *"
        expr = automation._get_schedule_expression()
        assert expr == "0 10 * * *"
        
        automation.config.schedule.cron_expression = None
        automation.config.schedule.schedule_type = ScheduleType.DAILY
        automation.config.schedule.run_time = automation.config.schedule.run_time.replace(hour=9, minute=30)
        expr = automation._get_schedule_expression()
        assert expr == "30 9 * * *"


@pytest.mark.asyncio
async def test_end_to_end_automation():
    """Test end-to-end automation workflow."""
    # Mock the orchestrator to avoid actual pipeline execution
    with patch('src.automation.runner.LeadGenerationOrchestrator') as mock_orchestrator_class:
        # Setup mock
        mock_orchestrator = Mock()
        mock_results = Mock()
        mock_results.total_qualified = 3
        mock_results.total_discovered = 10
        mock_results.success_rate = 0.3
        mock_results.duration_seconds = 45.0
        
        mock_orchestrator.run_full_pipeline = AsyncMock(return_value=mock_results)
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Create automation with test config
        automation = AutomatedLeadGenerator()
        automation.config.schedule.enabled = False  # Disable scheduling for test
        
        # Test pipeline execution
        await automation._execute_pipeline()
        
        # Verify execution
        assert automation.execution_count == 1
        assert automation.last_execution_time is not None
        mock_orchestrator.run_full_pipeline.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])