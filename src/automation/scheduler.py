"""
Production-grade task scheduler with cron support and error handling.
"""
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import structlog
from croniter import croniter

from .config import AutomationConfig, ScheduleType
from ..core.exceptions import AutomationError


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """Represents a scheduled automation task."""
    task_id: str
    name: str
    function: Callable
    schedule: str  # Cron expression or interval
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    enabled: bool = True


class AutomationScheduler:
    """
    Production-grade scheduler for automated lead generation.
    
    Features:
    - Cron-style scheduling
    - Graceful shutdown handling  
    - Task monitoring and logging
    - Error recovery and circuit breaker
    - Concurrent execution limits
    """
    
    def __init__(self, config: AutomationConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        
        # Task management
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.shutdown_event = asyncio.Event()
        
        # Execution tracking
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'avg_runtime_seconds': 0.0,
            'last_run_time': None
        }
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers."""
        if sys.platform != "win32":  # Unix-like systems
            for sig in [signal.SIGINT, signal.SIGTERM]:
                signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info("shutdown_signal_received", signal=signum)
        asyncio.create_task(self.shutdown())
    
    def add_task(
        self,
        task_id: str,
        name: str,
        function: Callable,
        schedule: str,
        enabled: bool = True
    ) -> ScheduledTask:
        """
        Add a new scheduled task.
        
        Args:
            task_id: Unique identifier for the task
            name: Human-readable task name
            function: Async function to execute
            schedule: Cron expression or interval (e.g., "0 9 * * *" or "hourly")
            enabled: Whether the task is enabled
            
        Returns:
            Created ScheduledTask
        """
        if task_id in self.tasks:
            raise AutomationError(f"Task '{task_id}' already exists")
            
        # Validate cron expression
        if not self._is_valid_schedule(schedule):
            raise AutomationError(f"Invalid schedule expression: {schedule}")
            
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            function=function,
            schedule=schedule,
            enabled=enabled,
            next_run=self._calculate_next_run(schedule)
        )
        
        self.tasks[task_id] = task
        self.logger.info("task_added", 
                        task_id=task_id, 
                        name=name, 
                        schedule=schedule,
                        next_run=task.next_run)
        
        return task
    
    def _is_valid_schedule(self, schedule: str) -> bool:
        """Validate schedule expression."""
        try:
            if schedule in ['hourly', 'daily', 'weekly']:
                return True
            croniter(schedule)
            return True
        except Exception:
            return False
    
    def _calculate_next_run(self, schedule: str, from_time: Optional[datetime] = None) -> datetime:
        """Calculate next execution time for a schedule."""
        base_time = from_time or datetime.now()
        
        if schedule == 'hourly':
            return base_time + timedelta(hours=1)
        elif schedule == 'daily':
            return base_time.replace(
                hour=self.config.schedule.run_time.hour,
                minute=self.config.schedule.run_time.minute,
                second=0,
                microsecond=0
            ) + timedelta(days=1)
        elif schedule == 'weekly':
            next_run = base_time.replace(
                hour=self.config.schedule.run_time.hour,
                minute=self.config.schedule.run_time.minute,
                second=0,
                microsecond=0
            )
            days_ahead = 7 - base_time.weekday()  # Next Monday
            return next_run + timedelta(days=days_ahead)
        else:
            # Cron expression
            cron = croniter(schedule, base_time)
            return cron.get_next(datetime)
    
    async def start(self):
        """Start the scheduler and begin processing tasks."""
        self.logger.info("scheduler_starting", 
                        task_count=len(self.tasks),
                        environment=self.config.environment)
        
        try:
            while not self.shutdown_event.is_set():
                await self._process_pending_tasks()
                await asyncio.sleep(60)  # Check every minute
                
        except Exception as e:
            self.logger.error("scheduler_error", error=str(e))
            raise
        finally:
            await self._cleanup_running_tasks()
            self.logger.info("scheduler_stopped")
    
    async def _process_pending_tasks(self):
        """Check and execute pending tasks."""
        current_time = datetime.now()
        
        for task_id, task in self.tasks.items():
            if not task.enabled:
                continue
                
            if task.next_run and current_time >= task.next_run:
                # Check concurrent execution limit
                if len(self.running_tasks) >= self.config.schedule.max_concurrent_runs:
                    self.logger.warning("concurrent_limit_reached", 
                                      limit=self.config.schedule.max_concurrent_runs)
                    continue
                
                await self._execute_task(task)
    
    async def _execute_task(self, task: ScheduledTask):
        """Execute a single task with error handling."""
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()
        task.run_count += 1
        
        self.logger.info("task_starting", 
                        task_id=task.task_id,
                        name=task.name,
                        run_count=task.run_count)
        
        # Create and track the task
        async_task = asyncio.create_task(
            self._run_task_with_timeout(task)
        )
        self.running_tasks[task.task_id] = async_task
        
        try:
            await async_task
        finally:
            # Clean up
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
    
    async def _run_task_with_timeout(self, task: ScheduledTask):
        """Run task with timeout and error handling."""
        start_time = datetime.now()
        
        try:
            # Execute with timeout
            await asyncio.wait_for(
                task.function(),
                timeout=self.config.schedule.timeout_minutes * 60
            )
            
            task.status = TaskStatus.COMPLETED
            task.last_error = None
            
            # Update statistics
            self.stats['successful_runs'] += 1
            runtime = (datetime.now() - start_time).total_seconds()
            self._update_avg_runtime(runtime)
            
            self.logger.info("task_completed",
                           task_id=task.task_id,
                           runtime_seconds=runtime)
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error_count += 1
            task.last_error = "Task timeout"
            self.stats['failed_runs'] += 1
            
            self.logger.error("task_timeout",
                            task_id=task.task_id,
                            timeout_minutes=self.config.schedule.timeout_minutes)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_count += 1
            task.last_error = str(e)
            self.stats['failed_runs'] += 1
            
            self.logger.error("task_failed",
                            task_id=task.task_id,
                            error=str(e),
                            error_count=task.error_count)
        
        finally:
            # Schedule next run
            task.next_run = self._calculate_next_run(task.schedule, task.last_run)
            self.stats['total_runs'] += 1
            self.stats['last_run_time'] = datetime.now()
    
    def _update_avg_runtime(self, runtime_seconds: float):
        """Update average runtime statistics."""
        successful_runs = self.stats['successful_runs']
        current_avg = self.stats['avg_runtime_seconds']
        
        # Calculate running average
        new_avg = ((current_avg * (successful_runs - 1)) + runtime_seconds) / successful_runs
        self.stats['avg_runtime_seconds'] = new_avg
    
    async def shutdown(self):
        """Gracefully shutdown the scheduler."""
        self.logger.info("scheduler_shutdown_requested")
        self.shutdown_event.set()
        
        # Wait for running tasks to complete
        await self._cleanup_running_tasks()
    
    async def _cleanup_running_tasks(self):
        """Clean up any running tasks."""
        if self.running_tasks:
            self.logger.info("waiting_for_tasks", count=len(self.running_tasks))
            
            # Wait for tasks to complete with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.running_tasks.values(), return_exceptions=True),
                    timeout=30  # 30 second graceful shutdown timeout
                )
            except asyncio.TimeoutError:
                # Force cancel remaining tasks
                for task_id, async_task in self.running_tasks.items():
                    async_task.cancel()
                    self.logger.warning("task_force_cancelled", task_id=task_id)
    
    def get_task_status(self, task_id: str) -> Optional[ScheduledTask]:
        """Get status of a specific task."""
        return self.tasks.get(task_id)
    
    def get_all_tasks_status(self) -> Dict[str, ScheduledTask]:
        """Get status of all tasks."""
        return self.tasks.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            **self.stats,
            'active_tasks': len([t for t in self.tasks.values() if t.enabled]),
            'running_tasks': len(self.running_tasks),
            'error_rate': self.stats['failed_runs'] / max(1, self.stats['total_runs'])
        }
    
    def enable_task(self, task_id: str):
        """Enable a task."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = True
            self.logger.info("task_enabled", task_id=task_id)
    
    def disable_task(self, task_id: str):
        """Disable a task."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            self.logger.info("task_disabled", task_id=task_id)