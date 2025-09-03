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
            
            # Revenue estimation
            lead = await self._estimate_revenue(lead)
            
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
    
    async def _estimate_revenue(self, lead: BusinessLead) -> BusinessLead:
        """Estimate business revenue using multiple methodologies."""
        
        revenue_estimates = []
        confidence_factors = []
        estimation_methods = []
        indicators = []
        
        # Method 1: Employee-based estimation
        if lead.employee_count and lead.industry:
            employee_estimate, employee_confidence = self._estimate_from_employees(lead)
            if employee_estimate:
                revenue_estimates.append(employee_estimate)
                confidence_factors.append(employee_confidence)
                estimation_methods.append("employee_count")
                indicators.append(f"Employee count ({lead.employee_count}) analysis")
        
        # Method 2: Industry and age-based estimation
        if lead.industry and lead.years_in_business:
            age_estimate, age_confidence = self._estimate_from_business_age(lead)
            if age_estimate:
                revenue_estimates.append(age_estimate)
                confidence_factors.append(age_confidence)
                estimation_methods.append("business_maturity")
                indicators.append(f"Business maturity ({lead.years_in_business} years) analysis")
        
        # Method 3: Location-based adjustment
        if lead.location.is_hamilton_area():
            location_factor = 0.85  # Hamilton has lower operating costs than Toronto
            indicators.append("Hamilton market adjustment applied")
        
        # Method 4: Industry-specific indicators
        if lead.industry and lead.industry in self.benchmarks:
            industry_estimate, industry_confidence = self._estimate_from_industry_profile(lead)
            if industry_estimate:
                revenue_estimates.append(industry_estimate)
                confidence_factors.append(industry_confidence)
                estimation_methods.append("industry_benchmarking")
                indicators.append(f"Industry ({lead.industry}) benchmarking")
        
        # Calculate weighted average estimate
        if revenue_estimates and confidence_factors:
            # Weighted average based on confidence
            total_weight = sum(confidence_factors)
            weighted_revenue = sum(est * conf for est, conf in zip(revenue_estimates, confidence_factors))
            final_estimate = int(weighted_revenue / total_weight) if total_weight > 0 else 0
            
            # Average confidence
            average_confidence = sum(confidence_factors) / len(confidence_factors)
            
            # Apply location adjustment
            if lead.location.is_hamilton_area():
                final_estimate = int(final_estimate * 0.85)  # 15% lower costs
            
            # Create revenue estimate
            lead.revenue_estimate = RevenueEstimate(
                estimated_amount=final_estimate,
                confidence_score=min(average_confidence, 1.0),
                estimation_method=estimation_methods,
                indicators=indicators
            )
            
            self.enrichment_stats['revenue_estimates_generated'] += 1
            
            if average_confidence >= 0.7:
                self.enrichment_stats['high_confidence_estimates'] += 1
        
        else:
            # No reliable estimation possible
            lead.revenue_estimate = RevenueEstimate(
                indicators=["Insufficient data for revenue estimation"]
            )
        
        return lead
    
    def _estimate_from_employees(self, lead: BusinessLead) -> tuple[Optional[int], float]:
        """Estimate revenue based on employee count and industry."""
        
        if not lead.employee_count or not lead.industry:
            return None, 0.0
        
        industry_key = lead.industry.lower()
        benchmark = self.benchmarks.get(industry_key, self.benchmarks.get('manufacturing'))
        
        if not benchmark:
            return None, 0.0
        
        # Base calculation
        estimated_revenue = lead.employee_count * benchmark['revenue_per_employee']
        
        # Confidence based on how well employee count fits typical range
        min_employees, max_employees = benchmark['employee_range']
        
        if min_employees <= lead.employee_count <= max_employees:
            confidence = benchmark['confidence_multiplier'] * 1.2  # Boost for fitting range
        elif min_employees * 0.7 <= lead.employee_count <= max_employees * 1.3:
            confidence = benchmark['confidence_multiplier'] * 0.8  # Reduce for being outside typical range
        else:
            confidence = benchmark['confidence_multiplier'] * 0.5  # Low confidence for outliers
        
        return estimated_revenue, min(confidence, 1.0)
    
    def _estimate_from_business_age(self, lead: BusinessLead) -> tuple[Optional[int], float]:
        """Estimate revenue based on business age and stability indicators."""
        
        if not lead.years_in_business:
            return None, 0.0
        
        # Base estimate for established businesses
        if lead.years_in_business >= 25:
            base_estimate = 1_800_000  # Very established
            confidence = 0.4
        elif lead.years_in_business >= 20:
            base_estimate = 1_500_000  # Well established
            confidence = 0.35
        elif lead.years_in_business >= 15:
            base_estimate = 1_200_000  # Established
            confidence = 0.3
        else:
            return None, 0.0  # Too young for reliable age-based estimation
        
        # Adjust for industry if known
        if lead.industry and lead.industry in self.benchmarks:
            benchmark = self.benchmarks[lead.industry]
            growth_factor = 1.0 + (benchmark['growth_rate'] * lead.years_in_business)
            base_estimate = int(base_estimate * growth_factor)
        
        return base_estimate, confidence
    
    def _estimate_from_industry_profile(self, lead: BusinessLead) -> tuple[Optional[int], float]:
        """Estimate revenue based on industry profile and typical business characteristics."""
        
        if not lead.industry or lead.industry not in self.benchmarks:
            return None, 0.0
        
        benchmark = self.benchmarks[lead.industry]
        
        # Use middle of typical employee range for baseline
        min_emp, max_emp = benchmark['employee_range']
        typical_employees = (min_emp + max_emp) // 2
        
        base_estimate = typical_employees * benchmark['revenue_per_employee']
        
        # Adjust confidence based on how much data we have
        confidence = benchmark['confidence_multiplier'] * 0.6  # Lower than employee-based
        
        # Adjust for known employee count
        if lead.employee_count:
            if min_emp <= lead.employee_count <= max_emp:
                confidence *= 1.3  # Boost confidence
            else:
                confidence *= 0.7  # Reduce confidence
        
        return base_estimate, min(confidence, 1.0)
    
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
    
    def get_enrichment_stats(self) -> Dict[str, int]:
        """Get enrichment statistics."""
        return self.enrichment_stats.copy()