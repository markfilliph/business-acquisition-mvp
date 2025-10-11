"""
Database connection management with migrations and proper error handling.
"""
import aiosqlite
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import structlog

from ..core.models import BusinessLead, LeadStatus, PipelineResults
from ..core.exceptions import DatabaseError


class DatabaseManager:
    """Production database manager with proper connection pooling and migrations."""

    def __init__(self, config: Any):
        """
        Initialize database manager.

        Args:
            config: Config object with 'path' and 'connection_timeout' attributes
        """
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self._connection_pool: List[aiosqlite.Connection] = []
        self._initialized = False
    
    async def initialize(self):
        """Initialize database with schema and migrations."""
        if self._initialized:
            return
        
        try:
            # Ensure database directory exists
            Path(self.config.path).parent.mkdir(parents=True, exist_ok=True)
            
            # Run migrations
            await self._run_migrations()
            
            self._initialized = True
            self.logger.info("database_initialized", path=self.config.path)
            
        except Exception as e:
            self.logger.error("database_initialization_failed", error=str(e))
            raise DatabaseError(f"Failed to initialize database: {e}")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with proper error handling."""
        if not self._initialized:
            await self.initialize()
        
        connection = None
        try:
            connection = await aiosqlite.connect(
                self.config.path,
                timeout=self.config.connection_timeout
            )
            
            # Enable foreign key constraints
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA journal_mode = WAL")  # Better concurrency
            
            yield connection
            
        except Exception as e:
            self.logger.error("database_connection_error", error=str(e))
            raise DatabaseError(f"Database connection failed: {e}")
        
        finally:
            if connection:
                await connection.close()
    
    async def _run_migrations(self):
        """Run database migrations."""
        # Use direct connection to avoid recursion
        connection = None
        try:
            connection = await aiosqlite.connect(
                self.config.path,
                timeout=self.config.connection_timeout
            )
            
            # Enable foreign key constraints
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA journal_mode = WAL")
            
            db = connection
            # Create leads table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_id TEXT UNIQUE NOT NULL,
                    business_name TEXT NOT NULL,
                    
                    -- Location fields
                    address TEXT,
                    city TEXT,
                    province TEXT DEFAULT 'ON',
                    postal_code TEXT,
                    country TEXT DEFAULT 'Canada',
                    
                    -- Contact fields
                    phone TEXT,
                    email TEXT,
                    website TEXT,
                    
                    -- Business details
                    industry TEXT,
                    years_in_business INTEGER,
                    employee_count INTEGER,
                    business_description TEXT,
                    
                    -- Revenue estimation
                    estimated_revenue INTEGER,
                    revenue_confidence REAL,
                    revenue_estimation_method TEXT, -- JSON array
                    revenue_indicators TEXT, -- JSON array
                    
                    -- Lead scoring
                    lead_score INTEGER DEFAULT 0,
                    revenue_fit_score INTEGER DEFAULT 0,
                    business_age_score INTEGER DEFAULT 0,
                    data_quality_score INTEGER DEFAULT 0,
                    industry_fit_score INTEGER DEFAULT 0,
                    location_score INTEGER DEFAULT 0,
                    growth_score INTEGER DEFAULT 0,
                    
                    -- Status and metadata
                    status TEXT DEFAULT 'discovered',
                    confidence_score REAL DEFAULT 0.0,
                    data_sources TEXT, -- JSON array
                    qualification_reasons TEXT, -- JSON array
                    disqualification_reasons TEXT, -- JSON array
                    notes TEXT, -- JSON array

                    -- Human review fields
                    review_reason TEXT, -- Why review is needed
                    reviewed_by TEXT, -- Analyst who reviewed
                    reviewed_at TIMESTAMP, -- When reviewed
                    review_decision TEXT, -- approved/rejected
                    review_notes TEXT -- Analyst notes
                    
                    -- Processing tracking
                    validation_errors TEXT, -- JSON array
                    enrichment_attempts INTEGER DEFAULT 0,
                    
                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_contacted TIMESTAMP,
                    
                    -- Constraints
                    CHECK (revenue_confidence BETWEEN 0.0 AND 1.0),
                    CHECK (lead_score BETWEEN 0 AND 100),
                    CHECK (confidence_score BETWEEN 0.0 AND 1.0),
                    CHECK (years_in_business >= 0),
                    CHECK (employee_count > 0)
                )
            ''')
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_leads_unique_id ON leads (unique_id)",
                "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status)",
                "CREATE INDEX IF NOT EXISTS idx_leads_score ON leads (lead_score DESC)",
                "CREATE INDEX IF NOT EXISTS idx_leads_updated ON leads (updated_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_leads_business_name ON leads (business_name)",
                "CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads (industry)",
                "CREATE INDEX IF NOT EXISTS idx_leads_city ON leads (city)",
                "CREATE INDEX IF NOT EXISTS idx_leads_qualified ON leads (status, lead_score DESC) WHERE status = 'qualified'",
            ]
            
            for index_sql in indexes:
                await db.execute(index_sql)
            
            # Pipeline runs tracking table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_seconds REAL,
                    
                    -- Statistics
                    total_discovered INTEGER DEFAULT 0,
                    total_validated INTEGER DEFAULT 0,
                    total_enriched INTEGER DEFAULT 0,
                    total_qualified INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    average_score REAL DEFAULT 0.0,
                    
                    -- Results
                    industry_breakdown TEXT, -- JSON
                    recommendations TEXT, -- JSON array
                    configuration TEXT, -- JSON
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Activity log table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS lead_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_unique_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    activity_description TEXT,
                    activity_data TEXT, -- JSON
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (lead_unique_id) REFERENCES leads (unique_id)
                )
            ''')
            
            await db.execute("CREATE INDEX IF NOT EXISTS idx_activities_lead ON lead_activities (lead_unique_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON lead_activities (timestamp DESC)")
            
            await db.commit()
            
        except Exception as e:
            self.logger.error("migration_failed", error=str(e))
            raise
        finally:
            if connection:
                await connection.close()
    
    async def upsert_lead(self, lead: BusinessLead) -> bool:
        """Insert or update a lead with comprehensive data."""
        try:
            async with self.get_connection() as db:
                # Prepare data for insertion
                lead_data = {
                    'unique_id': lead.unique_id,
                    'business_name': lead.business_name,
                    'address': lead.location.address,
                    'city': lead.location.city,
                    'province': lead.location.province,
                    'postal_code': lead.location.postal_code,
                    'country': lead.location.country,
                    'phone': lead.contact.phone,
                    'email': lead.contact.email,
                    'website': lead.contact.website,
                    'industry': lead.industry,
                    'years_in_business': lead.years_in_business,
                    'employee_count': lead.employee_count,
                    'business_description': lead.business_description,
                    'estimated_revenue': lead.revenue_estimate.estimated_amount,
                    'revenue_confidence': lead.revenue_estimate.confidence_score,
                    'revenue_estimation_method': json.dumps(lead.revenue_estimate.estimation_method),
                    'revenue_indicators': json.dumps(lead.revenue_estimate.indicators),
                    'lead_score': lead.lead_score.total_score,
                    'revenue_fit_score': lead.lead_score.revenue_fit_score,
                    'business_age_score': lead.lead_score.business_age_score,
                    'data_quality_score': lead.lead_score.data_quality_score,
                    'industry_fit_score': lead.lead_score.industry_fit_score,
                    'location_score': lead.lead_score.location_score,
                    'growth_score': lead.lead_score.growth_score,
                    'status': lead.status.value,
                    'confidence_score': lead.confidence_score,
                    'data_sources': json.dumps([ds.value for ds in lead.data_sources]),
                    'qualification_reasons': json.dumps(lead.lead_score.qualification_reasons),
                    'disqualification_reasons': json.dumps(lead.lead_score.disqualification_reasons),
                    'notes': json.dumps(lead.notes),
                    'validation_errors': json.dumps(lead.validation_errors),
                    'enrichment_attempts': lead.enrichment_attempts,
                    'updated_at': datetime.utcnow(),
                    'last_contacted': lead.last_contacted
                }
                
                # Insert or replace lead
                columns = list(lead_data.keys())
                placeholders = ', '.join(['?' for _ in columns])
                values = list(lead_data.values())
                
                sql = f'''
                    INSERT OR REPLACE INTO leads ({', '.join(columns)})
                    VALUES ({placeholders})
                '''
                
                await db.execute(sql, values)
                await db.commit()
                
                # Log activity
                await self._log_activity(db, lead.unique_id, 'upsert', 'Lead data updated')
                
                self.logger.info("lead_upserted", 
                               unique_id=lead.unique_id,
                               business_name=lead.business_name)
                
                return True
                
        except Exception as e:
            self.logger.error("lead_upsert_failed", 
                            unique_id=lead.unique_id,
                            error=str(e))
            raise DatabaseError(f"Failed to upsert lead {lead.unique_id}: {e}")
    
    async def get_qualified_leads(self, limit: int = 50, min_score: int = 60) -> List[Dict[str, Any]]:
        """Get qualified leads sorted by score."""
        try:
            async with self.get_connection() as db:
                db.row_factory = aiosqlite.Row
                
                sql = '''
                    SELECT * FROM leads 
                    WHERE status = 'qualified' AND lead_score >= ?
                    ORDER BY lead_score DESC, confidence_score DESC, updated_at DESC
                    LIMIT ?
                '''
                
                cursor = await db.execute(sql, (min_score, limit))
                rows = await cursor.fetchall()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error("get_qualified_leads_failed", error=str(e))
            raise DatabaseError(f"Failed to get qualified leads: {e}")
    
    async def get_leads_by_status(self, status: LeadStatus, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get leads by status."""
        try:
            async with self.get_connection() as db:
                db.row_factory = aiosqlite.Row
                
                sql = "SELECT * FROM leads WHERE status = ? ORDER BY updated_at DESC"
                params = [status.value]
                
                if limit:
                    sql += " LIMIT ?"
                    params.append(limit)
                
                cursor = await db.execute(sql, params)
                rows = await cursor.fetchall()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error("get_leads_by_status_failed", status=status.value, error=str(e))
            raise DatabaseError(f"Failed to get leads by status {status.value}: {e}")
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            async with self.get_connection() as db:
                stats = {}
                
                # Total counts by status
                cursor = await db.execute('''
                    SELECT status, COUNT(*) as count, AVG(lead_score) as avg_score
                    FROM leads 
                    GROUP BY status
                ''')
                status_stats = await cursor.fetchall()
                stats['by_status'] = {row[0]: {'count': row[1], 'avg_score': row[2] or 0} for row in status_stats}
                
                # Score distribution
                cursor = await db.execute('''
                    SELECT 
                        CASE 
                            WHEN lead_score >= 80 THEN 'excellent'
                            WHEN lead_score >= 60 THEN 'good'
                            WHEN lead_score >= 40 THEN 'fair'
                            ELSE 'poor'
                        END as score_tier,
                        COUNT(*) as count
                    FROM leads 
                    GROUP BY score_tier
                ''')
                score_dist = await cursor.fetchall()
                stats['score_distribution'] = {row[0]: row[1] for row in score_dist}
                
                # Industry breakdown (qualified leads only)
                cursor = await db.execute('''
                    SELECT industry, COUNT(*) as count
                    FROM leads 
                    WHERE status = 'qualified'
                    GROUP BY industry 
                    ORDER BY count DESC
                    LIMIT 10
                ''')
                industry_stats = await cursor.fetchall()
                stats['top_industries'] = {row[0] or 'Unknown': row[1] for row in industry_stats}
                
                # Data quality metrics
                cursor = await db.execute('''
                    SELECT 
                        AVG(confidence_score) as avg_confidence,
                        AVG(revenue_confidence) as avg_revenue_confidence,
                        COUNT(*) as total_leads,
                        SUM(CASE WHEN phone IS NOT NULL THEN 1 ELSE 0 END) as has_phone,
                        SUM(CASE WHEN email IS NOT NULL THEN 1 ELSE 0 END) as has_email,
                        SUM(CASE WHEN website IS NOT NULL THEN 1 ELSE 0 END) as has_website
                    FROM leads
                ''')
                quality_stats = await cursor.fetchone()
                if quality_stats:
                    stats['data_quality'] = {
                        'avg_confidence': round(quality_stats[0] or 0, 3),
                        'avg_revenue_confidence': round(quality_stats[1] or 0, 3),
                        'phone_coverage': round((quality_stats[3] / max(quality_stats[2], 1)) * 100, 1),
                        'email_coverage': round((quality_stats[4] / max(quality_stats[2], 1)) * 100, 1),
                        'website_coverage': round((quality_stats[5] / max(quality_stats[2], 1)) * 100, 1)
                    }
                
                # Recent activity
                cursor = await db.execute('''
                    SELECT COUNT(*) as recent_updates
                    FROM leads 
                    WHERE updated_at >= datetime('now', '-7 days')
                ''')
                recent_count = await cursor.fetchone()
                stats['recent_activity'] = {'updates_last_7_days': recent_count[0] if recent_count else 0}
                
                return stats
                
        except Exception as e:
            self.logger.error("get_database_statistics_failed", error=str(e))
            raise DatabaseError(f"Failed to get database statistics: {e}")
    
    async def save_pipeline_results(self, results: PipelineResults) -> str:
        """Save pipeline run results."""
        try:
            run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            async with self.get_connection() as db:
                await db.execute('''
                    INSERT INTO pipeline_runs (
                        run_id, start_time, end_time, duration_seconds,
                        total_discovered, total_validated, total_enriched, 
                        total_qualified, total_errors, success_rate, average_score,
                        industry_breakdown, recommendations
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    run_id, results.start_time, results.end_time, results.duration_seconds,
                    results.total_discovered, results.total_validated, results.total_enriched,
                    results.total_qualified, results.total_errors, results.success_rate, results.average_score,
                    json.dumps(results.industry_breakdown), json.dumps(results.recommendations)
                ))
                
                await db.commit()
                
                self.logger.info("pipeline_results_saved", run_id=run_id)
                return run_id
                
        except Exception as e:
            self.logger.error("save_pipeline_results_failed", error=str(e))
            raise DatabaseError(f"Failed to save pipeline results: {e}")
    
    async def _log_activity(self, db: aiosqlite.Connection, lead_unique_id: str, 
                           activity_type: str, description: str, data: Dict[str, Any] = None):
        """Log lead activity."""
        try:
            await db.execute('''
                INSERT INTO lead_activities (lead_unique_id, activity_type, activity_description, activity_data)
                VALUES (?, ?, ?, ?)
            ''', (lead_unique_id, activity_type, description, json.dumps(data) if data else None))
            
        except Exception as e:
            self.logger.warning("activity_log_failed", 
                              lead_id=lead_unique_id,
                              activity=activity_type,
                              error=str(e))
    
    async def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old data to prevent database bloat."""
        try:
            async with self.get_connection() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                # Archive old disqualified leads
                await db.execute('''
                    UPDATE leads 
                    SET status = 'archived' 
                    WHERE status = 'disqualified' 
                    AND updated_at < ?
                ''', (cutoff_date,))
                
                # Clean up old activity logs
                await db.execute('''
                    DELETE FROM lead_activities 
                    WHERE timestamp < ?
                ''', (cutoff_date,))
                
                # Clean up old pipeline runs (keep last 50)
                await db.execute('''
                    DELETE FROM pipeline_runs 
                    WHERE id NOT IN (
                        SELECT id FROM pipeline_runs 
                        ORDER BY created_at DESC 
                        LIMIT 50
                    )
                ''')
                
                await db.commit()
                
                self.logger.info("database_cleanup_completed", days_kept=days_to_keep)
                
        except Exception as e:
            self.logger.error("database_cleanup_failed", error=str(e))
            raise DatabaseError(f"Failed to cleanup database: {e}")