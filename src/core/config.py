"""
Centralized configuration management with Pydantic validation.
PRIORITY: P1 - Critical for 12-factor config management.

Task 6: Centralized Config Management with fail-fast validation.
"""
import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

logger = structlog.get_logger(__name__)


class AppConfig(BaseSettings):
    """
    Application configuration with environment variable loading and validation.

    Uses Pydantic BaseSettings for:
    - Automatic .env file loading
    - Type validation
    - Fail-fast on missing required fields
    - Environment variable override

    All UPPERCASE fields are loaded from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields in .env
    )

    # ==================== API Keys ====================
    GOOGLE_PLACES_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Places API key for business discovery"
    )

    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for LLM extraction"
    )

    YELP_API_KEY: Optional[str] = Field(
        default=None,
        description="Yelp API key for business data enrichment"
    )

    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key (optional, for Claude)"
    )

    GEOAPIFY_API_KEY: Optional[str] = Field(
        default=None,
        description="Geoapify API key for Places API (free tier: 3,000 credits/day)"
    )

    # ==================== Rate Limits ====================
    GOOGLE_PLACES_RATE_LIMIT: float = Field(
        default=10.0,
        ge=0.1,
        le=100.0,
        description="Google Places API rate limit (requests/second)"
    )

    OPENAI_RATE_LIMIT: float = Field(
        default=0.83,  # 50 requests/minute
        ge=0.1,
        le=100.0,
        description="OpenAI API rate limit (requests/second)"
    )

    YELP_RATE_LIMIT: float = Field(
        default=5.0,
        ge=0.1,
        le=100.0,
        description="Yelp API rate limit (requests/second)"
    )

    WAYBACK_RATE_LIMIT: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Wayback Machine API rate limit (requests/second)"
    )

    # ==================== Business Criteria Thresholds ====================
    REVENUE_CONFIDENCE_THRESHOLD: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for revenue gate (0.0-1.0)"
    )

    TARGET_REVENUE_MIN: int = Field(
        default=800_000,
        ge=0,
        description="Minimum target revenue in USD"
    )

    TARGET_REVENUE_MAX: int = Field(
        default=1_500_000,
        ge=0,
        description="Maximum target revenue in USD ($1.5M hard cap for SMB thesis)"
    )

    MIN_EMPLOYEE_COUNT: int = Field(
        default=5,
        ge=1,
        description="Minimum employee count"
    )

    MAX_EMPLOYEE_COUNT: int = Field(
        default=25,
        ge=1,
        description="Maximum employee count (stricter SMB cap)"
    )

    MAX_REVIEW_COUNT: int = Field(
        default=30,
        ge=0,
        description="Maximum review count (30+ reviews suggests chain/brand/larger operation)"
    )

    MIN_YEARS_IN_BUSINESS: int = Field(
        default=15,
        ge=0,
        description="Minimum years in business"
    )

    WEBSITE_MIN_AGE_YEARS: float = Field(
        default=3.0,
        ge=0.0,
        description="Minimum website age in years (for sign shop filtering)"
    )

    # ==================== Geographic Settings ====================
    GEO_RADIUS_KM: float = Field(
        default=15.0,
        ge=1.0,
        le=100.0,
        description="Geographic radius for business discovery (kilometers)"
    )

    GEO_CENTER_LAT: float = Field(
        default=43.2557,
        ge=-90.0,
        le=90.0,
        description="Geographic center latitude (Hamilton, ON)"
    )

    GEO_CENTER_LNG: float = Field(
        default=-79.8711,
        ge=-180.0,
        le=180.0,
        description="Geographic center longitude (Hamilton, ON)"
    )

    ALLOWED_CITIES: List[str] = Field(
        default_factory=lambda: ["Hamilton", "Ancaster", "Dundas", "Stoney Creek", "Waterdown"],
        description="Allowed cities for lead generation (comma-separated in .env)"
    )

    @field_validator("ALLOWED_CITIES", mode="before")
    @classmethod
    def parse_allowed_cities(cls, v):
        """Parse comma-separated string from .env into list."""
        if isinstance(v, str):
            return [city.strip() for city in v.split(",") if city.strip()]
        return v

    # ==================== Retry & Resilience Config ====================
    RETRY_MAX_ATTEMPTS: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for failed requests"
    )

    RETRY_BASE_DELAY: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Base delay for exponential backoff (seconds)"
    )

    RETRY_MAX_DELAY: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Maximum delay for exponential backoff (seconds)"
    )

    CIRCUIT_BREAKER_THRESHOLD: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of failures before circuit breaker opens"
    )

    CIRCUIT_BREAKER_TIMEOUT: int = Field(
        default=60,
        ge=1,
        le=600,
        description="Circuit breaker recovery timeout (seconds)"
    )

    # ==================== Cache Settings ====================
    PLACES_CACHE_TTL: int = Field(
        default=2592000,  # 30 days
        ge=0,
        description="Places API cache TTL (seconds)"
    )

    LLM_CACHE_TTL: int = Field(
        default=7776000,  # 90 days
        ge=0,
        description="LLM extraction cache TTL (seconds)"
    )

    WAYBACK_CACHE_TTL: int = Field(
        default=2592000,  # 30 days
        ge=0,
        description="Wayback Machine cache TTL (seconds)"
    )

    # ==================== Database Settings ====================
    DATABASE_PATH: str = Field(
        default="data/leads.db",
        description="SQLite database path"
    )

    DATABASE_TIMEOUT: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Database connection timeout (seconds)"
    )

    DATABASE_MAX_CONNECTIONS: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum database connections"
    )

    # ==================== HTTP Settings ====================
    HTTP_TIMEOUT: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="HTTP request timeout (seconds)"
    )

    HTTP_USER_AGENT: str = Field(
        default="Hamilton Business Research Bot 2.0 (Ethical Crawler)",
        description="HTTP User-Agent header"
    )

    HTTP_MAX_RETRIES: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum HTTP retries"
    )

    # ==================== Environment ====================
    ENVIRONMENT: str = Field(
        default="development",
        description="Environment: development, staging, production"
    )

    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode"
    )

    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )

    # ==================== Validation Methods ====================
    @field_validator("REVENUE_CONFIDENCE_THRESHOLD")
    @classmethod
    def validate_threshold(cls, v):
        """Ensure threshold is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("REVENUE_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return v

    @field_validator("TARGET_REVENUE_MAX")
    @classmethod
    def validate_revenue_range(cls, v, info):
        """Ensure max revenue is greater than min revenue."""
        if "TARGET_REVENUE_MIN" in info.data:
            min_rev = info.data["TARGET_REVENUE_MIN"]
            if v <= min_rev:
                raise ValueError(f"TARGET_REVENUE_MAX ({v}) must be greater than TARGET_REVENUE_MIN ({min_rev})")
        return v

    @field_validator("MAX_EMPLOYEE_COUNT")
    @classmethod
    def validate_employee_range(cls, v, info):
        """Ensure max employees is greater than min employees."""
        if "MIN_EMPLOYEE_COUNT" in info.data:
            min_emp = info.data["MIN_EMPLOYEE_COUNT"]
            if v <= min_emp:
                raise ValueError(f"MAX_EMPLOYEE_COUNT ({v}) must be greater than MIN_EMPLOYEE_COUNT ({min_emp})")
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v):
        """Ensure environment is valid."""
        valid_environments = ["development", "staging", "production"]
        if v not in valid_environments:
            raise ValueError(f"ENVIRONMENT must be one of: {valid_environments}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {valid_levels}")
        return v_upper

    # ==================== Helper Methods ====================
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"

    def has_api_key(self, service: str) -> bool:
        """Check if API key is configured for a service."""
        key_map = {
            "google_places": self.GOOGLE_PLACES_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "yelp": self.YELP_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "geoapify": self.GEOAPIFY_API_KEY,
        }
        return bool(key_map.get(service))

    def get_database_path(self) -> Path:
        """Get database path as Path object."""
        path = Path(self.DATABASE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def log_config(self):
        """Log configuration summary (without sensitive data)."""
        logger.info(
            "configuration_loaded",
            environment=self.ENVIRONMENT,
            debug=self.DEBUG,
            log_level=self.LOG_LEVEL,
            geo_radius_km=self.GEO_RADIUS_KM,
            allowed_cities=self.ALLOWED_CITIES,
            revenue_threshold=self.REVENUE_CONFIDENCE_THRESHOLD,
            has_google_key=self.has_api_key("google_places"),
            has_openai_key=self.has_api_key("openai"),
            has_yelp_key=self.has_api_key("yelp"),
            has_geoapify_key=self.has_api_key("geoapify"),
        )


# ==================== Singleton Instance ====================
try:
    config = AppConfig()
    config.log_config()
except Exception as e:
    logger.error("configuration_failed", error=str(e))
    raise


# ==================== Industry Benchmarks (Static Data) ====================
INDUSTRY_BENCHMARKS = {
    "manufacturing": {
        "revenue_per_employee": 85_000,
        "confidence_multiplier": 0.8,
        "typical_margins": 0.15,
        "employee_range": (8, 25),
        "growth_rate": 0.03
    },
    "wholesale": {
        "revenue_per_employee": 95_000,
        "confidence_multiplier": 0.7,
        "typical_margins": 0.12,
        "employee_range": (5, 18),
        "growth_rate": 0.025
    },
    "construction": {
        "revenue_per_employee": 90_000,
        "confidence_multiplier": 0.75,
        "typical_margins": 0.18,
        "employee_range": (6, 20),
        "growth_rate": 0.04
    },
    "professional_services": {
        "revenue_per_employee": 100_000,
        "confidence_multiplier": 0.6,
        "typical_margins": 0.25,
        "employee_range": (3, 15),
        "growth_rate": 0.05
    },
    "printing": {
        "revenue_per_employee": 80_000,
        "confidence_multiplier": 0.65,
        "typical_margins": 0.20,
        "employee_range": (5, 15),
        "growth_rate": 0.02
    },
    "equipment_rental": {
        "revenue_per_employee": 110_000,
        "confidence_multiplier": 0.7,
        "typical_margins": 0.22,
        "employee_range": (4, 12),
        "growth_rate": 0.035
    }
}

# Hamilton area validation data
HAMILTON_POSTAL_CODES = {
    "L8E", "L8G", "L8H", "L8J", "L8K", "L8L", "L8M",
    "L8N", "L8P", "L8R", "L8S", "L8T", "L8V", "L8W",
    "L9A", "L9C", "L9G", "L9H"  # Including Ancaster/Dundas
}

HAMILTON_NEIGHBORHOODS = [
    "downtown hamilton", "east hamilton", "west hamilton", "mountain",
    "dundas", "ancaster", "stoney creek", "waterdown", "flamborough"
]
