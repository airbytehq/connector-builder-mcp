"""Tests for utility functions."""

from connector_builder_mcp._util import (
    filter_config_secrets,
    validate_manifest_structure,
)


class TestConfigSecretFiltering:
    """Test configuration secret filtering."""

    def test_filter_simple_secrets(self):
        """Test filtering of simple secret keys."""
        config = {
            "api_key": "secret123",
            "username": "user",
            "password": "pass123",
            "normal_field": "value",
        }

        filtered = filter_config_secrets(config)

        assert filtered["api_key"] == "***REDACTED***"
        assert filtered["password"] == "***REDACTED***"
        assert filtered["username"] == "user"
        assert filtered["normal_field"] == "value"

    def test_filter_nested_secrets(self):
        """Test filtering of secrets in nested dictionaries."""
        config = {
            "connection": {"api_key": "secret123", "host": "localhost"},
            "auth": {"token": "token123", "user": "testuser"},
        }

        filtered = filter_config_secrets(config)

        assert filtered["connection"]["api_key"] == "***REDACTED***"
        assert filtered["connection"]["host"] == "localhost"
        assert filtered["auth"]["token"] == "***REDACTED***"
        assert filtered["auth"]["user"] == "testuser"

    def test_filter_case_insensitive(self):
        """Test that secret filtering is case insensitive."""
        config = {"API_KEY": "secret123", "Client_Secret": "secret456", "ACCESS_TOKEN": "token789"}

        filtered = filter_config_secrets(config)

        assert filtered["API_KEY"] == "***REDACTED***"
        assert filtered["Client_Secret"] == "***REDACTED***"
        assert filtered["ACCESS_TOKEN"] == "***REDACTED***"


class TestManifestValidation:
    """Test manifest structure validation."""

    def test_valid_manifest_structure(self):
        """Test validation of valid manifest structure."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }

        assert validate_manifest_structure(manifest) is True

    def test_missing_required_fields(self):
        """Test validation fails for missing required fields."""
        manifest = {"version": "0.1.0", "type": "DeclarativeSource"}

        assert validate_manifest_structure(manifest) is False

    def test_empty_manifest(self):
        """Test validation fails for empty manifest."""
        manifest = {}

        assert validate_manifest_structure(manifest) is False
