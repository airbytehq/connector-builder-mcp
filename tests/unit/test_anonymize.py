"""Tests for anonymization utilities."""

import os
from unittest.mock import patch

import pytest

from connector_builder_mcp.anonymize import (
    anonymize_dict,
    anonymize_email,
    anonymize_headers,
    anonymize_http_interaction,
    anonymize_query_params,
    anonymize_records,
    anonymize_string,
    anonymize_value,
    get_anonymization_salt,
    get_salt_id,
    should_anonymize_field,
)


class TestAnonymizationSalt:
    """Tests for salt management."""

    def test_get_anonymization_salt_missing_env_var(self):
        """Test that missing MOCK_ANON_SALT raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MOCK_ANON_SALT environment variable must be set"):
                get_anonymization_salt()

    def test_get_anonymization_salt_returns_bytes(self):
        """Test that get_anonymization_salt returns bytes."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_123"}):
            salt = get_anonymization_salt()
            assert isinstance(salt, bytes)
            assert salt == b"test_salt_123"

    def test_get_salt_id_returns_string(self):
        """Test that get_salt_id returns a short string identifier."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_123"}):
            salt_id = get_salt_id()
            assert isinstance(salt_id, str)
            assert len(salt_id) == 8

    def test_get_salt_id_deterministic(self):
        """Test that get_salt_id returns same value for same salt."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_123"}):
            salt_id_1 = get_salt_id()
            salt_id_2 = get_salt_id()
            assert salt_id_1 == salt_id_2


class TestAnonymizeString:
    """Tests for string anonymization."""

    def test_anonymize_string_basic(self):
        """Test basic string anonymization."""
        salt = b"test_salt"
        result = anonymize_string("test_value", salt)
        assert result.startswith("anon_")
        assert len(result) == 21  # "anon_" + 16 hex chars

    def test_anonymize_string_deterministic(self):
        """Test that same input produces same output."""
        salt = b"test_salt"
        result1 = anonymize_string("test_value", salt)
        result2 = anonymize_string("test_value", salt)
        assert result1 == result2

    def test_anonymize_string_different_inputs(self):
        """Test that different inputs produce different outputs."""
        salt = b"test_salt"
        result1 = anonymize_string("value1", salt)
        result2 = anonymize_string("value2", salt)
        assert result1 != result2

    def test_anonymize_string_empty(self):
        """Test that empty string returns empty string."""
        salt = b"test_salt"
        result = anonymize_string("", salt)
        assert result == ""


class TestAnonymizeEmail:
    """Tests for email anonymization."""

    def test_anonymize_email_basic(self):
        """Test basic email anonymization."""
        salt = b"test_salt"
        result = anonymize_email("user@example.com", salt)
        assert "@example.com" in result
        assert result.startswith("anon_")

    def test_anonymize_email_deterministic(self):
        """Test that same email produces same output."""
        salt = b"test_salt"
        result1 = anonymize_email("user@example.com", salt)
        result2 = anonymize_email("user@example.com", salt)
        assert result1 == result2

    def test_anonymize_email_different_domains_normalized(self):
        """Test that different domains are normalized to example.com."""
        salt = b"test_salt"
        result1 = anonymize_email("user@gmail.com", salt)
        result2 = anonymize_email("user@yahoo.com", salt)
        assert "@example.com" in result1
        assert "@example.com" in result2
        assert result1.split("@")[0] == result2.split("@")[0]

    def test_anonymize_email_invalid_format(self):
        """Test that invalid email format falls back to string anonymization."""
        salt = b"test_salt"
        result = anonymize_email("not_an_email", salt)
        assert result.startswith("anon_")
        assert "@" not in result


