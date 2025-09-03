"""
Main automation runner that integrates scheduling, monitoring, and pipeline execution.
"""
import asyncio
import sys
from datetime import datetime
from typing import Optional

import structlog

from .config import automation_config
from .scheduler import AutomationScheduler
from .monitoring import MonitoringService
from ..core.config import config
from ..agents.orchestrator import LeadGenerationOrchestrator
from ..core.exceptions import AutomationError


class AutomatedLeadGenerator:
    """
    Production automation system for lead generation.
    
    Integrates:
    - Scheduled pipeline execution
    - Real-time monitoring and alerting  
    - Error recovery and circuit breaking
    - Performance tracking and optimization
    """
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        
        # Initialize components
        self.scheduler = AutomationScheduler(automation_config)
        self.monitoring = MonitoringService(automation_config)
        self.orchestrator = LeadGenerationOrchestrator(config)
        
        # Execution state
        self.is_running = False
        self.last_execution_time: Optional[datetime] = None
        self.execution_count = 0
        
    async def start(self):
        """Start the automated lead generation system."""
        try:
            self.logger.info("automation_starting",
                           environment=automation_config.environment,
                           max_leads_per_run=automation_config.schedule.max_leads_per_run,
                           schedule_enabled=automation_config.schedule.enabled)
            
            # Register the main pipeline task
            if automation_config.schedule.enabled:
                self.scheduler.add_task(
                    task_id="lead_generation_pipeline",
                    name="Automated Lead Generation Pipeline",
                    function=self._execute_pipeline,
                    schedule=self._get_schedule_expression(),
                    enabled=True
                )
                
                # Add monitoring task
                self.scheduler.add_task(
                    task_id="system_monitoring",
                    name="System Health Monitoring",
                    function=self._update_monitoring,
                    schedule="*/5 * * * *",  # Every 5 minutes
                    enabled=True
                )
            
            # Start the scheduler
            self.is_running = True
            await self.scheduler.start()
            
        except Exception as e:
            self.logger.error("automation_start_failed", error=str(e))
            raise AutomationError(f"Failed to start automation: {e}")
    
    def _get_schedule_expression(self) -> str:
        """Get cron expression based on configuration."""
        schedule = automation_config.schedule
        
        if schedule.cron_expression:
            return schedule.cron_expression
        elif schedule.schedule_type.value == "daily":
            return f"{schedule.run_time.minute} {schedule.run_time.hour} * * *"
        elif schedule.schedule_type.value == "hourly":
            return f"0 * * * *"  # Top of every hour
        elif schedule.schedule_type.value == "weekly":
            return f"{schedule.run_time.minute} {schedule.run_time.hour} * * 1"  # Monday
        else:
            return "0 9 * * *"  # Default: 9 AM daily
    
    async def _execute_pipeline(self):
        """Execute the lead generation pipeline with monitoring."""
        execution_start = datetime.now()
        self.execution_count += 1
        
        self.logger.info("pipeline_execution_starting",
                        execution_count=self.execution_count,
                        max_leads=automation_config.schedule.max_leads_per_run)
        
        try:
            # Execute the pipeline
            results = await self.orchestrator.run_full_pipeline(
                target_leads=automation_config.schedule.max_leads_per_run
            )
            
            # Update execution tracking
            self.last_execution_time = execution_start
            execution_time = (datetime.now() - execution_start).total_seconds()
            
            # Log results
            self.logger.info("pipeline_execution_completed",
                           execution_count=self.execution_count,
                           qualified_leads=results.total_qualified,
                           total_discovered=results.total_discovered,
                           success_rate=results.success_rate,
                           execution_time_seconds=execution_time)
            
            # Export results if configured
            if automation_config.export_results:
                await self._export_results(results)
            
            # Fire success alert if significant results
            if results.total_qualified > automation_config.alerts.min_qualified_leads:
                await self.monitoring._fire_alert(
                    id="pipeline_success",
                    title="Pipeline Execution Successful",
                    message=f"Generated {results.total_qualified} qualified leads in {execution_time:.1f}s",
                    severity=self.monitoring.AlertSeverity.INFO,
                    source="pipeline",
                    metadata={
                        "qualified_leads": results.total_qualified,
                        "total_discovered": results.total_discovered,
                        "execution_time": execution_time
                    }
                )
            
        except Exception as e:
            execution_time = (datetime.now() - execution_start).total_seconds()
            
            self.logger.error("pipeline_execution_failed",
                            execution_count=self.execution_count,
                            error=str(e),
                            execution_time_seconds=execution_time)
            
            # Fire error alert
            await self.monitoring._fire_alert(
                id="pipeline_failure",
                title="Pipeline Execution Failed",
                message=f"Pipeline failed after {execution_time:.1f}s: {str(e)[:200]}",
                severity=self.monitoring.AlertSeverity.ERROR,
                source="pipeline",
                metadata={
                    "error": str(e),
                    "execution_time": execution_time,
                    "execution_count": self.execution_count
                }
            )
            
            raise  # Re-raise for scheduler error handling
    
    async def _update_monitoring(self):
        """Update monitoring metrics and check system health."""
        try:
            # Get scheduler statistics
            scheduler_stats = self.scheduler.get_stats()
            
            # Get pipeline results from database
            pipeline_stats = await self._get_pipeline_stats()
            
            # Combine metrics
            combined_metrics = {
                **scheduler_stats,
                **pipeline_stats,
                "last_execution_time": self.last_execution_time.isoformat() if self.last_execution_time else None,
                "execution_count": self.execution_count,
                "automation_uptime_hours": self._get_uptime_hours()
            }
            
            # Update monitoring
            await self.monitoring.update_metrics(combined_metrics)
            
        except Exception as e:
            self.logger.error("monitoring_update_failed", error=str(e))
    
    async def _get_pipeline_stats(self) -> dict:
        """Get pipeline statistics from database."""
        try:
            # Get recent qualified leads count
            async with self.orchestrator.db_manager.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) FROM leads 
                    WHERE status = 'qualified' 
                    AND created_at > datetime('now', '-24 hours')
                """)
                recent_qualified = (await cursor.fetchone())[0]
                
                cursor = await conn.execute("""
                    SELECT COUNT(*) FROM leads 
                    WHERE created_at > datetime('now', '-24 hours')
                """)
                recent_total = (await cursor.fetchone())[0]
            
            return {
                "qualified_leads": recent_qualified,
                "total_leads_24h": recent_total,
                "qualification_rate": recent_qualified / max(1, recent_total)
            }
            
        except Exception as e:
            self.logger.error("pipeline_stats_failed", error=str(e))
            return {"qualified_leads": 0, "total_leads_24h": 0, "qualification_rate": 0.0}
    
    def _get_uptime_hours(self) -> float:
        """Get automation uptime in hours."""
        if not hasattr(self, '_start_time'):
            self._start_time = datetime.now()
        
        return (datetime.now() - self._start_time).total_seconds() / 3600
    
    async def _export_results(self, results):
        """Export pipeline results to configured formats."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for format_type in automation_config.export_formats:
                if format_type == "csv":
                    # Export CSV using existing export script
                    from ..scripts.export_detailed_leads import export_qualified_leads
                    await export_qualified_leads()
                    
                elif format_type == "json":
                    # JSON export is included in the detailed export
                    pass
                    
            self.logger.info("results_exported", 
                           formats=automation_config.export_formats,
                           qualified_leads=results.total_qualified)
            
        except Exception as e:
            self.logger.error("results_export_failed", error=str(e))
    
    async def stop(self):
        """Stop the automation system gracefully."""
        self.logger.info("automation_stopping")
        self.is_running = False
        await self.scheduler.shutdown()
        self.logger.info("automation_stopped")
    
    def get_status(self) -> dict:
        """Get current automation status."""
        return {
            "is_running": self.is_running,
            "execution_count": self.execution_count,
            "last_execution": self.last_execution_time.isoformat() if self.last_execution_time else None,
            "uptime_hours": self._get_uptime_hours(),
            "scheduler_stats": self.scheduler.get_stats(),
            "active_alerts": len(self.monitoring.get_active_alerts()),
            "system_health": self.monitoring.current_metrics.system_health,
            "configuration": {
                "environment": automation_config.environment,
                "schedule_enabled": automation_config.schedule.enabled,
                "max_leads_per_run": automation_config.schedule.max_leads_per_run,
                "alert_channels": [ch.value for ch in automation_config.alerts.channels]
            }
        }


async def main():
    """Main entry point for automation system."""
    
    # Setup logging
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger(__name__)
    
    # Create and start automation
    automation = AutomatedLeadGenerator()
    
    try:
        await automation.start()
    except KeyboardInterrupt:
        logger.info("shutdown_requested")
        await automation.stop()
    except Exception as e:
        logger.error("automation_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())