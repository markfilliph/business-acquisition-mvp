"""
Production data models with comprehensive validation.
"""
import hashlib
import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ConfigDict

from .config import HAMILTON_POSTAL_CODES, HAMILTON_NEIGHBORHOODS


class LeadStatus(str, Enum):
    """Lead processing status with clear state transitions."""
    DISCOVERED = "discovered"
    VALIDATING = "validating"
    VALIDATED = "validated"
    ENRICHING = "enriching"
    ENRICHED = "enriched"
    SCORING = "scoring"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    ERROR = "error"
    ARCHIVED = "archived"


class DataSource(str, Enum):
    """Known data sources for lead discovery."""
    HAMILTON_CHAMBER = "hamilton_chamber"
    ONTARIO_MANUFACTURING = "ontario_manufacturing_directory"
    YELLOWPAGES = "yellowpages"
    GOOGLE_BUSINESS = "google_business"
    LINKEDIN = "linkedin"
    CANADA411 = "canada411"
    INDUSTRY_ASSOCIATION = "industry_association"
    MANUAL_RESEARCH = "manual_research"
    WEB_SCRAPING = "web_scraping"
    API_INTEGRATION = "api_integration"
    OPENSTREETMAP = "openstreetmap"
    VERIFIED_DATABASE = "verified_database"
    BUSINESS_AGGREGATOR = "business_aggregator"


class ContactInfo(BaseModel):
    """Validated contact information sub-model."""
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    # Website validation fields
    website_validated: bool = False
    website_validation_timestamp: Optional[datetime] = None
    website_status_code: Optional[int] = None
    website_response_time: Optional[float] = None
    website_business_name_match: float = 0.0
    website_has_ssl: bool = False
    website_validation_error: Optional[str] = None
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate and normalize Canadian phone numbers."""
        if not v:
            return None
        
        # Remove all non-digits
        digits = re.sub(r'\D', '', v)
        
        # Canadian phone number validation
        if len(digits) == 10:
            # Format as (XXX) XXX-XXXX
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            # Remove leading 1 and format
            digits = digits[1:]
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        
        return None  # Invalid phone number
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format."""
        if not v:
            return None
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, v.lower().strip()):
            return v.lower().strip()
        
        return None
    
    @field_validator('website')
    @classmethod
    def validate_website(cls, v):
        """Validate and normalize website URLs."""
        if not v:
            return None
        
        # Add protocol if missing
        if not v.startswith(('http://', 'https://')):
            v = f"https://{v}"
        
        try:
            parsed = urlparse(v)
            if parsed.netloc and '.' in parsed.netloc:
                return v.lower().strip()
        except Exception:
            pass
        
        return None
    
    def is_website_verified(self) -> bool:
        """Check if website is properly verified."""
        return (
            self.website_validated and
            self.website_status_code == 200 and
            self.website_business_name_match >= 0.6 and
            not self.website_validation_error
        )
    
    def update_website_validation(self, validation_result):
        """Update website validation fields from validation result."""
        from datetime import datetime
        
        self.website_validated = validation_result.is_accessible
        self.website_validation_timestamp = datetime.utcnow()
        self.website_status_code = validation_result.status_code
        self.website_response_time = validation_result.response_time
        self.website_business_name_match = validation_result.business_name_match
        self.website_has_ssl = validation_result.has_ssl
        self.website_validation_error = validation_result.error_message


class LocationInfo(BaseModel):
    """Validated location information."""
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "Canada"
    
    @field_validator('postal_code')
    @classmethod
    def validate_postal_code(cls, v):
        """Validate Canadian postal codes."""
        if not v:
            return None
        
        # Clean and format postal code
        cleaned = re.sub(r'[^A-Z0-9]', '', v.upper())
        
        if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', cleaned):
            return f"{cleaned[:3]} {cleaned[3:]}"
        
        return None
    
    @field_validator('province')
    @classmethod
    def validate_province(cls, v):
        """Normalize province names."""
        if not v:
            return "ON"  # Default to Ontario
        
        province_mapping = {
            "ontario": "ON",
            "on": "ON",
            "ont": "ON",
            "quebec": "QC",
            "qc": "QC",
            "british columbia": "BC",
            "bc": "BC"
        }
        
        return province_mapping.get(v.lower().strip(), v.upper())
    
    def is_hamilton_area(self) -> bool:
        """Check if location is in Hamilton area."""
        if not self.address:
            return False
        
        address_lower = self.address.lower()
        
        # Check for Hamilton neighborhoods
        if any(neighborhood in address_lower for neighborhood in HAMILTON_NEIGHBORHOODS):
            return True
        
        # Check postal code prefix
        if self.postal_code:
            prefix = self.postal_code[:3].replace(' ', '')
            return prefix in HAMILTON_POSTAL_CODES
        
        return False


