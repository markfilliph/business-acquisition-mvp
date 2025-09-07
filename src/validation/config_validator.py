#!/usr/bin/env python3
"""
Configuration validation system to prevent critical business logic errors.
Validates target criteria, revenue ranges, and industry classifications.
"""
import asyncio
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

import structlog
import aiohttp

from src.core.config import config
from src.core.models import BusinessLead


@dataclass 
class ValidationError:
    """Represents a critical validation error."""
    severity: str  # 'critical', 'warning', 'info'
    category: str  # 'revenue', 'industry', 'website', 'location' 
    message: str
    details: Dict[str, Any]


class CriticalConfigValidator:
    """Validates configuration and prevents critical business logic errors."""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.errors: List[ValidationError] = []
        
        # CRITICAL EXCLUSIONS - MUST NEVER BE INCLUDED
        self.FORBIDDEN_INDUSTRIES = {
            'welding', 'machining', 'metal_fabrication', 'auto_repair', 
            'construction', 'electrical', 'plumbing', 'hvac', 'roofing',
            'skilled_trades', 'contracting', 'carpentry', 'masonry',
            'landscaping', 'painting', 'flooring', 'demolition'
        }
        
        # ALLOWED INDUSTRIES ONLY
        self.ALLOWED_INDUSTRIES = {
            'manufacturing', 'wholesale', 'professional_services',
            'printing', 'equipment_rental'
        }
        
        # STRICT REVENUE RANGE
        self.MIN_REVENUE = 800_000  # $800K exactly
        self.MAX_REVENUE = 1_500_000  # $1.5M exactly
        
    async def validate_all(self) -> List[ValidationError]:
        """Run comprehensive validation checks."""
        self.errors = []
        
        # 1. Validate target industries
        self._validate_target_industries()
        
        # 2. Validate revenue ranges
        self._validate_revenue_ranges()
        
        # 3. Validate business criteria
        self._validate_business_criteria()
        
        # 4. Test website verification system
        await self._test_website_verification()
        
        return self.errors
    
    def _validate_target_industries(self):
        """Ensure no skilled trades in target industries."""
        target_industries = set(config.business_criteria.target_industries)
        
        # Check for forbidden industries
        forbidden_found = target_industries.intersection(self.FORBIDDEN_INDUSTRIES)
        if forbidden_found:
            self.errors.append(ValidationError(
                severity='critical',
                category='industry',
                message=f'CRITICAL: Forbidden skilled trades industries found in target list',
                details={'forbidden_industries': list(forbidden_found)}
            ))
        
        # Check for non-allowed industries
        non_allowed = target_industries - self.ALLOWED_INDUSTRIES
        if non_allowed:
            self.errors.append(ValidationError(
                severity='critical', 
                category='industry',
                message=f'CRITICAL: Non-approved industries found in target list',
                details={'non_approved_industries': list(non_allowed)}
            ))
    
    def _validate_revenue_ranges(self):
        """Validate strict revenue range compliance."""
        min_revenue = config.business_criteria.target_revenue_min
        max_revenue = config.business_criteria.target_revenue_max
        
        if min_revenue != self.MIN_REVENUE:
            self.errors.append(ValidationError(
                severity='critical',
                category='revenue',
                message=f'CRITICAL: Minimum revenue must be exactly ${self.MIN_REVENUE:,}',
                details={'configured': min_revenue, 'required': self.MIN_REVENUE}
            ))
        
        if max_revenue != self.MAX_REVENUE:
            self.errors.append(ValidationError(
                severity='critical', 
                category='revenue',
                message=f'CRITICAL: Maximum revenue must be exactly ${self.MAX_REVENUE:,}',
                details={'configured': max_revenue, 'required': self.MAX_REVENUE}
            ))
    
    def _validate_business_criteria(self):
        """Validate other business criteria."""
        criteria = config.business_criteria
        
        # Minimum age should be 15+ years
        if criteria.min_years_in_business < 15:
            self.errors.append(ValidationError(
                severity='warning',
                category='age',
                message='Business age minimum is less than recommended 15 years',
                details={'configured': criteria.min_years_in_business, 'recommended': 15}
            ))
        
        # Employee count should be reasonable
        if criteria.max_employee_count > 50:
            self.errors.append(ValidationError(
                severity='warning',
                category='size', 
                message='Maximum employee count exceeds recommended 50',
                details={'configured': criteria.max_employee_count, 'recommended': 50}
            ))
    
    async def _test_website_verification(self):
        """Test website verification system with known websites."""
        test_websites = [
            ('https://360energy.net', True),  # Should work
            ('https://nonexistent-site-12345.com', False),  # Should fail
            ('https://www.fox40world.com', True)  # Should work
        ]
        
        from src.services.validation_service import BusinessValidationService
        validator = BusinessValidationService(config)
        
        for website, expected_result in test_websites:
            try:
                result = await validator._verify_website(website)
                if result != expected_result:
                    self.errors.append(ValidationError(
                        severity='critical' if expected_result else 'warning',
                        category='website',
                        message=f'Website verification failed for {website}',
                        details={'expected': expected_result, 'actual': result, 'website': website}
                    ))
            except Exception as e:
                self.errors.append(ValidationError(
                    severity='critical',
                    category='website',
                    message=f'Website verification threw exception for {website}',
                    details={'website': website, 'error': str(e)}
                ))
    
    def validate_lead_against_criteria(self, lead: BusinessLead) -> List[ValidationError]:
        """Validate a specific lead against our criteria."""
        lead_errors = []
        
        # Check industry
        if lead.industry in self.FORBIDDEN_INDUSTRIES:
            lead_errors.append(ValidationError(
                severity='critical',
                category='industry', 
                message=f'CRITICAL: Lead {lead.business_name} is skilled trades ({lead.industry})',
                details={'business_name': lead.business_name, 'industry': lead.industry}
            ))
        
        # Check revenue if available
        if hasattr(lead, 'revenue_estimate') and lead.revenue_estimate.estimated_amount:
            revenue = lead.revenue_estimate.estimated_amount
            if not (self.MIN_REVENUE <= revenue <= self.MAX_REVENUE):
                lead_errors.append(ValidationError(
                    severity='critical',
                    category='revenue',
                    message=f'CRITICAL: Lead {lead.business_name} revenue ${revenue:,} outside target range',
                    details={
                        'business_name': lead.business_name,
                        'revenue': revenue,
                        'min_allowed': self.MIN_REVENUE,
                        'max_allowed': self.MAX_REVENUE
                    }
                ))
        
        return lead_errors
    
    def report_errors(self) -> str:
        """Generate error report."""
        if not self.errors:
            return "✅ All validation checks passed"
        
        report = []
        critical_count = sum(1 for e in self.errors if e.severity == 'critical')
        warning_count = sum(1 for e in self.errors if e.severity == 'warning')
        
        report.append(f"🚨 VALIDATION ERRORS FOUND: {critical_count} critical, {warning_count} warnings")
        report.append("=" * 60)
        
        for error in self.errors:
            icon = "🚨" if error.severity == 'critical' else "⚠️ "
            report.append(f"{icon} [{error.category.upper()}] {error.message}")
            if error.details:
                for key, value in error.details.items():
                    report.append(f"    {key}: {value}")
            report.append("")
        
        return "\n".join(report)


async def run_validation_check():
    """Run comprehensive validation and report results."""
    print("🔍 RUNNING CRITICAL CONFIGURATION VALIDATION")
    print("=" * 60)
    
    validator = CriticalConfigValidator()
    errors = await validator.validate_all()
    
    report = validator.report_errors()
    print(report)
    
    if any(e.severity == 'critical' for e in errors):
        print("\n❌ CRITICAL ERRORS FOUND - SYSTEM UNSAFE TO RUN")
        return False
    else:
        print("\n✅ VALIDATION PASSED - SYSTEM SAFE TO RUN")
        return True


if __name__ == "__main__":
    asyncio.run(run_validation_check())