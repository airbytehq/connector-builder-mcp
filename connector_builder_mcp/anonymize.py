"""Anonymization utilities for connector test data.

This module provides deterministic anonymization for API responses and records,
preserving structure while protecting sensitive information.
"""

import hashlib
import hmac
import os
import re
from typing import Any


def get_anonymization_salt() -> bytes:
    """Get the anonymization salt from environment variable.

    Returns:
        Salt bytes for HMAC operations

    Raises:
        ValueError: If MOCK_ANON_SALT environment variable is not set
    """
    salt = os.environ.get("MOCK_ANON_SALT")
    if not salt:
        raise ValueError(
            "MOCK_ANON_SALT environment variable must be set for anonymization. "
            "This ensures deterministic, reproducible anonymization across runs."
        )
    return salt.encode("utf-8")


def get_salt_id() -> str:
    """Get a short identifier for the current salt.

    Returns:
        First 8 characters of the salt's HMAC hash
    """
    salt = get_anonymization_salt()
    salt_hash = hmac.new(b"salt_id", salt, hashlib.sha256).hexdigest()
    return salt_hash[:8]


def anonymize_string(value: str, salt: bytes) -> str:
    """Anonymize a string value using HMAC-SHA256.

    Args:
        value: String to anonymize
        salt: Salt bytes for HMAC

    Returns:
        Anonymized string (hex digest truncated to 16 characters)
    """
    if not value:
        return value

    hashed = hmac.new(salt, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"anon_{hashed[:16]}"


def anonymize_email(email: str, salt: bytes) -> str:
    """Anonymize an email address while preserving format.

    Args:
        email: Email address to anonymize
        salt: Salt bytes for HMAC

    Returns:
        Anonymized email with format preserved (e.g., anon_abc123@example.com)
    """
    if not email or "@" not in email:
        return anonymize_string(email, salt)

    local_part, domain = email.rsplit("@", 1)
    anonymized_local = anonymize_string(local_part, salt)

    return f"{anonymized_local}@example.com"


def should_anonymize_field(field_name: str) -> bool:
    """Check if a field name suggests it contains sensitive data.

    Args:
        field_name: Field name to check

    Returns:
        True if field should be anonymized
    """
    sensitive_patterns = [
        r"id$",
        r"_id$",
        r"email",
        r"phone",
        r"ssn",
        r"social_security",
        r"credit_card",
        r"account",
        r"customer",
        r"user",
        r"name$",
        r"address",
    ]

    field_lower = field_name.lower()
    return any(re.search(pattern, field_lower) for pattern in sensitive_patterns)


def anonymize_value(value: Any, field_name: str, salt: bytes) -> Any:
    """Anonymize a value based on its type and field name.

    Args:
        value: Value to potentially anonymize
        field_name: Name of the field (used to determine if anonymization needed)
        salt: Salt bytes for HMAC

    Returns:
        Anonymized value or original value if anonymization not needed
    """
    if value is None:
        return value

    if not should_anonymize_field(field_name):
        return value

    if isinstance(value, str):
        if "@" in value and "." in value.split("@")[-1]:
            return anonymize_email(value, salt)
        return anonymize_string(value, salt)

    return value


def anonymize_dict(data: dict[str, Any], salt: bytes) -> dict[str, Any]:
    """Recursively anonymize dictionary values.

    Args:
        data: Dictionary to anonymize
        salt: Salt bytes for HMAC

    Returns:
        New dictionary with anonymized values
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = anonymize_dict(value, salt)
        elif isinstance(value, list):
            anonymized_list: list[Any] = [
                anonymize_dict(item, salt)
                if isinstance(item, dict)
                else anonymize_value(item, key, salt)
                for item in value
            ]
            result[key] = anonymized_list
        else:
            result[key] = anonymize_value(value, key, salt)

    return result


def anonymize_headers(headers: dict[str, Any], salt: bytes) -> dict[str, Any]:
    """Anonymize HTTP headers by redacting sensitive values.

    Args:
        headers: HTTP headers dictionary
        salt: Salt bytes for HMAC

    Returns:
        New dictionary with sensitive headers redacted
    """
    sensitive_headers = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "x-auth-token",
        "auth-token",
    }

    volatile_headers = {
        "date",
        "x-request-id",
        "request-id",
        "x-trace-id",
        "trace-id",
        "x-correlation-id",
    }

    result = {}
    for key, value in headers.items():
        key_lower = key.lower()

        if key_lower in volatile_headers:
            continue

        if key_lower in sensitive_headers:
            result[key] = "***REDACTED***"
        else:
            result[key] = value

    return result


def anonymize_query_params(params: dict[str, Any], salt: bytes) -> dict[str, Any]:
    """Anonymize query parameters by redacting sensitive values.

    Args:
        params: Query parameters dictionary
        salt: Salt bytes for HMAC

    Returns:
        New dictionary with sensitive parameters redacted
    """
    sensitive_param_patterns = [
        r"token",
        r"key",
        r"secret",
        r"password",
        r"pwd",
        r"auth",
        r"api",
        r"access",
    ]

    result = {}
    for key, value in params.items():
        key_lower = key.lower()

        is_sensitive = any(re.search(pattern, key_lower) for pattern in sensitive_param_patterns)

        if is_sensitive:
            result[key] = "***REDACTED***"
        else:
            result[key] = value

    return result


def anonymize_http_interaction(interaction: dict[str, Any]) -> dict[str, Any]:
    """Anonymize an HTTP request/response interaction.

    Args:
        interaction: HTTP interaction dictionary with request and response

    Returns:
        New dictionary with anonymized interaction
    """
    salt = get_anonymization_salt()
    result = dict(interaction)

    if "request" in result and isinstance(result["request"], dict):
        request = dict(result["request"])

        if "headers" in request and isinstance(request["headers"], dict):
            request["headers"] = anonymize_headers(request["headers"], salt)

        if "query" in request and isinstance(request["query"], dict):
            request["query"] = anonymize_query_params(request["query"], salt)

        if "body_json" in request and isinstance(request["body_json"], dict):
            request["body_json"] = anonymize_dict(request["body_json"], salt)

        result["request"] = request

    if "response" in result and isinstance(result["response"], dict):
        response = dict(result["response"])

        if "headers" in response and isinstance(response["headers"], dict):
            response["headers"] = anonymize_headers(response["headers"], salt)

        if "body_json" in response and isinstance(response["body_json"], dict):
            response["body_json"] = anonymize_dict(response["body_json"], salt)

        result["response"] = response

    return result


def anonymize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anonymize a list of record dictionaries.

    Args:
        records: List of record dictionaries

    Returns:
        New list with anonymized records
    """
    salt = get_anonymization_salt()
    return [anonymize_dict(record, salt) for record in records]