class TestShouldAnonymizeField:
    """Tests for field name detection."""

    def test_should_anonymize_id_fields(self):
        """Test that ID fields are detected."""
        assert should_anonymize_field("user_id")
        assert should_anonymize_field("customer_id")
        assert should_anonymize_field("id")
        assert should_anonymize_field("userId")

    def test_should_anonymize_email_fields(self):
        """Test that email fields are detected."""
        assert should_anonymize_field("email")
        assert should_anonymize_field("user_email")
        assert should_anonymize_field("Email")

    def test_should_anonymize_name_fields(self):
        """Test that name fields are detected."""
        assert should_anonymize_field("name")
        assert should_anonymize_field("user_name")
        assert should_anonymize_field("customer_name")

    def test_should_not_anonymize_safe_fields(self):
        """Test that safe fields are not detected."""
        assert not should_anonymize_field("created_at")
        assert not should_anonymize_field("updated_at")
        assert not should_anonymize_field("count")
        assert not should_anonymize_field("status")
        assert not should_anonymize_field("type")


class TestAnonymizeValue:
    """Tests for value anonymization."""

    def test_anonymize_value_sensitive_field(self):
        """Test that sensitive field values are anonymized."""
        salt = b"test_salt"
        result = anonymize_value("12345", "user_id", salt)
        assert result.startswith("anon_")

    def test_anonymize_value_email_field(self):
        """Test that email field values are anonymized with format preservation."""
        salt = b"test_salt"
        result = anonymize_value("user@example.com", "email", salt)
        assert "@example.com" in result
        assert result.startswith("anon_")

    def test_anonymize_value_non_sensitive_field(self):
        """Test that non-sensitive field values are not anonymized."""
        salt = b"test_salt"
        result = anonymize_value("active", "status", salt)
        assert result == "active"

    def test_anonymize_value_none(self):
        """Test that None values are preserved."""
        salt = b"test_salt"
        result = anonymize_value(None, "user_id", salt)
        assert result is None

    def test_anonymize_value_non_string(self):
        """Test that non-string values are preserved."""
        salt = b"test_salt"
        result = anonymize_value(12345, "user_id", salt)
        assert result == 12345


class TestAnonymizeDict:
    """Tests for dictionary anonymization."""

    def test_anonymize_dict_basic(self):
        """Test basic dictionary anonymization."""
        salt = b"test_salt"
        data = {
            "user_id": "12345",
            "email": "user@example.com",
            "status": "active",
        }
        result = anonymize_dict(data, salt)
        assert result["user_id"].startswith("anon_")
        assert "@example.com" in result["email"]
        assert result["status"] == "active"

    def test_anonymize_dict_nested(self):
        """Test nested dictionary anonymization."""
        salt = b"test_salt"
        data = {
            "user": {
                "user_id": "12345",
                "email": "user@example.com",
            },
            "status": "active",
        }
        result = anonymize_dict(data, salt)
        assert result["user"]["user_id"].startswith("anon_")
        assert "@example.com" in result["user"]["email"]
        assert result["status"] == "active"

    def test_anonymize_dict_with_list(self):
        """Test dictionary with list values."""
        salt = b"test_salt"
        data = {
            "users": [
                {"user_id": "123", "name": "Alice"},
                {"user_id": "456", "name": "Bob"},
            ]
        }
        result = anonymize_dict(data, salt)
        assert len(result["users"]) == 2
        assert result["users"][0]["user_id"].startswith("anon_")
        assert result["users"][1]["user_id"].startswith("anon_")


class TestAnonymizeHeaders:
    """Tests for HTTP header anonymization."""

    def test_anonymize_headers_sensitive(self):
        """Test that sensitive headers are redacted."""
        salt = b"test_salt"
        headers = {
            "Authorization": "Bearer token123",
            "Cookie": "session=abc123",
            "Content-Type": "application/json",
        }
        result = anonymize_headers(headers, salt)
        assert result["Authorization"] == "***REDACTED***"
        assert result["Cookie"] == "***REDACTED***"
        assert result["Content-Type"] == "application/json"

    def test_anonymize_headers_volatile(self):
        """Test that volatile headers are removed."""
        salt = b"test_salt"
        headers = {
            "Date": "Mon, 28 Oct 2024 12:00:00 GMT",
            "X-Request-Id": "req-123",
            "Content-Type": "application/json",
        }
        result = anonymize_headers(headers, salt)
        assert "Date" not in result
        assert "X-Request-Id" not in result
        assert result["Content-Type"] == "application/json"

    def test_anonymize_headers_case_insensitive(self):
        """Test that header matching is case-insensitive."""
        salt = b"test_salt"
        headers = {
            "authorization": "Bearer token123",
            "COOKIE": "session=abc123",
        }
        result = anonymize_headers(headers, salt)
        assert result["authorization"] == "***REDACTED***"
        assert result["COOKIE"] == "***REDACTED***"


