"""Utility functions for Builder MCP server."""

import logging
import sys
from typing import Any


def initialize_logging() -> None:
    """Initialize logging configuration for the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


def filter_config_secrets(config: dict[str, Any]) -> dict[str, Any]:
    """Filter sensitive information from configuration for logging.

    Args:
        config: Configuration dictionary that may contain secrets

    Returns:
        Configuration dictionary with sensitive values masked
    """
    filtered = config.copy()
    sensitive_keys = {
        "password",
        "token",
        "key",
        "secret",
        "credential",
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
    }

    for key, value in filtered.items():
        if isinstance(value, dict):
            filtered[key] = filter_config_secrets(value)
        elif any(sensitive in key.lower() for sensitive in sensitive_keys):
            filtered[key] = "***REDACTED***"

    return filtered


def validate_manifest_structure(manifest: dict[str, Any]) -> bool:
    """Basic validation of manifest structure.

    Args:
        manifest: Connector manifest dictionary

    Returns:
        True if manifest has required structure, False otherwise
    """
    required_fields = ["version", "type", "check", "streams"]
    return all(field in manifest for field in required_fields)
