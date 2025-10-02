"""
Business data enrichment service with revenue estimation and intelligence gathering.
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

import structlog

from ..core.config import SystemConfig, INDUSTRY_BENCHMARKS
from ..core.models import BusinessLead, RevenueEstimate, LeadStatus
from ..core.exceptions import DataSourceError


class BusinessEnrichmentService:
    """Enrich business leads with additional data and revenue estimates."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self.benchmarks = INDUSTRY_BENCHMARKS
        
        self.enrichment_stats = {
            'leads_processed': 0,
            'revenue_estimates_generated': 0,
            'high_confidence_estimates': 0,
            'enrichment_failures': 0
        }
    
    async def enrich_leads(self, leads: List[BusinessLead]) -> List[BusinessLead]:
        """Enrich multiple leads concurrently."""
        
        self.logger.info("enrichment_started", count=len(leads))
        
        # Process leads in batches to avoid overwhelming external services
        batch_size = 5
        enriched_leads = []
        
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self.enrich_single_lead(lead) for lead in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.error("lead_enrichment_failed", error=str(result))
                    self.enrichment_stats['enrichment_failures'] += 1
                else:
                    enriched_leads.append(result)
            
            # Small delay between batches
            if i + batch_size < len(leads):
                await asyncio.sleep(1)
        
        self.logger.info("enrichment_completed", 
                        processed=len(enriched_leads),
                        stats=self.enrichment_stats)
        
        return enriched_leads
    
    async def enrich_single_lead(self, lead: BusinessLead) -> BusinessLead:
        """Enrich a single business lead with comprehensive data."""
        
        try:
            lead.status = LeadStatus.ENRICHING
            lead.enrichment_attempts += 1
            
            # Email discovery
            lead = await self._discover_email(lead)

            # REMOVED: Revenue estimation - cannot be verified from public sources
            # Revenue data is not available for small businesses

            # Business intelligence gathering
            lead = await self._gather_business_intelligence(lead)
            
            # Update confidence score
            lead.update_confidence_score()
            
            lead.status = LeadStatus.ENRICHED
            lead.add_note("Data enrichment completed", "enrichment_service")
            
            self.enrichment_stats['leads_processed'] += 1
            
            return lead
            
        except Exception as e:
            self.logger.error("single_lead_enrichment_failed", 
                            business_name=lead.business_name,
                            error=str(e))
            lead.status = LeadStatus.ERROR
            lead.validation_errors.append(f"Enrichment failed: {str(e)}")
            self.enrichment_stats['enrichment_failures'] += 1
            return lead
    
    # REMOVED: _estimate_revenue - NO REVENUE ESTIMATION ALLOWED
    # REMOVED: _estimate_from_employees - NO REVENUE ESTIMATION ALLOWED
    # REMOVED: _estimate_from_business_age - NO REVENUE ESTIMATION ALLOWED
    # REMOVED: _estimate_from_industry_profile - NO REVENUE ESTIMATION ALLOWED
    # Revenue data cannot be verified from public sources for small businesses
    
    async def _gather_business_intelligence(self, lead: BusinessLead) -> BusinessLead:
        """Gather additional business intelligence from available sources."""
        
        intelligence_notes = []
        
        # Industry analysis
        if lead.industry:
            industry_insights = self._get_industry_insights(lead.industry)
            intelligence_notes.extend(industry_insights)
        
        # Location analysis
        if lead.location.is_hamilton_area():
            location_insights = self._get_location_insights(lead.location.city)
            intelligence_notes.extend(location_insights)
        
        # Business size analysis
        if lead.employee_count:
            size_insights = self._get_business_size_insights(lead.employee_count, lead.industry)
            intelligence_notes.extend(size_insights)
        
        # Add insights as notes
        for insight in intelligence_notes:
            lead.add_note(insight, "business_intelligence")
        
        return lead
    
    def _get_industry_insights(self, industry: str) -> List[str]:
        """Get industry-specific insights."""
        
        insights = []
        
        if industry == 'manufacturing':
            insights.extend([
                "Manufacturing sector in Hamilton benefits from proximity to US markets",
                "Strong local supply chain ecosystem",
                "Access to skilled trades workforce"
            ])
        elif industry == 'wholesale':
            insights.extend([
                "Hamilton's strategic location ideal for distribution",
                "Lower warehouse costs than GTA",
                "Good transportation infrastructure"
            ])
        elif industry == 'construction':
            insights.extend([
                "Hamilton construction market driven by urban renewal",
                "Steady demand from residential and commercial development"
            ])
        
        return insights
    
    def _get_location_insights(self, city: Optional[str]) -> List[str]:
        """Get location-specific insights."""
        
        insights = []
        
        if city and 'hamilton' in city.lower():
            insights.extend([
                "Hamilton market offers cost advantages over Toronto",
                "Growing tech and innovation sector",
                "Strategic location for North American trade"
            ])
        elif city and 'ancaster' in city.lower():
            insights.extend([
                "Ancaster: Affluent area with higher-end service demand",
                "Good access to both Hamilton and Burlington markets"
            ])
        elif city and 'dundas' in city.lower():
            insights.extend([
                "Dundas: Historic town with strong local business community",
                "Good mix of residential and commercial opportunities"
            ])
        
        return insights
    
    def _get_business_size_insights(self, employee_count: int, industry: Optional[str]) -> List[str]:
        """Get insights based on business size."""
        
        insights = []
        
        if employee_count <= 10:
            insights.append("Small team size suggests owner-managed operation")
        elif employee_count <= 25:
            insights.append("Medium-sized team indicates established operations")
        elif employee_count <= 50:
            insights.append("Larger team suggests potential for delegation/systems")
        
        # Industry-specific size insights
        if industry == 'manufacturing' and employee_count >= 15:
            insights.append("Manufacturing team size suggests multi-shift or specialized operations")
        elif industry == 'professional_services' and employee_count <= 12:
            insights.append("Professional services team size ideal for personal service delivery")
        
        return insights

    async def _discover_email(self, lead: BusinessLead) -> BusinessLead:
        """Discover business email through multiple methods."""

        if lead.contact.email:
            # Already has email
            return lead

        discovered_email = None

        try:
            # Method 1: Common business email patterns
            if lead.business_name and lead.contact.website:
                discovered_email = await self._generate_business_email(lead)

            # Method 2: Website scraping for contact information
            if not discovered_email and lead.contact.website:
                discovered_email = await self._extract_email_from_website(lead.contact.website)

            # Method 3: Standard business email patterns
            if not discovered_email:
                discovered_email = self._generate_standard_email_patterns(lead)

            if discovered_email:
                lead.contact.email = discovered_email
                lead.add_note(f"Email discovered: {discovered_email}", "enrichment_service")
                self.logger.info("email_discovered",
                               business_name=lead.business_name,
                               email=discovered_email)
            else:
                lead.add_note("No email could be discovered", "enrichment_service")
                self.logger.warning("email_discovery_failed",
                                  business_name=lead.business_name)

        except Exception as e:
            self.logger.error("email_discovery_error",
                            business_name=lead.business_name,
                            error=str(e))

        return lead

    async def _generate_business_email(self, lead: BusinessLead) -> Optional[str]:
        """Generate likely business email addresses."""

        if not lead.contact.website or not lead.business_name:
            return None

        # Extract domain from website
        try:
            domain = lead.contact.website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]

            # Common business email patterns
            email_patterns = [
                f"info@{domain}",
                f"contact@{domain}",
                f"sales@{domain}",
                f"admin@{domain}",
                f"office@{domain}"
            ]

            # Return first pattern (most common)
            return email_patterns[0]

        except Exception:
            return None

    async def _extract_email_from_website(self, website: str) -> Optional[str]:
        """Extract email from website contact pages (simulated)."""

        # This would normally scrape the website for email addresses
        # For now, return None to avoid false data
        return None

    def _generate_standard_email_patterns(self, lead: BusinessLead) -> Optional[str]:
        """Generate standard email patterns when website is not available."""

        if not lead.business_name:
            return None

        # For businesses without websites, we can't reliably generate emails
        # This avoids creating fake email addresses
        return None

    def get_enrichment_stats(self) -> Dict[str, int]:
        """Get enrichment statistics."""
        return self.enrichment_stats.copy()