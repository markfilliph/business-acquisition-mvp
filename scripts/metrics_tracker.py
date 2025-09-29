"""
Lead Quality Metrics and Performance Tracking System
Comprehensive analytics for lead generation and validation performance.
"""

import os
import logging
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class MetricsSummary:
    period: str
    verification_rate: float
    false_positive_rate: float
    data_completeness: float
    source_reliability: Dict[str, float]
    conversion_to_meeting: float
    time_to_validate: float
    total_leads_processed: int
    hot_leads_generated: int
    successful_contacts: int
    generated_at: datetime

@dataclass
class PerformanceTrend:
    metric_name: str
    time_series: List[Tuple[datetime, float]]
    trend_direction: str
    improvement_percentage: float
    recommendations: List[str]

class LeadQualityMetrics:
    """Comprehensive metrics tracking for lead generation performance."""

    def __init__(self, db_path: str = "data/metrics_tracking.db"):
        self.db_path = db_path

        # Initialize database
        self._init_database()

        # Metrics definitions
        self.metric_definitions = {
            'verification_rate': 'Percentage of leads successfully verified',
            'false_positive_rate': 'Percentage of hot leads that were incorrect',
            'data_completeness': 'Percentage of complete data fields',
            'source_reliability': 'Accuracy rate by data source',
            'conversion_to_meeting': 'Percentage of hot leads that resulted in meetings',
            'time_to_validate': 'Average time to complete validation process',
            'contact_success_rate': 'Percentage of valid contact information',
            'revenue_accuracy': 'Accuracy of revenue estimates vs actual',
            'priority_accuracy': 'Accuracy of priority scoring vs outcomes'
        }

        # Benchmark targets
        self.benchmark_targets = {
            'verification_rate': 0.85,         # 85% target
            'false_positive_rate': 0.15,      # <15% target
            'data_completeness': 0.90,        # 90% target
            'conversion_to_meeting': 0.25,    # 25% target
            'time_to_validate': 3600,         # <1 hour target (seconds)
            'contact_success_rate': 0.80,     # 80% target
            'revenue_accuracy': 0.75,         # 75% target
            'priority_accuracy': 0.70         # 70% target
        }

    def _init_database(self):
        """Initialize SQLite database for metrics tracking."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Metrics snapshots table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    verification_rate REAL,
                    false_positive_rate REAL,
                    data_completeness REAL,
                    source_reliability TEXT,
                    conversion_to_meeting REAL,
                    time_to_validate REAL,
                    total_leads_processed INTEGER,
                    hot_leads_generated INTEGER,
                    successful_contacts INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Lead performance tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    validation_start_time TEXT,
                    validation_end_time TEXT,
                    verification_successful BOOLEAN,
                    data_fields_complete INTEGER,
                    data_fields_total INTEGER,
                    marked_as_hot BOOLEAN,
                    actual_outcome TEXT,
                    contact_successful BOOLEAN,
                    meeting_scheduled BOOLEAN,
                    revenue_estimate REAL,
                    revenue_actual REAL,
                    priority_score REAL,
                    data_sources TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Source performance tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    total_requests INTEGER DEFAULT 0,
                    successful_requests INTEGER DEFAULT 0,
                    accurate_results INTEGER DEFAULT 0,
                    total_results INTEGER DEFAULT 0,
                    average_response_time REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def track_lead_validation(self, business_name: str, validation_data: Dict[str, Any]):
        """Track metrics for a lead validation process."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO lead_performance
                    (business_name, validation_start_time, validation_end_time,
                     verification_successful, data_fields_complete, data_fields_total,
                     marked_as_hot, contact_successful, revenue_estimate,
                     priority_score, data_sources)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    business_name,
                    validation_data.get('start_time', datetime.now().isoformat()),
                    validation_data.get('end_time', datetime.now().isoformat()),
                    validation_data.get('verification_successful', False),
                    validation_data.get('data_fields_complete', 0),
                    validation_data.get('data_fields_total', 1),
                    validation_data.get('marked_as_hot', False),
                    validation_data.get('contact_successful', False),
                    validation_data.get('revenue_estimate', 0),
                    validation_data.get('priority_score', 0),
                    json.dumps(validation_data.get('data_sources', []))
                ))

            logger.info(f"Tracked validation metrics for {business_name}")

        except Exception as e:
            logger.error(f"Failed to track lead validation: {e}")

    def track_source_performance(self, source_name: str, data_type: str,
                                request_successful: bool, result_accurate: bool = None,
                                response_time: float = None):
        """Track performance metrics for data sources."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get existing record or create new one
                cursor = conn.execute("""
                    SELECT total_requests, successful_requests, accurate_results,
                           total_results, average_response_time
                    FROM source_performance
                    WHERE source_name = ? AND data_type = ?
                """, (source_name, data_type))

                existing = cursor.fetchone()

                if existing:
                    total_requests = existing[0] + 1
                    successful_requests = existing[1] + (1 if request_successful else 0)
                    accurate_results = existing[2] + (1 if result_accurate else 0)
                    total_results = existing[3] + (1 if result_accurate is not None else 0)

                    # Update average response time
                    if response_time and existing[4]:
                        avg_time = (existing[4] * (total_requests - 1) + response_time) / total_requests
                    else:
                        avg_time = response_time or existing[4]

                    conn.execute("""
                        UPDATE source_performance
                        SET total_requests = ?, successful_requests = ?,
                            accurate_results = ?, total_results = ?,
                            average_response_time = ?, last_updated = ?
                        WHERE source_name = ? AND data_type = ?
                    """, (
                        total_requests, successful_requests, accurate_results,
                        total_results, avg_time, datetime.now().isoformat(),
                        source_name, data_type
                    ))
                else:
                    conn.execute("""
                        INSERT INTO source_performance
                        (source_name, data_type, total_requests, successful_requests,
                         accurate_results, total_results, average_response_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        source_name, data_type, 1, 1 if request_successful else 0,
                        1 if result_accurate else 0, 1 if result_accurate is not None else 0,
                        response_time
                    ))

        except Exception as e:
            logger.error(f"Failed to track source performance: {e}")

    def update_lead_outcome(self, business_name: str, outcome_data: Dict[str, Any]):
        """Update lead record with actual outcome data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE lead_performance
                    SET actual_outcome = ?, meeting_scheduled = ?, revenue_actual = ?
                    WHERE business_name = ? AND actual_outcome IS NULL
                """, (
                    outcome_data.get('outcome', 'unknown'),
                    outcome_data.get('meeting_scheduled', False),
                    outcome_data.get('revenue_actual'),
                    business_name
                ))

            logger.info(f"Updated outcome for {business_name}")

        except Exception as e:
            logger.error(f"Failed to update lead outcome: {e}")

    def calculate_metrics(self, days: int = 30) -> MetricsSummary:
        """Calculate comprehensive metrics for specified time period."""
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get lead performance data
                df = pd.read_sql_query("""
                    SELECT * FROM lead_performance
                    WHERE created_at >= ?
                """, conn, params=(cutoff_date.isoformat(),))

                if len(df) == 0:
                    return self._empty_metrics_summary(days)

                # Calculate verification rate
                verified_leads = len(df[df['verification_successful'] == True])
                total_leads = len(df)
                verification_rate = verified_leads / total_leads if total_leads > 0 else 0

                # Calculate false positive rate
                hot_leads = df[df['marked_as_hot'] == True]
                if len(hot_leads) > 0:
                    false_positives = len(hot_leads[
                        (hot_leads['actual_outcome'].isin(['rejected', 'not_interested', 'invalid'])) |
                        (hot_leads['meeting_scheduled'] == False)
                    ])
                    false_positive_rate = false_positives / len(hot_leads)
                else:
                    false_positive_rate = 0

                # Calculate data completeness
                total_fields = df['data_fields_total'].sum()
                complete_fields = df['data_fields_complete'].sum()
                data_completeness = complete_fields / total_fields if total_fields > 0 else 0

                # Calculate source reliability
                source_reliability = self._calculate_source_reliability()

                # Calculate conversion to meeting
                hot_leads_count = len(hot_leads)
                meetings_scheduled = len(df[df['meeting_scheduled'] == True])
                conversion_to_meeting = meetings_scheduled / hot_leads_count if hot_leads_count > 0 else 0

                # Calculate average validation time
                df['validation_duration'] = pd.to_datetime(df['validation_end_time']) - pd.to_datetime(df['validation_start_time'])
                avg_validation_time = df['validation_duration'].dt.total_seconds().mean()

                # Count successful contacts
                successful_contacts = len(df[df['contact_successful'] == True])

                return MetricsSummary(
                    period=f"Last {days} days",
                    verification_rate=verification_rate,
                    false_positive_rate=false_positive_rate,
                    data_completeness=data_completeness,
                    source_reliability=source_reliability,
                    conversion_to_meeting=conversion_to_meeting,
                    time_to_validate=avg_validation_time,
                    total_leads_processed=total_leads,
                    hot_leads_generated=hot_leads_count,
                    successful_contacts=successful_contacts,
                    generated_at=datetime.now()
                )

        except Exception as e:
            logger.error(f"Failed to calculate metrics: {e}")
            return self._empty_metrics_summary(days)

    def _calculate_source_reliability(self) -> Dict[str, float]:
        """Calculate reliability metrics for each data source."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT source_name, data_type, successful_requests, total_requests,
                           accurate_results, total_results
                    FROM source_performance
                """)

                source_reliability = {}
                for row in cursor.fetchall():
                    source_name, data_type, successful, total, accurate, total_results = row

                    # Calculate success rate
                    success_rate = successful / total if total > 0 else 0

                    # Calculate accuracy rate
                    accuracy_rate = accurate / total_results if total_results > 0 else 0

                    # Combined reliability score
                    reliability = (success_rate * 0.6) + (accuracy_rate * 0.4)

                    source_key = f"{source_name}_{data_type}"
                    source_reliability[source_key] = reliability

                return source_reliability

        except Exception as e:
            logger.error(f"Failed to calculate source reliability: {e}")
            return {}

    def _empty_metrics_summary(self, days: int) -> MetricsSummary:
        """Return empty metrics summary when no data available."""
        return MetricsSummary(
            period=f"Last {days} days",
            verification_rate=0.0,
            false_positive_rate=0.0,
            data_completeness=0.0,
            source_reliability={},
            conversion_to_meeting=0.0,
            time_to_validate=0.0,
            total_leads_processed=0,
            hot_leads_generated=0,
            successful_contacts=0,
            generated_at=datetime.now()
        )

    def store_metrics_snapshot(self, metrics: MetricsSummary):
        """Store a metrics snapshot for historical tracking."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO metrics_snapshots
                    (snapshot_date, verification_rate, false_positive_rate,
                     data_completeness, source_reliability, conversion_to_meeting,
                     time_to_validate, total_leads_processed, hot_leads_generated,
                     successful_contacts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().date().isoformat(),
                    metrics.verification_rate,
                    metrics.false_positive_rate,
                    metrics.data_completeness,
                    json.dumps(metrics.source_reliability),
                    metrics.conversion_to_meeting,
                    metrics.time_to_validate,
                    metrics.total_leads_processed,
                    metrics.hot_leads_generated,
                    metrics.successful_contacts
                ))

            logger.info("Metrics snapshot stored")

        except Exception as e:
            logger.error(f"Failed to store metrics snapshot: {e}")

    def get_performance_trends(self, days: int = 90) -> List[PerformanceTrend]:
        """Analyze performance trends over time."""
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query("""
                    SELECT snapshot_date, verification_rate, false_positive_rate,
                           data_completeness, conversion_to_meeting, time_to_validate
                    FROM metrics_snapshots
                    WHERE snapshot_date >= ?
                    ORDER BY snapshot_date
                """, conn, params=(cutoff_date.date().isoformat(),))

                trends = []

                if len(df) >= 2:
                    for metric in ['verification_rate', 'false_positive_rate',
                                 'data_completeness', 'conversion_to_meeting']:
                        trend = self._calculate_trend(df, metric)
                        trends.append(trend)

                return trends

        except Exception as e:
            logger.error(f"Failed to calculate performance trends: {e}")
            return []

    def _calculate_trend(self, df: pd.DataFrame, metric_name: str) -> PerformanceTrend:
        """Calculate trend for a specific metric."""
        try:
            df['date'] = pd.to_datetime(df['snapshot_date'])
            time_series = list(zip(df['date'], df[metric_name]))

            # Calculate trend direction
            if len(df) >= 2:
                first_half = df[metric_name][:len(df)//2].mean()
                second_half = df[metric_name][len(df)//2:].mean()

                if second_half > first_half * 1.05:  # 5% improvement
                    trend_direction = "improving"
                    improvement = ((second_half - first_half) / first_half) * 100
                elif second_half < first_half * 0.95:  # 5% decline
                    trend_direction = "declining"
                    improvement = ((second_half - first_half) / first_half) * 100
                else:
                    trend_direction = "stable"
                    improvement = 0
            else:
                trend_direction = "insufficient_data"
                improvement = 0

            # Generate recommendations
            recommendations = self._generate_metric_recommendations(metric_name, trend_direction, df[metric_name].iloc[-1])

            return PerformanceTrend(
                metric_name=metric_name,
                time_series=time_series,
                trend_direction=trend_direction,
                improvement_percentage=improvement,
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Failed to calculate trend for {metric_name}: {e}")
            return PerformanceTrend(
                metric_name=metric_name,
                time_series=[],
                trend_direction="error",
                improvement_percentage=0,
                recommendations=["Error calculating trend"]
            )

    def _generate_metric_recommendations(self, metric_name: str, trend: str, current_value: float) -> List[str]:
        """Generate recommendations based on metric performance."""
        recommendations = []
        target = self.benchmark_targets.get(metric_name, 0.5)

        if metric_name == 'verification_rate':
            if current_value < target:
                recommendations.append("Improve data source quality and validation processes")
            if trend == "declining":
                recommendations.append("Review recent changes to validation criteria")

        elif metric_name == 'false_positive_rate':
            if current_value > target:
                recommendations.append("Tighten lead qualification criteria")
            if trend == "improving":  # Lower false positive rate is better
                recommendations.append("Continue current validation improvements")

        elif metric_name == 'data_completeness':
            if current_value < target:
                recommendations.append("Enhance data enrichment processes")
            if trend == "declining":
                recommendations.append("Review data source reliability")

        elif metric_name == 'conversion_to_meeting':
            if current_value < target:
                recommendations.append("Improve lead scoring and prioritization")
            if trend == "declining":
                recommendations.append("Review outreach messaging and timing")

        return recommendations

    def get_source_performance_report(self) -> Dict[str, Any]:
        """Generate detailed source performance report."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query("""
                    SELECT source_name, data_type, total_requests, successful_requests,
                           accurate_results, total_results, average_response_time
                    FROM source_performance
                """, conn)

                if len(df) == 0:
                    return {"sources": [], "summary": "No source data available"}

                # Calculate performance metrics for each source
                source_metrics = []
                for _, row in df.iterrows():
                    success_rate = row['successful_requests'] / row['total_requests'] if row['total_requests'] > 0 else 0
                    accuracy_rate = row['accurate_results'] / row['total_results'] if row['total_results'] > 0 else 0

                    source_metrics.append({
                        'source': f"{row['source_name']} ({row['data_type']})",
                        'success_rate': success_rate,
                        'accuracy_rate': accuracy_rate,
                        'total_requests': row['total_requests'],
                        'avg_response_time': row['average_response_time'],
                        'reliability_score': (success_rate * 0.6) + (accuracy_rate * 0.4)
                    })

                # Sort by reliability score
                source_metrics.sort(key=lambda x: x['reliability_score'], reverse=True)

                return {
                    "sources": source_metrics,
                    "top_performer": source_metrics[0] if source_metrics else None,
                    "needs_improvement": [s for s in source_metrics if s['reliability_score'] < 0.7]
                }

        except Exception as e:
            logger.error(f"Failed to generate source performance report: {e}")
            return {"sources": [], "summary": f"Error: {e}"}

    def generate_performance_dashboard_data(self) -> Dict[str, Any]:
        """Generate comprehensive data for performance dashboard."""
        try:
            current_metrics = self.calculate_metrics(30)
            trends = self.get_performance_trends(90)
            source_report = self.get_source_performance_report()

            # Compare to benchmarks
            benchmark_comparison = {}
            for metric, target in self.benchmark_targets.items():
                current_value = getattr(current_metrics, metric, 0)
                if metric == 'false_positive_rate':  # Lower is better
                    performance = "above_target" if current_value <= target else "below_target"
                else:  # Higher is better
                    performance = "above_target" if current_value >= target else "below_target"

                benchmark_comparison[metric] = {
                    'current': current_value,
                    'target': target,
                    'performance': performance,
                    'gap': abs(current_value - target)
                }

            return {
                'current_metrics': current_metrics,
                'trends': trends,
                'source_performance': source_report,
                'benchmark_comparison': benchmark_comparison,
                'generated_at': datetime.now()
            }

        except Exception as e:
            logger.error(f"Failed to generate dashboard data: {e}")
            return {'error': str(e)}

# Convenience function for easy metrics tracking
def track_validation_metrics(business_name: str, start_time: datetime, end_time: datetime,
                           success: bool, data_complete: int, data_total: int,
                           hot_lead: bool, contact_success: bool, revenue_est: float,
                           priority: float, sources: List[str]):
    """Convenience function to track validation metrics."""
    tracker = LeadQualityMetrics()
    validation_data = {
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'verification_successful': success,
        'data_fields_complete': data_complete,
        'data_fields_total': data_total,
        'marked_as_hot': hot_lead,
        'contact_successful': contact_success,
        'revenue_estimate': revenue_est,
        'priority_score': priority,
        'data_sources': sources
    }
    tracker.track_lead_validation(business_name, validation_data)

if __name__ == "__main__":
    # Test the metrics system
    tracker = LeadQualityMetrics()

    # Track sample validation
    sample_validation = {
        'start_time': (datetime.now() - timedelta(minutes=15)).isoformat(),
        'end_time': datetime.now().isoformat(),
        'verification_successful': True,
        'data_fields_complete': 8,
        'data_fields_total': 10,
        'marked_as_hot': True,
        'contact_successful': True,
        'revenue_estimate': 1200000,
        'priority_score': 85.5,
        'data_sources': ['clearbit', 'hunter', 'linkedin']
    }

    tracker.track_lead_validation("Test Business Inc.", sample_validation)

    # Track source performance
    tracker.track_source_performance("clearbit", "revenue", True, True, 2.3)
    tracker.track_source_performance("hunter", "email", True, True, 1.8)

    # Calculate metrics
    metrics = tracker.calculate_metrics(30)

    print(f"Metrics Summary (Last 30 days):")
    print(f"Verification Rate: {metrics.verification_rate:.2%}")
    print(f"False Positive Rate: {metrics.false_positive_rate:.2%}")
    print(f"Data Completeness: {metrics.data_completeness:.2%}")
    print(f"Conversion to Meeting: {metrics.conversion_to_meeting:.2%}")
    print(f"Total Leads Processed: {metrics.total_leads_processed}")
    print(f"Hot Leads Generated: {metrics.hot_leads_generated}")
    print(f"Successful Contacts: {metrics.successful_contacts}")

    # Store snapshot
    tracker.store_metrics_snapshot(metrics)

    print("\nMetrics tracking system initialized and tested successfully")