class RevenueEstimate(BaseModel):
    """Revenue estimation with confidence tracking."""
    estimated_amount: Optional[int] = None
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    estimation_method: List[str] = Field(default_factory=list)
    indicators: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    def format_revenue(self) -> str:
        """Format revenue as human-readable string."""
        if not self.estimated_amount:
            return "Unknown"
        
        millions = self.estimated_amount / 1_000_000
        if millions >= 1.0:
            return f"${millions:.1f}M"
        else:
            thousands = self.estimated_amount / 1_000
            return f"${thousands:.0f}K"
    
    def is_in_target_range(self, min_revenue: int = 1_000_000, max_revenue: int = 2_000_000) -> bool:
        """Check if estimate falls within target range."""
        if not self.estimated_amount:
            return False
        return min_revenue <= self.estimated_amount <= max_revenue


class LeadScore(BaseModel):
    """Detailed lead scoring breakdown."""
    total_score: int = Field(0, ge=0, le=100)
    revenue_fit_score: int = Field(0, ge=0, le=35)
    business_age_score: int = Field(0, ge=0, le=25)
    data_quality_score: int = Field(0, ge=0, le=15)
    industry_fit_score: int = Field(0, ge=0, le=10)
    location_score: int = Field(0, ge=0, le=8)
    growth_score: int = Field(0, ge=0, le=7)
    
    qualification_reasons: List[str] = Field(default_factory=list)
    disqualification_reasons: List[str] = Field(default_factory=list)
    scoring_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def is_qualified(self, threshold: int = 60) -> bool:
        """Check if lead meets qualification threshold."""
        return self.total_score >= threshold and len(self.disqualification_reasons) == 0


