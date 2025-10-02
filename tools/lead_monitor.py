"""
Real-Time Lead Monitoring System
Continuous monitoring for acquisition signals and market changes.
"""

import os
import logging
import time
import asyncio
import schedule
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from requests_cache import CachedSession

logger = logging.getLogger(__name__)

@dataclass
class MonitoringAlert:
    business_name: str
    alert_type: str
    severity: str
    message: str
    evidence: List[str]
    detected_at: datetime
    source: str
    requires_action: bool

@dataclass
class MonitoringReport:
    monitoring_period: str
    total_alerts: int
    high_priority_alerts: int
    businesses_monitored: int
    alerts_by_type: Dict[str, int]
    recommended_actions: List[str]
    generated_at: datetime

class LeadMonitor:
    """Comprehensive lead monitoring system for real-time signal detection."""

    def __init__(self, db_path: str = "data/lead_monitoring.db"):
        self.db_path = db_path
        self.session = CachedSession(
            cache_name='monitoring_cache',
            expire_after=3600  # 1 hour cache for monitoring data
        )

        # Initialize database
        self._init_database()

        # Monitoring configuration
        self.monitoring_triggers = [
            'business_for_sale_listings',
            'owner_retirement_news',
            'financial_distress_signals',
            'competitor_acquisitions',
            'regulatory_changes',
            'property_sales',
            'key_personnel_changes',
            'market_disruptions'
        ]

        # Alert thresholds
        self.alert_thresholds = {
            'high': 0.8,    # 80% confidence triggers high priority
            'medium': 0.6,  # 60% confidence triggers medium priority
            'low': 0.4      # 40% confidence triggers low priority
        }

        # Monitoring intervals (in minutes)
        self.monitoring_intervals = {
            'high_priority_businesses': 60,     # Every hour
            'medium_priority_businesses': 240,   # Every 4 hours
            'low_priority_businesses': 1440,     # Daily
            'market_trends': 360,                # Every 6 hours
            'news_alerts': 120                   # Every 2 hours
        }

        # Search keywords for different alert types
        self.search_keywords = {
            'business_for_sale_listings': [
                'business for sale', 'selling business', 'business opportunity',
                'established business', 'turnkey operation', 'owner retiring'
            ],
            'owner_retirement_news': [
                'retirement', 'retiring', 'stepping down', 'succession',
                'next generation', 'family business transition'
            ],
            'financial_distress_signals': [
                'bankruptcy', 'receivership', 'financial difficulty',
                'debt restructuring', 'payment delays', 'cash flow problems'
            ],
            'competitor_acquisitions': [
                'acquisition', 'merger', 'bought by', 'acquired by',
                'consolidation', 'strategic purchase'
            ],
            'regulatory_changes': [
                'new regulation', 'regulatory change', 'compliance requirement',
                'industry standard', 'government policy', 'environmental regulation'
            ]
        }

        # Active monitoring flag and thread
        self.monitoring_active = False
        self.monitoring_thread = None
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Callback functions for alerts
        self.alert_callbacks: List[Callable[[MonitoringAlert], None]] = []

    def _init_database(self):
        """Initialize SQLite database for monitoring data."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    evidence TEXT,
                    source TEXT,
                    requires_action BOOLEAN,
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitored_businesses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL UNIQUE,
                    priority_level TEXT DEFAULT 'medium',
                    monitoring_keywords TEXT,
                    last_checked TIMESTAMP,
                    total_alerts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def add_business_to_monitoring(self, business: Dict[str, Any], priority: str = 'medium'):
        """Add a business to the monitoring system."""
        try:
            business_name = business.get('name', 'Unknown')

            # Generate monitoring keywords based on business info
            keywords = self._generate_monitoring_keywords(business)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO monitored_businesses
                    (business_name, priority_level, monitoring_keywords, last_checked)
                    VALUES (?, ?, ?, ?)
                """, (
                    business_name,
                    priority,
                    json.dumps(keywords),
                    datetime.now().isoformat()
                ))

            logger.info(f"Added {business_name} to monitoring with {priority} priority")

        except Exception as e:
            logger.error(f"Failed to add business to monitoring: {e}")

    def _generate_monitoring_keywords(self, business: Dict[str, Any]) -> List[str]:
        """Generate specific monitoring keywords for a business."""
        keywords = []

        business_name = business.get('name', '')
        if business_name:
            keywords.extend([
                business_name,
                f'"{business_name}"',  # Exact phrase search
                business_name.replace(' ', '+')  # For URL searches
            ])

        # Add owner names if available
        contacts = business.get('contacts', [])
        for contact in contacts:
            name = contact.get('name', '')
            title = contact.get('title', '').lower()
            if any(role in title for role in ['owner', 'president', 'ceo', 'founder']):
                keywords.append(name)

        # Add location-specific terms
        location = business.get('location', '')
        if location:
            keywords.append(f"{business_name} {location}")

        # Add industry-specific terms
        industry = business.get('industry', '')
        if industry:
            keywords.append(f"{business_name} {industry}")

        return list(set(keywords))  # Remove duplicates

    def monitor_business_listings(self, business_name: str, keywords: List[str]) -> List[MonitoringAlert]:
        """Monitor for business for sale listings."""
        alerts = []

        try:
            # Search business for sale websites
            listing_sites = [
                'bizbuysell.com',
                'businessbroker.net',
                'businessesforsale.com',
                'sunbeltnetwork.com'
            ]

            for site in listing_sites:
                try:
                    alerts.extend(self._search_business_listings(site, business_name, keywords))
                    time.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.warning(f"Failed to search {site}: {e}")

        except Exception as e:
            logger.error(f"Business listing monitoring failed for {business_name}: {e}")

        return alerts

    def monitor_news_mentions(self, business_name: str, keywords: List[str]) -> List[MonitoringAlert]:
        """Monitor news and media for business mentions."""
        alerts = []

        try:
            # Search news sources
            news_sources = self._search_news_sources(business_name, keywords)
            for article in news_sources:
                alert = self._analyze_news_article(business_name, article)
                if alert:
                    alerts.append(alert)

            # Search social media mentions
            social_mentions = self._search_social_media(business_name, keywords)
            for mention in social_mentions:
                alert = self._analyze_social_mention(business_name, mention)
                if alert:
                    alerts.append(alert)

        except Exception as e:
            logger.error(f"News monitoring failed for {business_name}: {e}")

        return alerts

    def monitor_financial_signals(self, business_name: str) -> List[MonitoringAlert]:
        """Monitor for financial distress signals."""
        alerts = []

        try:
            # Check court filings
            court_alerts = self._check_court_filings(business_name)
            alerts.extend(court_alerts)

            # Check lien filings
            lien_alerts = self._check_lien_filings(business_name)
            alerts.extend(lien_alerts)

            # Check credit reports (if available)
            credit_alerts = self._check_credit_changes(business_name)
            alerts.extend(credit_alerts)

        except Exception as e:
            logger.error(f"Financial signal monitoring failed for {business_name}: {e}")

        return alerts

    def monitor_competitor_activity(self, industry: str, location: str) -> List[MonitoringAlert]:
        """Monitor competitor acquisition activity."""
        alerts = []

        try:
            # Search for acquisition news in industry
            acquisition_news = self._search_acquisition_news(industry, location)
            for news in acquisition_news:
                alert = MonitoringAlert(
                    business_name=f"Industry: {industry}",
                    alert_type='competitor_acquisitions',
                    severity='medium',
                    message=f"Acquisition activity detected in {industry}",
                    evidence=[news.get('headline', 'Acquisition news detected')],
                    detected_at=datetime.now(),
                    source='news_search',
                    requires_action=False
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Competitor monitoring failed for {industry}: {e}")

        return alerts

    def monitor_regulatory_changes(self, industry: str) -> List[MonitoringAlert]:
        """Monitor for regulatory changes affecting industry."""
        alerts = []

        try:
            # Check government websites for regulatory updates
            regulatory_updates = self._check_regulatory_updates(industry)
            for update in regulatory_updates:
                alert = MonitoringAlert(
                    business_name=f"Industry: {industry}",
                    alert_type='regulatory_changes',
                    severity='low',
                    message=f"Regulatory change may affect {industry}",
                    evidence=[update.get('description', 'Regulatory update detected')],
                    detected_at=datetime.now(),
                    source='government_source',
                    requires_action=False
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Regulatory monitoring failed for {industry}: {e}")

        return alerts

    def continuous_monitoring(self):
        """Main continuous monitoring loop."""
        logger.info("Starting continuous monitoring")
        self.monitoring_active = True

        # Schedule different monitoring tasks
        schedule.every(self.monitoring_intervals['high_priority_businesses']).minutes.do(
            self._monitor_high_priority_businesses
        )
        schedule.every(self.monitoring_intervals['medium_priority_businesses']).minutes.do(
            self._monitor_medium_priority_businesses
        )
        schedule.every(self.monitoring_intervals['low_priority_businesses']).minutes.do(
            self._monitor_low_priority_businesses
        )
        schedule.every(self.monitoring_intervals['market_trends']).minutes.do(
            self._monitor_market_trends
        )
        schedule.every(self.monitoring_intervals['news_alerts']).minutes.do(
            self._monitor_news_alerts
        )

        # Main monitoring loop
        while self.monitoring_active:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

        logger.info("Continuous monitoring stopped")

    def start_monitoring(self):
        """Start monitoring in a separate thread."""
        if not self.monitoring_active:
            self.monitoring_thread = threading.Thread(target=self.continuous_monitoring)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            logger.info("Monitoring started in background thread")

    def stop_monitoring(self):
        """Stop continuous monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        logger.info("Monitoring stopped")

    def _monitor_high_priority_businesses(self):
        """Monitor high priority businesses."""
        businesses = self._get_businesses_by_priority('high')
        for business in businesses:
            self._monitor_single_business(business, priority='high')

    def _monitor_medium_priority_businesses(self):
        """Monitor medium priority businesses."""
        businesses = self._get_businesses_by_priority('medium')
        for business in businesses:
            self._monitor_single_business(business, priority='medium')

    def _monitor_low_priority_businesses(self):
        """Monitor low priority businesses."""
        businesses = self._get_businesses_by_priority('low')
        for business in businesses:
            self._monitor_single_business(business, priority='low')

    def _monitor_market_trends(self):
        """Monitor overall market trends."""
        logger.info("Monitoring market trends")
        # Implement market trend monitoring logic
        pass

    def _monitor_news_alerts(self):
        """Monitor general news alerts."""
        logger.info("Monitoring news alerts")
        # Implement general news monitoring logic
        pass

    def _monitor_single_business(self, business: Dict[str, Any], priority: str):
        """Monitor a single business for alerts."""
        try:
            business_name = business['business_name']
            keywords = json.loads(business.get('monitoring_keywords', '[]'))

            logger.debug(f"Monitoring {business_name} ({priority} priority)")

            all_alerts = []

            # Run monitoring checks in parallel
            futures = []
            futures.append(self.executor.submit(self.monitor_business_listings, business_name, keywords))
            futures.append(self.executor.submit(self.monitor_news_mentions, business_name, keywords))
            futures.append(self.executor.submit(self.monitor_financial_signals, business_name))

            # Collect results
            for future in futures:
                try:
                    alerts = future.result(timeout=30)
                    all_alerts.extend(alerts)
                except Exception as e:
                    logger.error(f"Monitoring task failed for {business_name}: {e}")

            # Process and store alerts
            for alert in all_alerts:
                self._process_alert(alert)

            # Update last checked timestamp
            self._update_last_checked(business_name)

        except Exception as e:
            logger.error(f"Failed to monitor {business_name}: {e}")

    def _process_alert(self, alert: MonitoringAlert):
        """Process and store a monitoring alert."""
        try:
            # Store alert in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO monitoring_alerts
                    (business_name, alert_type, severity, message, evidence,
                     source, requires_action)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.business_name,
                    alert.alert_type,
                    alert.severity,
                    alert.message,
                    json.dumps(alert.evidence),
                    alert.source,
                    alert.requires_action
                ))

            # Update business alert count
            conn.execute("""
                UPDATE monitored_businesses
                SET total_alerts = total_alerts + 1
                WHERE business_name = ?
            """, (alert.business_name,))

            # Trigger callbacks for high priority alerts
            if alert.severity == 'high':
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Alert callback failed: {e}")

            logger.info(f"Alert processed: {alert.alert_type} for {alert.business_name}")

        except Exception as e:
            logger.error(f"Failed to process alert: {e}")

    def add_alert_callback(self, callback: Callable[[MonitoringAlert], None]):
        """Add a callback function for alert notifications."""
        self.alert_callbacks.append(callback)

    def get_recent_alerts(self, hours: int = 24) -> List[MonitoringAlert]:
        """Get recent alerts from the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT business_name, alert_type, severity, message, evidence,
                           source, requires_action, created_at
                    FROM monitoring_alerts
                    WHERE created_at >= ? AND resolved = FALSE
                    ORDER BY created_at DESC
                """, (cutoff_time.isoformat(),))

                alerts = []
                for row in cursor.fetchall():
                    alert = MonitoringAlert(
                        business_name=row[0],
                        alert_type=row[1],
                        severity=row[2],
                        message=row[3],
                        evidence=json.loads(row[4] or '[]'),
                        detected_at=datetime.fromisoformat(row[7]),
                        source=row[5],
                        requires_action=bool(row[6])
                    )
                    alerts.append(alert)

                return alerts

        except Exception as e:
            logger.error(f"Failed to get recent alerts: {e}")
            return []

    def generate_monitoring_report(self, days: int = 7) -> MonitoringReport:
        """Generate a comprehensive monitoring report."""
        cutoff_time = datetime.now() - timedelta(days=days)

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get alert statistics
                cursor = conn.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high_priority,
                           alert_type
                    FROM monitoring_alerts
                    WHERE created_at >= ?
                    GROUP BY alert_type
                """, (cutoff_time.isoformat(),))

                alert_stats = cursor.fetchall()
                total_alerts = sum(row[0] for row in alert_stats)
                high_priority_alerts = sum(row[1] for row in alert_stats)
                alerts_by_type = {row[2]: row[0] for row in alert_stats}

                # Get monitored business count
                cursor = conn.execute("SELECT COUNT(*) FROM monitored_businesses")
                businesses_monitored = cursor.fetchone()[0]

                # Generate recommendations
                recommendations = self._generate_monitoring_recommendations(
                    total_alerts, high_priority_alerts, alerts_by_type
                )

                return MonitoringReport(
                    monitoring_period=f"Last {days} days",
                    total_alerts=total_alerts,
                    high_priority_alerts=high_priority_alerts,
                    businesses_monitored=businesses_monitored,
                    alerts_by_type=alerts_by_type,
                    recommended_actions=recommendations,
                    generated_at=datetime.now()
                )

        except Exception as e:
            logger.error(f"Failed to generate monitoring report: {e}")
            return MonitoringReport(
                monitoring_period=f"Last {days} days",
                total_alerts=0,
                high_priority_alerts=0,
                businesses_monitored=0,
                alerts_by_type={},
                recommended_actions=["Error generating report"],
                generated_at=datetime.now()
            )

    # Helper methods (simplified implementations)
    def _get_businesses_by_priority(self, priority: str) -> List[Dict[str, Any]]:
        """Get businesses by priority level."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT business_name, monitoring_keywords, last_checked
                    FROM monitored_businesses
                    WHERE priority_level = ?
                """, (priority,))

                return [
                    {
                        'business_name': row[0],
                        'monitoring_keywords': row[1],
                        'last_checked': row[2]
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to get businesses by priority: {e}")
            return []

    def _search_business_listings(self, site: str, business_name: str, keywords: List[str]) -> List[MonitoringAlert]:
        """Search business listing sites."""
        # Placeholder implementation
        return []

    def _search_news_sources(self, business_name: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search news sources for business mentions."""
        # Placeholder implementation
        return []

    def _analyze_news_article(self, business_name: str, article: Dict[str, Any]) -> Optional[MonitoringAlert]:
        """Analyze news article for relevant signals."""
        # Placeholder implementation
        return None

    def _search_social_media(self, business_name: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search social media for mentions."""
        # Placeholder implementation
        return []

    def _analyze_social_mention(self, business_name: str, mention: Dict[str, Any]) -> Optional[MonitoringAlert]:
        """Analyze social media mention."""
        # Placeholder implementation
        return None

    def _check_court_filings(self, business_name: str) -> List[MonitoringAlert]:
        """Check for new court filings."""
        # Placeholder implementation
        return []

    def _check_lien_filings(self, business_name: str) -> List[MonitoringAlert]:
        """Check for new lien filings."""
        # Placeholder implementation
        return []

    def _check_credit_changes(self, business_name: str) -> List[MonitoringAlert]:
        """Check for credit rating changes."""
        # Placeholder implementation
        return []

    def _search_acquisition_news(self, industry: str, location: str) -> List[Dict[str, Any]]:
        """Search for acquisition news in industry."""
        # Placeholder implementation
        return []

    def _check_regulatory_updates(self, industry: str) -> List[Dict[str, Any]]:
        """Check for regulatory updates."""
        # Placeholder implementation
        return []

    def _update_last_checked(self, business_name: str):
        """Update last checked timestamp for business."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE monitored_businesses
                    SET last_checked = ?
                    WHERE business_name = ?
                """, (datetime.now().isoformat(), business_name))
        except Exception as e:
            logger.error(f"Failed to update last checked: {e}")

    def _generate_monitoring_recommendations(self, total_alerts: int, high_priority: int,
                                           alerts_by_type: Dict[str, int]) -> List[str]:
        """Generate monitoring recommendations."""
        recommendations = []

        if high_priority > 5:
            recommendations.append("High alert volume detected - prioritize immediate review")

        if 'business_for_sale_listings' in alerts_by_type:
            recommendations.append("Business listing alerts require immediate follow-up")

        if 'financial_distress_signals' in alerts_by_type:
            recommendations.append("Financial distress detected - assess acquisition opportunity")

        if total_alerts == 0:
            recommendations.append("No alerts detected - consider expanding monitoring criteria")

        return recommendations

if __name__ == "__main__":
    # Test the monitoring system
    monitor = LeadMonitor()

    # Add a test business
    test_business = {
        'name': 'Test Manufacturing Inc.',
        'industry': 'Manufacturing',
        'location': 'Hamilton, ON',
        'contacts': [
            {
                'name': 'John Owner',
                'title': 'President',
                'email': 'john@testmfg.com'
            }
        ]
    }

    monitor.add_business_to_monitoring(test_business, priority='high')

    # Add alert callback
    def alert_handler(alert: MonitoringAlert):
        print(f"ALERT: {alert.severity.upper()} - {alert.message}")

    monitor.add_alert_callback(alert_handler)

    print("Monitoring system initialized")
    print("Use monitor.start_monitoring() to begin continuous monitoring")
    print("Use monitor.stop_monitoring() to stop")

    # Generate sample report
    report = monitor.generate_monitoring_report()
    print(f"\nMonitoring Report ({report.monitoring_period}):")
    print(f"Total Alerts: {report.total_alerts}")
    print(f"High Priority: {report.high_priority_alerts}")
    print(f"Businesses Monitored: {report.businesses_monitored}")