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


def filter_config_secrets(
    config: dict[str, Any] | list[Any] | Any,
) -> dict[str, Any] | list[Any] | Any:
    """Filter sensitive information from configuration for logging.

    Args:
        config: Configuration dictionary, list, or other value that may contain secrets

    Returns:
        Configuration with sensitive values masked
    """
    if isinstance(config, dict):
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
            if isinstance(value, dict | list):
                filtered[key] = filter_config_secrets(value)
            elif any(sensitive in key.lower() for sensitive in sensitive_keys):
                filtered[key] = "***REDACTED***"

        return filtered
    elif isinstance(config, list):
        return [filter_config_secrets(item) for item in config]
    else:
        return config


def validate_manifest_structure(manifest: dict[str, Any]) -> bool:
    """Basic validation of manifest structure.

    Args:
        manifest: Connector manifest dictionary

    Returns:
        True if manifest has required structure, False otherwise
    """
    required_fields = ["version", "type", "check", "streams"]
    return all(field in manifest for field in required_fields)
