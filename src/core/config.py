"""
Production configuration management with environment-specific settings.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    path: str = "data/leads.db"
    connection_timeout: int = 30
    max_connections: int = 10
    backup_interval_hours: int = 24
    
    def __post_init__(self):
        # Ensure database directory exists
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)


@dataclass
class HttpConfig:
    """HTTP client configuration with rate limiting."""
    requests_per_minute: int = 30
    concurrent_requests: int = 5
    connection_timeout: int = 10
    read_timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 2.0
    respect_robots_txt: bool = True
    user_agent: str = "Hamilton Business Research Bot 2.0 (Ethical Crawler)"


@dataclass
class BusinessCriteria:
    """Target business criteria for lead qualification."""
    target_revenue_min: int = 800_000  # $800K
    target_revenue_max: int = 1_500_000  # $1.5M
    min_years_in_business: int = 15
    max_employee_count: int = 50
    target_locations: List[str] = field(default_factory=lambda: [
        "Hamilton", "Dundas", "Ancaster", "Stoney Creek", "Waterdown"
    ])
    target_industries: List[str] = field(default_factory=lambda: [
        "manufacturing", "wholesale", "professional_services",
        "printing", "equipment_rental"
    ])
    # EXCLUDED: All skilled trades (metal_fabrication, auto_repair, construction, welding, machining, etc.) - require special licenses
    
    # Major established companies to exclude (too large/established for our criteria)
    excluded_companies: List[str] = field(default_factory=lambda: [
        "G.S. Dunn Limited",
        "G.S. Dunn Ltd",
        "G.S. Dunn",
        "ArcelorMittal Dofasco",
        "Dofasco",
        "Stelco",
        "National Steel Car",
        "McMaster University",
        "Mohawk College",
        "Hamilton Health Sciences",
        "St. Joseph's Healthcare Hamilton"
    ])
    
    # Exclusion patterns (company names containing these will be excluded)
    excluded_patterns: List[str] = field(default_factory=lambda: [
        "university", "college", "hospital", "health sciences",
        "government", "municipal", "city of", "province of"
    ])


@dataclass
class ScoringWeights:
    """Lead scoring weights for qualification algorithm."""
    revenue_fit: int = 35
    business_age: int = 25
    data_quality: int = 15
    industry_fit: int = 10
    location_bonus: int = 8
    growth_indicators: int = 7
    qualification_threshold: int = 50


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"  # json or text
    file_path: str = "logs/lead_generation.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    
    def __post_init__(self):
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)


@dataclass
class SystemConfig:
    """Master system configuration."""
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    
    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    business_criteria: BusinessCriteria = field(default_factory=BusinessCriteria)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # API Keys (optional)
    api_keys: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "google_maps": os.getenv("GOOGLE_MAPS_API_KEY"),
        "bing_maps": os.getenv("BING_MAPS_API_KEY"),
        "serpapi": os.getenv("SERPAPI_KEY"),
        "hunter_io": os.getenv("HUNTER_IO_KEY"),
    })
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.environment == "production":
            # Production safety checks
            if self.http.requests_per_minute > 60:
                self.http.requests_per_minute = 60
            
            if self.debug:
                self.debug = False  # Never debug in production
            
            self.logging.level = "INFO"
        
        elif self.environment == "development":
            # Development optimizations
            self.http.requests_per_minute = 10  # Slower for development
            self.logging.level = "DEBUG"
    
    def is_production(self) -> bool:
        return self.environment == "production"
    
    def has_api_key(self, service: str) -> bool:
        return bool(self.api_keys.get(service))


# Global configuration instance
config = SystemConfig()


# Industry benchmarks based on Statistics Canada data
INDUSTRY_BENCHMARKS = {
    "manufacturing": {
        "revenue_per_employee": 165_000,
        "confidence_multiplier": 0.8,
        "typical_margins": 0.15,
        "employee_range": (8, 25),
        "growth_rate": 0.03
    },
    "wholesale": {
        "revenue_per_employee": 220_000,
        "confidence_multiplier": 0.7,
        "typical_margins": 0.12,
        "employee_range": (5, 18),
        "growth_rate": 0.025
    },
    "construction": {
        "revenue_per_employee": 185_000,
        "confidence_multiplier": 0.75,
        "typical_margins": 0.18,
        "employee_range": (6, 20),
        "growth_rate": 0.04
    },
    "professional_services": {
        "revenue_per_employee": 135_000,
        "confidence_multiplier": 0.6,
        "typical_margins": 0.25,
        "employee_range": (3, 15),
        "growth_rate": 0.05
    },
    "printing": {
        "revenue_per_employee": 140_000,
        "confidence_multiplier": 0.65,
        "typical_margins": 0.20,
        "employee_range": (5, 15),
        "growth_rate": 0.02
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