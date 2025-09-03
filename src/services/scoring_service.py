"""
Intelligent lead scoring service with dynamic weights and detailed analysis.
"""
from datetime import datetime
from typing import List, Dict, Any, Tuple

import structlog

from ..core.config import SystemConfig
from ..core.models import BusinessLead, LeadScore, LeadStatus
from ..core.exceptions import ScoringError


class IntelligentScoringService:
    """Advanced lead scoring with dynamic weights and comprehensive analysis."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self.weights = config.scoring
        
        self.scoring_stats = {
            'leads_scored': 0,
            'leads_qualified': 0,
            'leads_disqualified': 0,
            'average_score': 0.0,
            'score_distribution': {'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0}
        }
    
    async def score_leads(self, leads: List[BusinessLead]) -> List[BusinessLead]:
        """Score multiple leads and update statistics."""
        
        self.logger.info("scoring_started", count=len(leads))
        
        scored_leads = []
        total_score = 0
        
        for lead in leads:
            try:
                scored_lead = await self.score_single_lead(lead)
                scored_leads.append(scored_lead)
                
                # Update statistics
                total_score += scored_lead.lead_score.total_score
                self.scoring_stats['leads_scored'] += 1
                
                if scored_lead.lead_score.is_qualified(self.weights.qualification_threshold):
                    self.scoring_stats['leads_qualified'] += 1
                else:
                    self.scoring_stats['leads_disqualified'] += 1
                
                # Update score distribution
                score = scored_lead.lead_score.total_score
                if score >= 80:
                    self.scoring_stats['score_distribution']['excellent'] += 1
                elif score >= 60:
                    self.scoring_stats['score_distribution']['good'] += 1
                elif score >= 40:
                    self.scoring_stats['score_distribution']['fair'] += 1
                else:
                    self.scoring_stats['score_distribution']['poor'] += 1
                
            except Exception as e:
                self.logger.error("lead_scoring_failed", 
                                business_name=lead.business_name,
                                error=str(e))
                # Add lead with error status
                lead.status = LeadStatus.ERROR
                lead.validation_errors.append(f"Scoring failed: {str(e)}")
                scored_leads.append(lead)
        
        # Calculate average score
        if self.scoring_stats['leads_scored'] > 0:
            self.scoring_stats['average_score'] = total_score / self.scoring_stats['leads_scored']
        
        # Sort leads by score (highest first)
        scored_leads.sort(key=lambda x: x.lead_score.total_score, reverse=True)
        
        self.logger.info("scoring_completed", 
                        qualified=self.scoring_stats['leads_qualified'],
                        average_score=self.scoring_stats['average_score'])
        
        return scored_leads
    
    async def score_single_lead(self, lead: BusinessLead) -> BusinessLead:
        """Score a single lead with detailed breakdown."""
        
        try:
            lead.status = LeadStatus.SCORING
            
            # Initialize scoring components
            qualification_reasons = []
            disqualification_reasons = []
            
            # Score each component
            revenue_score, revenue_reasons = self._score_revenue_fit(lead)
            age_score, age_reasons = self._score_business_age(lead)
            data_score, data_reasons = self._score_data_quality(lead)
            industry_score, industry_reasons = self._score_industry_fit(lead)
            location_score, location_reasons = self._score_location(lead)
            growth_score, growth_reasons = self._score_growth_indicators(lead)
            
            # Combine reasons
            all_reasons = [
                revenue_reasons, age_reasons, data_reasons,
                industry_reasons, location_reasons, growth_reasons
            ]
            
            for reasons in all_reasons:
                qualification_reasons.extend(reasons.get('positive', []))
                disqualification_reasons.extend(reasons.get('negative', []))
            
            # Calculate total score
            total_score = min(
                revenue_score + age_score + data_score + 
                industry_score + location_score + growth_score,
                100
            )
            
            # Create detailed lead score
            lead.lead_score = LeadScore(
                total_score=total_score,
                revenue_fit_score=revenue_score,
                business_age_score=age_score,
                data_quality_score=data_score,
                industry_fit_score=industry_score,
                location_score=location_score,
                growth_score=growth_score,
                qualification_reasons=qualification_reasons,
                disqualification_reasons=disqualification_reasons,
                scoring_timestamp=datetime.utcnow()
            )
            
            # Determine final qualification status
            if lead.lead_score.is_qualified(self.weights.qualification_threshold):
                lead.status = LeadStatus.QUALIFIED
                lead.add_note(f"QUALIFIED with score {total_score}/100", "scoring_service")
            else:
                lead.status = LeadStatus.DISQUALIFIED
                lead.add_note(f"Disqualified with score {total_score}/100", "scoring_service")
            
            return lead
            
        except Exception as e:
            self.logger.error("single_lead_scoring_failed", 
                            business_name=lead.business_name,
                            error=str(e))
            raise ScoringError(f"Failed to score lead {lead.business_name}: {e}")
    
    def _score_revenue_fit(self, lead: BusinessLead) -> Tuple[int, Dict[str, List[str]]]:
        """Score revenue fit against target range."""
        
        reasons = {'positive': [], 'negative': []}
        
        if not lead.revenue_estimate.estimated_amount:
            reasons['negative'].append("No revenue estimate available")
            return 0, reasons
        
        if lead.revenue_estimate.confidence_score < 0.2:
            reasons['negative'].append("Very low revenue estimation confidence")
            return 2, reasons
        
        revenue = lead.revenue_estimate.estimated_amount
        target_min = self.config.business_criteria.target_revenue_min
        target_max = self.config.business_criteria.target_revenue_max
        
        # Score based on fit to target range
        if target_min <= revenue <= target_max:
            # Perfect fit - scale by confidence
            base_score = self.weights.revenue_fit
            confidence_multiplier = lead.revenue_estimate.confidence_score
            score = int(base_score * confidence_multiplier)
            
            reasons['positive'].append(f"Revenue estimate ${revenue/1_000_000:.1f}M fits target range perfectly")
            
            if confidence_multiplier >= 0.7:
                reasons['positive'].append(f"High confidence ({confidence_multiplier:.1%}) in revenue estimate")
            
        else:
            # Outside target range - disqualify
            score = 0
            reasons['negative'].append(f"Revenue estimate ${revenue/1_000_000:.1f}M outside strict target range (${target_min/1_000_000:.1f}M-${target_max/1_000_000:.1f}M)")
        
        return score, reasons
    
    def _score_business_age(self, lead: BusinessLead) -> Tuple[int, Dict[str, List[str]]]:
        """Score business age and stability."""
        
        reasons = {'positive': [], 'negative': []}
        
        if not lead.years_in_business:
            reasons['negative'].append("Unknown business age")
            return 0, reasons
        
        age = lead.years_in_business
        min_age = self.config.business_criteria.min_years_in_business
        
        if age >= min_age + 10:  # Well beyond minimum
            score = self.weights.business_age
            reasons['positive'].append(f"Very established business ({age} years)")
        elif age >= min_age + 5:  # Above minimum
            score = int(self.weights.business_age * 0.8)
            reasons['positive'].append(f"Well established business ({age} years)")
        elif age >= min_age:  # Meets minimum
            score = int(self.weights.business_age * 0.6)
            reasons['positive'].append(f"Meets minimum age requirement ({age} years)")
        else:
            score = 0
            reasons['negative'].append(f"Too young ({age} years, minimum {min_age})")
        
        return score, reasons
    
    def _score_data_quality(self, lead: BusinessLead) -> Tuple[int, Dict[str, List[str]]]:
        """Score data completeness and quality."""
        
        reasons = {'positive': [], 'negative': []}
        
        completeness = lead.calculate_data_completeness()
        confidence = lead.confidence_score
        
        # Base score from data completeness
        base_score = int(self.weights.data_quality * completeness)
        
        # Adjust for confidence
        final_score = int(base_score * (0.5 + confidence * 0.5))
        
        if completeness >= 0.8:
            reasons['positive'].append(f"Excellent data completeness ({completeness:.1%})")
        elif completeness >= 0.6:
            reasons['positive'].append(f"Good data completeness ({completeness:.1%})")
        elif completeness >= 0.4:
            reasons['positive'].append(f"Fair data completeness ({completeness:.1%})")
        else:
            reasons['negative'].append(f"Poor data completeness ({completeness:.1%})")
        
        if confidence >= 0.7:
            reasons['positive'].append(f"High data confidence ({confidence:.1%})")
        elif confidence < 0.3:
            reasons['negative'].append(f"Low data confidence ({confidence:.1%})")
        
        return final_score, reasons
    
    def _score_industry_fit(self, lead: BusinessLead) -> Tuple[int, Dict[str, List[str]]]:
        """Score industry alignment with targets."""
        
        reasons = {'positive': [], 'negative': []}
        
        if not lead.industry:
            reasons['negative'].append("Unknown industry")
            return 0, reasons
        
        target_industries = self.config.business_criteria.target_industries
        
        if lead.industry.lower() in [ind.lower() for ind in target_industries]:
            score = self.weights.industry_fit
            reasons['positive'].append(f"Target industry: {lead.industry}")
        elif lead.industry.lower() in ['manufacturing', 'wholesale', 'construction']:
            score = int(self.weights.industry_fit * 0.7)
            reasons['positive'].append(f"Compatible industry: {lead.industry}")
        else:
            score = int(self.weights.industry_fit * 0.3)
            reasons['negative'].append(f"Non-target industry: {lead.industry}")
        
        return score, reasons
    
    def _score_location(self, lead: BusinessLead) -> Tuple[int, Dict[str, List[str]]]:
        """Score location advantages."""
        
        reasons = {'positive': [], 'negative': []}
        
        if lead.location.is_hamilton_area():
            score = self.weights.location_bonus
            reasons['positive'].append("Located in Hamilton area (target market)")
            
            if lead.location.city and 'hamilton' in lead.location.city.lower():
                reasons['positive'].append("Central Hamilton location")
            elif lead.location.city:
                reasons['positive'].append(f"Hamilton suburb location: {lead.location.city}")
        else:
            score = 0
            reasons['negative'].append("Outside Hamilton target area")
        
        return score, reasons
    
    def _score_growth_indicators(self, lead: BusinessLead) -> Tuple[int, Dict[str, List[str]]]:
        """Score potential growth indicators."""
        
        reasons = {'positive': [], 'negative': []}
        
        score = 0
        
        # Employee count suggests stability
        if lead.employee_count:
            if 5 <= lead.employee_count <= 30:
                score += int(self.weights.growth_indicators * 0.4)
                reasons['positive'].append(f"Optimal team size ({lead.employee_count}) for acquisition")
            elif lead.employee_count > 30:
                score += int(self.weights.growth_indicators * 0.2)
                reasons['positive'].append(f"Larger established operation ({lead.employee_count} employees)")
        
        # Revenue confidence indicates data quality
        if lead.revenue_estimate.confidence_score >= 0.7:
            score += int(self.weights.growth_indicators * 0.3)
            reasons['positive'].append("High-confidence revenue estimate indicates transparency")
        
        # Multiple data sources suggest visibility
        if len(lead.data_sources) > 1:
            score += int(self.weights.growth_indicators * 0.3)
            reasons['positive'].append("Multiple data sources suggest market presence")
        
        if score == 0:
            reasons['negative'].append("Limited growth indicators identified")
        
        return min(score, self.weights.growth_indicators), reasons
    
    def get_scoring_stats(self) -> Dict[str, Any]:
        """Get scoring statistics."""
        return self.scoring_stats.copy()