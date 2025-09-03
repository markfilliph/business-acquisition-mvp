"""
Main pipeline orchestrator that coordinates all lead generation stages.
"""
import asyncio
from datetime import datetime
from typing import List, Optional

import structlog

from ..core.config import SystemConfig
from ..core.models import BusinessLead, PipelineResults, LeadStatus
from ..database.connection import DatabaseManager
from ..services.discovery_service import EthicalDiscoveryService
from ..services.enrichment_service import BusinessEnrichmentService
from ..services.scoring_service import IntelligentScoringService


class LeadGenerationOrchestrator:
    """Coordinates the entire lead generation pipeline."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        
        # Initialize services
        self.db_manager = DatabaseManager(config.database)
        self.discovery_service = EthicalDiscoveryService(config)
        self.enrichment_service = BusinessEnrichmentService(config)
        self.scoring_service = IntelligentScoringService(config)
        
        # Pipeline state
        self.results = PipelineResults()
    
    async def run_full_pipeline(self, target_leads: int = 50) -> PipelineResults:
        """Execute the complete lead generation pipeline."""
        
        self.logger.info("pipeline_started", target_leads=target_leads)
        self.results = PipelineResults(start_time=datetime.utcnow())
        
        try:
            # Initialize database
            await self.db_manager.initialize()
            
            # Stage 1: Discovery
            self.logger.info("stage_1_discovery_starting")
            discovered_leads = await self.discovery_service.discover_businesses(target_leads)
            self.results.total_discovered = len(discovered_leads)
            
            if not discovered_leads:
                self.logger.warning("no_leads_discovered")
                self.results.recommendations.append("No businesses discovered - check data sources")
                self.results.finalize()
                return self.results
            
            # Stage 2: Validation and enrichment
            self.logger.info("stage_2_enrichment_starting", count=len(discovered_leads))
            enriched_leads = await self.enrichment_service.enrich_leads(discovered_leads)
            
            # Filter out error leads
            valid_leads = [lead for lead in enriched_leads if lead.status != LeadStatus.ERROR]
            self.results.total_enriched = len(valid_leads)
            self.results.total_errors = len(enriched_leads) - len(valid_leads)
            
            if not valid_leads:
                self.logger.warning("no_leads_after_enrichment")
                self.results.recommendations.append("All leads failed enrichment - check data quality")
                self.results.finalize()
                return self.results
            
            # Stage 3: Scoring and qualification
            self.logger.info("stage_3_scoring_starting", count=len(valid_leads))
            scored_leads = await self.scoring_service.score_leads(valid_leads)
            
            # Separate qualified leads
            qualified_leads = [
                lead for lead in scored_leads 
                if lead.status == LeadStatus.QUALIFIED
            ]
            
            self.results.total_qualified = len(qualified_leads)
            self.results.qualified_leads = qualified_leads
            
            # Stage 4: Database persistence
            self.logger.info("stage_4_persistence_starting", count=len(scored_leads))
            await self._persist_leads(scored_leads)
            
            # Stage 5: Generate insights and recommendations
            await self._generate_insights()
            
            # Finalize results
            self.results.finalize()
            
            # Save pipeline run to database
            run_id = await self.db_manager.save_pipeline_results(self.results)
            
            self.logger.info("pipeline_completed", 
                           run_id=run_id,
                           qualified=self.results.total_qualified,
                           success_rate=f"{self.results.success_rate:.1%}")
            
            return self.results
            
        except Exception as e:
            self.logger.error("pipeline_failed", error=str(e))
            self.results.recommendations.append(f"Pipeline failed: {str(e)}")
            self.results.finalize()
            raise
    
    async def _persist_leads(self, leads: List[BusinessLead]) -> None:
        """Persist all leads to database."""
        
        success_count = 0
        
        for lead in leads:
            try:
                await self.db_manager.upsert_lead(lead)
                success_count += 1
            except Exception as e:
                self.logger.error("lead_persistence_failed", 
                                business_name=lead.business_name,
                                error=str(e))
        
        self.logger.info("leads_persisted", 
                        success=success_count,
                        total=len(leads))
    
    async def _generate_insights(self) -> None:
        """Generate insights and recommendations based on pipeline results."""
        
        recommendations = []
        
        # Success rate analysis
        if self.results.success_rate < 0.1:  # Less than 10% qualified
            recommendations.append("Very low qualification rate - consider relaxing criteria or improving data sources")
        elif self.results.success_rate < 0.2:  # Less than 20% qualified
            recommendations.append("Low qualification rate - review scoring weights or target criteria")
        elif self.results.success_rate > 0.5:  # More than 50% qualified
            recommendations.append("High qualification rate - consider tightening criteria for better focus")
        
        # Data quality analysis
        if self.results.total_errors > self.results.total_enriched * 0.3:  # More than 30% errors
            recommendations.append("High error rate during enrichment - check data source quality")
        
        # Industry insights
        if self.results.industry_breakdown:
            top_industry = max(self.results.industry_breakdown, key=self.results.industry_breakdown.get)
            recommendations.append(f"Focus recruitment on {top_industry} - highest qualification rate")
        
        # Volume recommendations
        if self.results.total_qualified < 5:
            recommendations.append("Low qualified lead count - consider expanding search criteria or geographic area")
        elif self.results.total_qualified > 20:
            recommendations.append("Good lead volume - prioritize by score for contact sequence")
        
        # Scoring insights
        if self.results.average_score < 50:
            recommendations.append("Low average scores - review target market alignment or scoring algorithm")
        
        self.results.recommendations = recommendations
    
    async def get_qualified_leads(self, limit: Optional[int] = None) -> List[BusinessLead]:
        """Get qualified leads from database."""
        
        try:
            leads_data = await self.db_manager.get_qualified_leads(
                limit=limit or 50,
                min_score=self.config.scoring.qualification_threshold
            )
            
            # Convert to BusinessLead objects (simplified for this example)
            leads = []
            for lead_data in leads_data:
                # In practice, you'd convert the database row back to BusinessLead
                # This is a simplified representation
                self.logger.info("qualified_lead_found", 
                               business_name=lead_data.get('business_name'),
                               score=lead_data.get('lead_score'))
            
            return leads
            
        except Exception as e:
            self.logger.error("get_qualified_leads_failed", error=str(e))
            return []
    
    async def get_pipeline_statistics(self) -> dict:
        """Get comprehensive pipeline statistics."""
        
        try:
            db_stats = await self.db_manager.get_database_statistics()
            
            # Combine with service statistics
            discovery_stats = self.discovery_service.get_discovery_stats()
            enrichment_stats = self.enrichment_service.get_enrichment_stats()
            scoring_stats = self.scoring_service.get_scoring_stats()
            
            return {
                "database": db_stats,
                "discovery": discovery_stats,
                "enrichment": enrichment_stats,
                "scoring": scoring_stats,
                "last_run": self.results.to_dict() if self.results.end_time else None
            }
            
        except Exception as e:
            self.logger.error("get_statistics_failed", error=str(e))
            return {}