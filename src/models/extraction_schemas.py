"""
Pydantic schemas for LLM-based data extraction.
PRIORITY: P0 - Critical for revenue gate (staff signals).
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator


class BusinessExtraction(BaseModel):
    """
    Schema for extracting business information from website content.

    Designed to prevent hallucination through strict validation.
    """

    founding_year: Optional[int] = Field(
        None,
        description="Year the company was founded (YYYY format). Only extract if explicitly stated.",
        ge=1800,
        le=2025
    )

    staff_count: Optional[int] = Field(
        None,
        description="Number of employees. Only extract if explicitly mentioned. Do NOT infer from company size adjectives.",
        ge=1,
        le=100000
    )

    facility_sqft: Optional[int] = Field(
        None,
        description="Facility size in square feet. Only extract if explicitly stated.",
        ge=100,
        le=10000000
    )

    certifications: List[str] = Field(
        default_factory=list,
        description="Industry certifications mentioned (ISO, AS9100, etc.)",
        max_items=20
    )

    equipment_mentions: List[str] = Field(
        default_factory=list,
        description="Manufacturing equipment or machinery mentioned",
        max_items=30
    )

    services_offered: List[str] = Field(
        default_factory=list,
        description="Explicit services or capabilities listed",
        max_items=50
    )

    confidence_score: float = Field(
        0.0,
        description="LLM confidence in extraction quality (0.0 - 1.0)",
        ge=0.0,
        le=1.0
    )

    extraction_notes: str = Field(
        "",
        description="Any caveats or context about the extraction",
        max_length=500
    )

    @validator('founding_year')
    def validate_founding_year(cls, v):
        """Ensure founding year is reasonable."""
        if v is not None:
            import datetime
            current_year = datetime.datetime.now().year
            if v > current_year:
                raise ValueError(f"Founding year {v} cannot be in the future")
            if v < 1800:
                raise ValueError(f"Founding year {v} is unreasonably old")
        return v

    @validator('staff_count')
    def validate_staff_count(cls, v):
        """Ensure staff count is reasonable."""
        if v is not None and v < 1:
            raise ValueError("Staff count must be at least 1")
        return v

    @validator('certifications', 'equipment_mentions', 'services_offered')
    def validate_lists_not_generic(cls, v):
        """Prevent generic/hallucinated list entries."""
        if v:
            # Filter out overly generic terms
            generic_terms = {'various', 'multiple', 'many', 'etc', 'and more', 'miscellaneous'}
            return [item for item in v if item.lower() not in generic_terms and len(item) > 2]
        return v


class WebsiteMetadata(BaseModel):
    """Metadata about the website scraping process."""

    url: str = Field(..., description="URL that was scraped")
    scrape_timestamp: str = Field(..., description="ISO timestamp of scrape")
    content_length: int = Field(..., description="Length of scraped content in characters")
    scrape_successful: bool = Field(..., description="Whether scraping succeeded")
    scrape_error: Optional[str] = Field(None, description="Error message if scraping failed")


class ExtractionResult(BaseModel):
    """Complete extraction result with metadata."""

    business_data: BusinessExtraction
    metadata: WebsiteMetadata
    tokens_used: int = Field(0, description="OpenAI tokens consumed")
    cost_usd: float = Field(0.0, description="API cost in USD")
    extraction_duration_sec: float = Field(0.0, description="Time taken for extraction")

    def has_staff_signal(self) -> bool:
        """Check if we got a usable staff count."""
        return self.business_data.staff_count is not None and self.business_data.staff_count > 0

    def has_founding_year(self) -> bool:
        """Check if we got founding year."""
        return self.business_data.founding_year is not None

    def get_quality_score(self) -> float:
        """
        Compute overall extraction quality score.

        Returns:
            Float 0.0 - 1.0 indicating extraction usefulness
        """
        score = 0.0

        # Staff count is most valuable (40%)
        if self.has_staff_signal():
            score += 0.4

        # Founding year is valuable (20%)
        if self.has_founding_year():
            score += 0.2

        # Facility size (10%)
        if self.business_data.facility_sqft:
            score += 0.1

        # Certifications (10%)
        if len(self.business_data.certifications) > 0:
            score += 0.1

        # Equipment mentions (10%)
        if len(self.business_data.equipment_mentions) > 0:
            score += 0.1

        # Services (10%)
        if len(self.business_data.services_offered) > 0:
            score += 0.1

        # Apply confidence modifier
        score *= self.business_data.confidence_score

        return score