class BusinessLead(BaseModel):
    """Complete business lead model with full validation."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    # Core identification
    business_name: str = Field(min_length=2, max_length=200)
    unique_id: Optional[str] = None
    
    # Location and contact
    location: LocationInfo = Field(default_factory=LocationInfo)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    
    # Business details
    industry: Optional[str] = None
    years_in_business: Optional[int] = Field(None, ge=0, le=150)
    employee_count: Optional[int] = Field(None, ge=1, le=10000)
    business_description: Optional[str] = None
    
    # Revenue and scoring
    revenue_estimate: RevenueEstimate = Field(default_factory=RevenueEstimate)
    lead_score: LeadScore = Field(default_factory=LeadScore)
    
    # Metadata and tracking
    status: LeadStatus = LeadStatus.DISCOVERED
    data_sources: List[DataSource] = Field(default_factory=list)
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    notes: List[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_contacted: Optional[datetime] = None
    
    # Internal processing flags
    validation_errors: List[str] = Field(default_factory=list)
    enrichment_attempts: int = 0
    
    @model_validator(mode='before')
    @classmethod
    def generate_unique_id(cls, values):
        """Generate unique ID after all validation."""
        if not values.get('unique_id'):
            # Create stable hash from core business identifiers
            business_name = values.get('business_name', '')
            location = values.get('location') or LocationInfo()
            contact = values.get('contact') or ContactInfo()
            
            identifier_string = f"{business_name}_{location.address or ''}_{contact.phone or ''}"
            values['unique_id'] = hashlib.md5(identifier_string.encode()).hexdigest()[:12]
        
        return values
    
    @field_validator('industry')
    @classmethod
    def normalize_industry(cls, v):
        """Normalize industry names."""
        if not v:
            return None
        
        # Common industry mappings
        industry_mapping = {
            "manufacturing": "manufacturing",
            "manufacturer": "manufacturing",
            "wholesale": "wholesale",
            "wholesaler": "wholesale",
            "construction": "construction",
            "contractor": "construction",
            "professional services": "professional_services",
            "printing": "printing",
            "metal fabrication": "metal_fabrication",
            "auto repair": "auto_repair"
        }
        
        normalized = v.lower().strip()
        return industry_mapping.get(normalized, normalized)
    
    def calculate_data_completeness(self) -> float:
        """Calculate percentage of key data fields populated."""
        key_fields = [
            self.contact.phone,
            self.contact.email,
            self.contact.website,
            self.location.address,
            self.industry,
            self.years_in_business,
            self.employee_count
        ]
        
        completed = sum(1 for field in key_fields if field is not None)
        return completed / len(key_fields)
    
    def update_confidence_score(self):
        """Update overall confidence score based on data completeness and revenue confidence."""
        data_completeness = self.calculate_data_completeness()
        revenue_confidence = self.revenue_estimate.confidence_score
        
        # Weighted average: 60% data completeness, 40% revenue confidence
        self.confidence_score = (data_completeness * 0.6) + (revenue_confidence * 0.4)
    
    def add_note(self, note: str, source: str = "system"):
        """Add timestamped note."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        formatted_note = f"[{timestamp}] {source}: {note}"
        self.notes.append(formatted_note)
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export/serialization."""
        return {
            "unique_id": self.unique_id,
            "business_name": self.business_name,
            "industry": self.industry,
            "address": self.location.address,
            "city": self.location.city,
            "postal_code": self.location.postal_code,
            "phone": self.contact.phone,
            "email": self.contact.email,
            "website": self.contact.website,
            "years_in_business": self.years_in_business,
            "employee_count": self.employee_count,
            "estimated_revenue": self.revenue_estimate.format_revenue(),
            "revenue_confidence": f"{self.revenue_estimate.confidence_score:.1%}",
            "lead_score": self.lead_score.total_score,
            "qualification_status": "Qualified" if self.lead_score.is_qualified() else "Not Qualified",
            "status": self.status.value,
            "confidence_score": f"{self.confidence_score:.1%}",
            "data_sources": [source.value for source in self.data_sources],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "notes": "; ".join(self.notes[-3:]) if self.notes else ""  # Last 3 notes
        }


class PipelineResults(BaseModel):
    """Results from a complete pipeline run."""
    
    # Statistics
    total_discovered: int = 0
    total_validated: int = 0
    total_enriched: int = 0
    total_qualified: int = 0
    total_errors: int = 0
    
    # Timing
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Results
    qualified_leads: List[BusinessLead] = Field(default_factory=list)
    top_performers: List[BusinessLead] = Field(default_factory=list)
    
    # Analysis
    success_rate: float = 0.0
    average_score: float = 0.0
    industry_breakdown: Dict[str, int] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    
    def finalize(self):
        """Calculate final statistics."""
        self.end_time = datetime.utcnow()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        if self.total_discovered > 0:
            self.success_rate = self.total_qualified / self.total_discovered
        
        if self.qualified_leads:
            self.average_score = sum(lead.lead_score.total_score for lead in self.qualified_leads) / len(self.qualified_leads)
            
            # Sort and get top performers
            sorted_leads = sorted(self.qualified_leads, key=lambda x: x.lead_score.total_score, reverse=True)
            self.top_performers = sorted_leads[:10]
            
            # Industry breakdown
            for lead in self.qualified_leads:
                industry = lead.industry or "unknown"
                self.industry_breakdown[industry] = self.industry_breakdown.get(industry, 0) + 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "pipeline_statistics": {
                "total_discovered": self.total_discovered,
                "total_validated": self.total_validated,
                "total_enriched": self.total_enriched,
                "total_qualified": self.total_qualified,
                "total_errors": self.total_errors,
                "success_rate": f"{self.success_rate:.1%}",
                "average_score": f"{self.average_score:.1f}",
                "duration_seconds": self.duration_seconds
            },
            "qualified_leads": [lead.to_dict() for lead in self.qualified_leads],
            "top_performers": [lead.to_dict() for lead in self.top_performers],
            "industry_breakdown": self.industry_breakdown,
            "recommendations": self.recommendations,
            "timestamp": self.end_time.isoformat() if self.end_time else None
        }