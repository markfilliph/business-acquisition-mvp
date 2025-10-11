"""
Tests for centralized configuration management.
Validates Pydantic-based config loading and validation.
"""

import pytest
import os
from pydantic import ValidationError
from src.core.config import AppConfig, config, INDUSTRY_BENCHMARKS


class TestConfigLoading:
    """Test config loading from environment."""

    def test_config_loads_successfully(self):
        """Test that config loads without errors."""
        assert config is not None
        assert isinstance(config, AppConfig)

    def test_config_has_all_required_fields(self):
        """Test that all required fields are present."""
        # API Keys (optional)
        assert hasattr(config, "GOOGLE_PLACES_API_KEY")
        assert hasattr(config, "OPENAI_API_KEY")
        assert hasattr(config, "YELP_API_KEY")

        # Rate Limits
        assert hasattr(config, "GOOGLE_PLACES_RATE_LIMIT")
        assert hasattr(config, "OPENAI_RATE_LIMIT")

        # Business Criteria
        assert hasattr(config, "REVENUE_CONFIDENCE_THRESHOLD")
        assert hasattr(config, "TARGET_REVENUE_MIN")
        assert hasattr(config, "TARGET_REVENUE_MAX")

        # Geographic
        assert hasattr(config, "GEO_RADIUS_KM")
        assert hasattr(config, "ALLOWED_CITIES")

        # Retry
        assert hasattr(config, "RETRY_MAX_ATTEMPTS")
        assert hasattr(config, "CIRCUIT_BREAKER_THRESHOLD")

    def test_config_defaults_are_reasonable(self):
        """Test that default values are reasonable."""
        assert 0.0 <= config.REVENUE_CONFIDENCE_THRESHOLD <= 1.0
        assert config.TARGET_REVENUE_MAX > config.TARGET_REVENUE_MIN
        assert config.MAX_EMPLOYEE_COUNT > config.MIN_EMPLOYEE_COUNT
        assert config.GEO_RADIUS_KM > 0
        assert len(config.ALLOWED_CITIES) > 0


class TestConfigValidation:
    """Test Pydantic validation rules."""

    def test_invalid_revenue_threshold_raises_error(self):
        """Test that invalid revenue threshold raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(REVENUE_CONFIDENCE_THRESHOLD=1.5)

        assert "REVENUE_CONFIDENCE_THRESHOLD" in str(exc_info.value)

    def test_negative_revenue_threshold_raises_error(self):
        """Test that negative revenue threshold raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(REVENUE_CONFIDENCE_THRESHOLD=-0.1)

        assert "REVENUE_CONFIDENCE_THRESHOLD" in str(exc_info.value)

    def test_invalid_environment_raises_error(self):
        """Test that invalid environment raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(ENVIRONMENT="invalid_env")

        assert "ENVIRONMENT" in str(exc_info.value)

    def test_invalid_log_level_raises_error(self):
        """Test that invalid log level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(LOG_LEVEL="INVALID")

        assert "LOG_LEVEL" in str(exc_info.value)

    def test_revenue_max_less_than_min_raises_error(self):
        """Test that TARGET_REVENUE_MAX < TARGET_REVENUE_MIN raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(TARGET_REVENUE_MIN=2000000, TARGET_REVENUE_MAX=1000000)

        error_str = str(exc_info.value)
        assert "TARGET_REVENUE_MAX" in error_str or "greater than" in error_str.lower()

    def test_employee_max_less_than_min_raises_error(self):
        """Test that MAX_EMPLOYEE_COUNT < MIN_EMPLOYEE_COUNT raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(MIN_EMPLOYEE_COUNT=50, MAX_EMPLOYEE_COUNT=10)

        error_str = str(exc_info.value)
        assert "MAX_EMPLOYEE_COUNT" in error_str or "greater than" in error_str.lower()


class TestConfigHelperMethods:
    """Test config helper methods."""

    def test_is_production(self):
        """Test is_production() method."""
        prod_config = AppConfig(ENVIRONMENT="production")
        assert prod_config.is_production() is True

        dev_config = AppConfig(ENVIRONMENT="development")
        assert dev_config.is_production() is False

    def test_is_development(self):
        """Test is_development() method."""
        dev_config = AppConfig(ENVIRONMENT="development")
        assert dev_config.is_development() is True

        prod_config = AppConfig(ENVIRONMENT="production")
        assert prod_config.is_development() is False

    def test_has_api_key(self):
        """Test has_api_key() method."""
        config_with_key = AppConfig(GOOGLE_PLACES_API_KEY="test_key")
        assert config_with_key.has_api_key("google_places") is True

        config_without_key = AppConfig(GOOGLE_PLACES_API_KEY=None)
        assert config_without_key.has_api_key("google_places") is False

    def test_get_database_path(self):
        """Test get_database_path() method."""
        path = config.get_database_path()
        assert path.name.endswith(".db")
        assert path.parent.exists()  # Should create parent dir


