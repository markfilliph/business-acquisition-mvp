"""
Custom exceptions for the lead generation system.
"""


class LeadGenerationError(Exception):
    """Base exception for lead generation errors."""
    pass


class ValidationError(LeadGenerationError):
    """Raised when data validation fails."""
    pass


class DatabaseError(LeadGenerationError):
    """Raised when database operations fail."""
    pass


class HttpClientError(LeadGenerationError):
    """Raised when HTTP requests fail."""
    pass


class RateLimitError(HttpClientError):
    """Raised when rate limits are exceeded."""
    pass


class CircuitBreakerOpenError(HttpClientError):
    """Raised when circuit breaker is open."""
    pass


class DataSourceError(LeadGenerationError):
    """Raised when data source operations fail."""
    pass


class ScoringError(LeadGenerationError):
    """Raised when lead scoring fails."""
    pass


class ConfigurationError(LeadGenerationError):
    """Raised when configuration is invalid."""
    pass


class AutomationError(LeadGenerationError):
    """Raised when automation system operations fail."""
    pass


class MonitoringError(LeadGenerationError):
    """Raised when monitoring and alerting operations fail."""
    pass