class TestAnonymizeQueryParams:
    """Tests for query parameter anonymization."""

    def test_anonymize_query_params_sensitive(self):
        """Test that sensitive query params are redacted."""
        salt = b"test_salt"
        params = {
            "api_key": "key123",
            "access_token": "token456",
            "page": "1",
        }
        result = anonymize_query_params(params, salt)
        assert result["api_key"] == "***REDACTED***"
        assert result["access_token"] == "***REDACTED***"
        assert result["page"] == "1"

    def test_anonymize_query_params_patterns(self):
        """Test various sensitive parameter patterns."""
        salt = b"test_salt"
        params = {
            "secret": "sec123",
            "password": "pass123",
            "auth": "auth123",
            "limit": "10",
        }
        result = anonymize_query_params(params, salt)
        assert result["secret"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"
        assert result["auth"] == "***REDACTED***"
        assert result["limit"] == "10"


class TestAnonymizeHttpInteraction:
    """Tests for HTTP interaction anonymization."""

    def test_anonymize_http_interaction_request(self):
        """Test request anonymization."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt"}):
            interaction = {
                "request": {
                    "headers": {"Authorization": "Bearer token123"},
                    "query": {"api_key": "key123", "page": "1"},
                    "body_json": {"user_id": "12345"},
                }
            }
            result = anonymize_http_interaction(interaction)
            assert result["request"]["headers"]["Authorization"] == "***REDACTED***"
            assert result["request"]["query"]["api_key"] == "***REDACTED***"
            assert result["request"]["query"]["page"] == "1"
            assert result["request"]["body_json"]["user_id"].startswith("anon_")

    def test_anonymize_http_interaction_response(self):
        """Test response anonymization."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt"}):
            interaction = {
                "response": {
                    "headers": {"Set-Cookie": "session=abc123"},
                    "body_json": {
                        "user_id": "12345",
                        "email": "user@example.com",
                        "status": "active",
                    },
                }
            }
            result = anonymize_http_interaction(interaction)
            assert result["response"]["headers"]["Set-Cookie"] == "***REDACTED***"
            assert result["response"]["body_json"]["user_id"].startswith("anon_")
            assert "@example.com" in result["response"]["body_json"]["email"]
            assert result["response"]["body_json"]["status"] == "active"

    def test_anonymize_http_interaction_both(self):
        """Test full interaction anonymization."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt"}):
            interaction = {
                "request": {
                    "headers": {"Authorization": "Bearer token123"},
                },
                "response": {
                    "body_json": {"user_id": "12345"},
                },
            }
            result = anonymize_http_interaction(interaction)
            assert result["request"]["headers"]["Authorization"] == "***REDACTED***"
            assert result["response"]["body_json"]["user_id"].startswith("anon_")


class TestAnonymizeRecords:
    """Tests for record list anonymization."""

    def test_anonymize_records_basic(self):
        """Test basic record list anonymization."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt"}):
            records = [
                {"user_id": "123", "email": "user1@example.com", "status": "active"},
                {"user_id": "456", "email": "user2@example.com", "status": "inactive"},
            ]
            result = anonymize_records(records)
            assert len(result) == 2
            assert result[0]["user_id"].startswith("anon_")
            assert "@example.com" in result[0]["email"]
            assert result[0]["status"] == "active"
            assert result[1]["user_id"].startswith("anon_")
            assert "@example.com" in result[1]["email"]
            assert result[1]["status"] == "inactive"

    def test_anonymize_records_deterministic(self):
        """Test that same records produce same anonymized output."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt"}):
            records = [{"user_id": "123", "email": "user@example.com"}]
            result1 = anonymize_records(records)
            result2 = anonymize_records(records)
            assert result1[0]["user_id"] == result2[0]["user_id"]
            assert result1[0]["email"] == result2[0]["email"]

    def test_anonymize_records_empty(self):
        """Test that empty list returns empty list."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt"}):
            result = anonymize_records([])
            assert result == []