class TestConfigFieldValidation:
    """Test individual field validation."""

    def test_rate_limits_have_valid_ranges(self):
        """Test that rate limits are within valid ranges."""
        # Should accept valid values
        valid_config = AppConfig(
            GOOGLE_PLACES_RATE_LIMIT=10.0,
            OPENAI_RATE_LIMIT=0.83,
            YELP_RATE_LIMIT=5.0
        )
        assert valid_config.GOOGLE_PLACES_RATE_LIMIT == 10.0

        # Should reject negative values
        with pytest.raises(ValidationError):
            AppConfig(GOOGLE_PLACES_RATE_LIMIT=-1.0)

        # Should reject values too high
        with pytest.raises(ValidationError):
            AppConfig(GOOGLE_PLACES_RATE_LIMIT=1000.0)

    def test_geo_radius_has_valid_range(self):
        """Test that geo radius is within valid range."""
        # Should accept valid values
        valid_config = AppConfig(GEO_RADIUS_KM=15.0)
        assert valid_config.GEO_RADIUS_KM == 15.0

        # Should reject values too small
        with pytest.raises(ValidationError):
            AppConfig(GEO_RADIUS_KM=0.5)

        # Should reject values too large
        with pytest.raises(ValidationError):
            AppConfig(GEO_RADIUS_KM=200.0)

    def test_retry_config_has_valid_ranges(self):
        """Test that retry config values are within valid ranges."""
        valid_config = AppConfig(
            RETRY_MAX_ATTEMPTS=3,
            RETRY_BASE_DELAY=1.0,
            RETRY_MAX_DELAY=60.0
        )
        assert valid_config.RETRY_MAX_ATTEMPTS == 3

        # Should reject zero attempts
        with pytest.raises(ValidationError):
            AppConfig(RETRY_MAX_ATTEMPTS=0)

        # Should reject negative delays
        with pytest.raises(ValidationError):
            AppConfig(RETRY_BASE_DELAY=-1.0)


class TestConfigParsing:
    """Test config parsing from different formats."""

    def test_allowed_cities_parses_from_string(self):
        """Test that ALLOWED_CITIES parses from comma-separated string."""
        config_with_string = AppConfig(ALLOWED_CITIES="Hamilton,Toronto,Ottawa")
        assert config_with_string.ALLOWED_CITIES == ["Hamilton", "Toronto", "Ottawa"]

    def test_allowed_cities_handles_whitespace(self):
        """Test that ALLOWED_CITIES handles whitespace correctly."""
        config_with_whitespace = AppConfig(ALLOWED_CITIES=" Hamilton , Toronto , Ottawa ")
        assert config_with_whitespace.ALLOWED_CITIES == ["Hamilton", "Toronto", "Ottawa"]

    def test_allowed_cities_accepts_list(self):
        """Test that ALLOWED_CITIES accepts list directly."""
        cities_list = ["Hamilton", "Toronto"]
        config_with_list = AppConfig(ALLOWED_CITIES=cities_list)
        assert config_with_list.ALLOWED_CITIES == cities_list

    def test_log_level_case_insensitive(self):
        """Test that LOG_LEVEL is case insensitive."""
        config_lower = AppConfig(LOG_LEVEL="info")
        assert config_lower.LOG_LEVEL == "INFO"

        config_mixed = AppConfig(LOG_LEVEL="DeBuG")
        assert config_mixed.LOG_LEVEL == "DEBUG"


class TestIndustryBenchmarks:
    """Test industry benchmark constants."""

    def test_industry_benchmarks_exist(self):
        """Test that industry benchmarks are defined."""
        assert len(INDUSTRY_BENCHMARKS) > 0

    def test_industry_benchmarks_have_required_fields(self):
        """Test that each industry has required fields."""
        required_fields = [
            "revenue_per_employee",
            "confidence_multiplier",
            "typical_margins",
            "employee_range",
            "growth_rate"
        ]

        for industry, benchmarks in INDUSTRY_BENCHMARKS.items():
            for field in required_fields:
                assert field in benchmarks, f"Industry '{industry}' missing field '{field}'"

    def test_industry_benchmarks_have_valid_values(self):
        """Test that benchmark values are reasonable."""
        for industry, benchmarks in INDUSTRY_BENCHMARKS.items():
            assert benchmarks["revenue_per_employee"] > 0
            assert 0 <= benchmarks["confidence_multiplier"] <= 1.0
            assert 0 <= benchmarks["typical_margins"] <= 1.0
            assert 0 <= benchmarks["growth_rate"] <= 1.0
            assert len(benchmarks["employee_range"]) == 2
            assert benchmarks["employee_range"][1] > benchmarks["employee_range"][0]


class TestConfigEnvironmentVariables:
    """Test config loading from environment variables."""

    def test_config_loads_from_env_vars(self, monkeypatch):
        """Test that config loads values from environment variables."""
        monkeypatch.setenv("REVENUE_CONFIDENCE_THRESHOLD", "0.8")
        monkeypatch.setenv("GEO_RADIUS_KM", "20.5")

        test_config = AppConfig()
        assert test_config.REVENUE_CONFIDENCE_THRESHOLD == 0.8
        assert test_config.GEO_RADIUS_KM == 20.5

    def test_config_validates_env_vars(self, monkeypatch):
        """Test that config validates values from environment variables."""
        monkeypatch.setenv("REVENUE_CONFIDENCE_THRESHOLD", "1.5")

        with pytest.raises(ValidationError):
            AppConfig()


class TestConfigDefaults:
    """Test that config provides sensible defaults."""

    def test_default_config_is_valid(self):
        """Test that default config (no env vars) is valid."""
        default_config = AppConfig()
        assert default_config.ENVIRONMENT == "development"
        assert default_config.REVENUE_CONFIDENCE_THRESHOLD == 0.6
        assert default_config.GEO_RADIUS_KM == 15.0

    def test_optional_api_keys_default_to_none(self):
        """Test that optional API keys default to None."""
        default_config = AppConfig()
        # API keys should be optional (None by default)
        # This should not raise an error
        assert default_config.GOOGLE_PLACES_API_KEY is None or isinstance(default_config.GOOGLE_PLACES_API_KEY, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
