"""
Base class for all business data sources.

Provides common interface and tracking for source performance.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SourceMetrics:
    """Track performance metrics for a data source."""
    source_name: str
    businesses_found: int = 0
    validation_pass_rate: float = 0.0
    avg_data_quality: float = 0.0
    cost_per_lead: float = 0.0
    errors: int = 0
    last_run: Optional[datetime] = None
    run_count: int = 0
    total_fetch_time_seconds: float = 0.0


@dataclass
class BusinessData:
    """Standardized business data structure from any source."""
    name: str
    source: str
    source_url: str
    confidence: float  # 0.0-1.0 confidence in data accuracy

    # Optional fields
    street: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    industry: Optional[str] = None
    naics_code: Optional[str] = None
    employee_count: Optional[int] = None
    revenue_range: Optional[str] = None
    year_established: Optional[int] = None
    review_count: Optional[int] = None  # Number of online reviews (Google, Yelp, etc.)
    rating: Optional[float] = None  # Average rating (0.0-5.0)
    description: Optional[str] = None

    # Metadata
    raw_data: Dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'name': self.name,
            'source': self.source,
            'source_url': self.source_url,
            'confidence': self.confidence,
            'street': self.street,
            'city': self.city,
            'province': self.province,
            'postal_code': self.postal_code,
            'phone': self.phone,
            'website': self.website,
            'email': self.email,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'industry': self.industry,
            'naics_code': self.naics_code,
            'employee_count': self.employee_count,
            'revenue_range': self.revenue_range,
            'year_established': self.year_established,
            'review_count': self.review_count,
            'rating': self.rating,
            'description': self.description,
            'fetched_at': self.fetched_at.isoformat()
        }


class BaseBusinessSource(ABC):
    """
    Abstract base class for business data sources.

    All sources must implement:
    - fetch_businesses() - Main data fetching method
    - validate_config() - Check if source is properly configured
    """

    def __init__(self, name: str, priority: int = 50):
        """
        Initialize source.

        Args:
            name: Unique identifier for this source
            priority: Higher = checked first (0-100, default 50)
        """
        self.name = name
        self.priority = priority
        self.metrics = SourceMetrics(source_name=name)
        self.logger = logger.bind(source=name)

    @abstractmethod
    async def fetch_businesses(
        self,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None,
        max_results: int = 50
    ) -> List[BusinessData]:
        """
        Fetch businesses from this source.

        Args:
            location: Target location (city, region)
            industry: Industry filter (optional)
            max_results: Maximum number of results

        Returns:
            List of BusinessData objects
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that source is properly configured.

        Returns:
            True if ready to use, False otherwise
        """
        pass

    def is_available(self) -> bool:
        """Check if source is available for use."""
        return self.validate_config()

    def update_metrics(self, businesses_found: int, fetch_time: float, errors: int = 0):
        """Update source metrics after a run."""
        self.metrics.businesses_found += businesses_found
        self.metrics.errors += errors
        self.metrics.run_count += 1
        self.metrics.total_fetch_time_seconds += fetch_time
        self.metrics.last_run = datetime.utcnow()

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics as dictionary."""
        return {
            'source_name': self.metrics.source_name,
            'businesses_found': self.metrics.businesses_found,
            'validation_pass_rate': self.metrics.validation_pass_rate,
            'avg_data_quality': self.metrics.avg_data_quality,
            'cost_per_lead': self.metrics.cost_per_lead,
            'errors': self.metrics.errors,
            'last_run': self.metrics.last_run.isoformat() if self.metrics.last_run else None,
            'run_count': self.metrics.run_count,
            'total_fetch_time': self.metrics.total_fetch_time_seconds,
            'avg_fetch_time': (
                self.metrics.total_fetch_time_seconds / self.metrics.run_count
                if self.metrics.run_count > 0 else 0
            )
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(name={self.name}, priority={self.priority})>"
