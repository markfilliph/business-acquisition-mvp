"""
Standardized output schema for all lead generation.

This schema MUST be used for ALL lead exports to ensure consistency.
Fields are locked and should NEVER change between lead generation runs.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from .config import INDUSTRY_BENCHMARKS


# LOCKED SCHEMA - DO NOT MODIFY FIELD NAMES WITHOUT APPROVAL
STANDARD_CSV_HEADERS = [
    'Business Name',
    'Address',
    'City',
    'Province',
    'Postal Code',
    'Phone Number',
    'Website',
    'Industry',
    'Estimated Employees (Range)',
    'Estimated SDE (CAD)',
    'Estimated Revenue (CAD)',
    'Confidence Score',
    'Status',
    'Data Sources'
]


class StandardLeadOutput(BaseModel):
    """
    Standardized lead output format - ALL fields are required.

    This model enforces consistent output across all lead generation runs.
    """

    # REQUIRED CORE FIELDS
    business_name: str = Field(..., description="Legal or operating business name")
    address: str = Field(..., description="Street address (number + street)")
    city: str = Field(default="Hamilton", description="City name")
    province: str = Field(default="ON", description="Province code (2 letters)")
    postal_code: str = Field(..., description="Canadian postal code (A1A 1A1 format)")
    phone_number: str = Field(..., description="Primary phone (XXX) XXX-XXXX format)")
    website: str = Field(..., description="Company website URL")

    # BUSINESS METRICS
    industry: str = Field(..., description="Primary industry classification")
    estimated_employees_range: str = Field(..., description="Employee count range (e.g., '5-10', '10-25')")
    estimated_sde_cad: str = Field(..., description="Estimated Seller's Discretionary Earnings in CAD")
    estimated_revenue_cad: str = Field(..., description="Estimated annual revenue in CAD")

    # METADATA
    confidence_score: str = Field(..., description="Overall data confidence (0-100%)")
    status: str = Field(default="QUALIFIED", description="Lead status")
    data_sources: str = Field(..., description="Comma-separated list of data sources")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching STANDARD_CSV_HEADERS exactly."""
        return {
            'Business Name': self.business_name,
            'Address': self.address,
            'City': self.city,
            'Province': self.province,
            'Postal Code': self.postal_code,
            'Phone Number': self.phone_number,
            'Website': self.website,
            'Industry': self.industry,
            'Estimated Employees (Range)': self.estimated_employees_range,
            'Estimated SDE (CAD)': self.estimated_sde_cad,
            'Estimated Revenue (CAD)': self.estimated_revenue_cad,
            'Confidence Score': self.confidence_score,
            'Status': self.status,
            'Data Sources': self.data_sources
        }


def calculate_sde_from_revenue(
    revenue: int,
    employee_count: Optional[int] = None,
    industry: Optional[str] = None
) -> tuple[int, str]:
    """
    Calculate Seller's Discretionary Earnings (SDE) from revenue.

    SDE = Revenue - (COGS + Operating Expenses) + Owner Compensation + Non-recurring expenses

    For small businesses, SDE typically ranges from 15-30% of revenue depending on:
    - Industry margins
    - Business maturity
    - Employee count

    Args:
        revenue: Annual revenue estimate
        employee_count: Number of employees
        industry: Industry classification

    Returns:
        Tuple of (sde_amount, formatted_string)
    """
    # Base SDE percentages by industry
    sde_margins = {
        'manufacturing': 0.18,      # 18% - lower margins due to COGS
        'wholesale': 0.20,          # 20% - moderate margins
        'professional_services': 0.30,  # 30% - higher margins, lower COGS
        'printing': 0.18,           # 18% - equipment and material costs
        'construction': 0.22,       # 22% - moderate margins
        'equipment_rental': 0.25,   # 25% - good margins after equipment costs
        'default': 0.22             # 22% - conservative default
    }

    # Get base margin for industry
    margin = sde_margins.get(industry, sde_margins['default'])

    # Adjust margin based on employee count (smaller = higher SDE %)
    if employee_count:
        if employee_count <= 5:
            margin += 0.05  # +5% for very small businesses
        elif employee_count >= 20:
            margin -= 0.03  # -3% for larger businesses (more overhead)

    # Ensure margin stays within reasonable bounds (15-35%)
    margin = max(0.15, min(0.35, margin))

    # Calculate SDE
    sde = int(revenue * margin)

    # Format as currency with margin indicator
    formatted = format_currency_cad(sde, show_margin=True, margin=margin)

    return sde, formatted


def calculate_employee_range(
    employee_count: Optional[int] = None,
    industry: Optional[str] = None,
    revenue: Optional[int] = None
) -> str:
    """
    Calculate employee range estimate.

    If exact count is known, create a range around it.
    If estimated, use industry benchmarks and revenue.

    Args:
        employee_count: Known or estimated employee count
        industry: Industry classification
        revenue: Annual revenue estimate

    Returns:
        Formatted range string (e.g., "5-10", "10-25")
    """
    if employee_count:
        # Known count - create a reasonable range around it
        if employee_count <= 3:
            return f"1-{employee_count + 2}"
        elif employee_count <= 10:
            lower = max(1, employee_count - 2)
            upper = employee_count + 3
            return f"{lower}-{upper}"
        elif employee_count <= 25:
            lower = max(1, employee_count - 5)
            upper = employee_count + 5
            return f"{lower}-{upper}"
        else:
            lower = max(1, employee_count - 10)
            upper = employee_count + 10
            return f"{lower}-{upper}"

    # Estimate from revenue and industry
    if revenue and industry:
        benchmark = INDUSTRY_BENCHMARKS.get(industry, {})
        revenue_per_employee = benchmark.get('revenue_per_employee', 75000)

        estimated = revenue / revenue_per_employee

        if estimated <= 5:
            return "3-8"
        elif estimated <= 10:
            return "8-15"
        elif estimated <= 20:
            return "15-30"
        elif estimated <= 50:
            return "30-60"
        else:
            return "50+"

    # Default ranges by industry
    default_ranges = {
        'manufacturing': "8-25",
        'wholesale': "5-18",
        'professional_services': "3-15",
        'printing': "5-20",
        'construction': "10-30",
        'equipment_rental': "5-15"
    }

    return default_ranges.get(industry, "5-20")


def format_currency_cad(amount: int, show_margin: bool = False, margin: float = 0.0) -> str:
    """
    Format currency amount in CAD with proper formatting.

    Args:
        amount: Dollar amount
        show_margin: Include margin percentage in output
        margin: SDE margin percentage (if applicable)

    Returns:
        Formatted string (e.g., "$1.2M", "$450K", "$85K (18% margin)")
    """
    if amount >= 1_000_000:
        formatted = f"${amount / 1_000_000:.1f}M"
    else:
        formatted = f"${amount / 1_000:.0f}K"

    if show_margin and margin > 0:
        formatted += f" ({margin:.0%} margin)"

    return formatted


def convert_business_lead_to_standard_output(business_lead) -> StandardLeadOutput:
    """
    Convert a BusinessLead model to StandardLeadOutput format.

    This ensures ALL leads are exported in the same consistent format.

    Args:
        business_lead: BusinessLead instance from models.py

    Returns:
        StandardLeadOutput instance ready for CSV export
    """
    # Calculate employee range
    employee_range = calculate_employee_range(
        employee_count=business_lead.employee_count,
        industry=business_lead.industry,
        revenue=business_lead.revenue_estimate.estimated_amount
    )

    # Calculate revenue
    revenue = business_lead.revenue_estimate.estimated_amount or 0
    revenue_formatted = format_currency_cad(revenue) if revenue > 0 else "Unknown"

    # Calculate SDE
    sde_amount, sde_formatted = calculate_sde_from_revenue(
        revenue=revenue,
        employee_count=business_lead.employee_count,
        industry=business_lead.industry
    ) if revenue > 0 else (0, "Unknown")

    # Format confidence score
    confidence = f"{business_lead.confidence_score:.0%}"

    # Format data sources
    sources = ", ".join([source.value for source in business_lead.data_sources]) if business_lead.data_sources else "Unknown"

    return StandardLeadOutput(
        business_name=business_lead.business_name,
        address=business_lead.location.address or "Unknown",
        city=business_lead.location.city or "Hamilton",
        province=business_lead.location.province or "ON",
        postal_code=business_lead.location.postal_code or "Unknown",
        phone_number=business_lead.contact.phone or "Unknown",
        website=business_lead.contact.website or "Unknown",
        industry=business_lead.industry or "Unknown",
        estimated_employees_range=employee_range,
        estimated_sde_cad=sde_formatted,
        estimated_revenue_cad=revenue_formatted,
        confidence_score=confidence,
        status=business_lead.status.value.upper(),
        data_sources=sources
    )
