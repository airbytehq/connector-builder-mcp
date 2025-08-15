#!/usr/bin/env python3
"""Test script for the create_manifest_yaml_scaffold function."""

import os
import sys


# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from connector_builder_mcp._connector_builder import create_manifest_yaml_scaffold


def test_scaffold_generation():
    """Test the scaffold generation function."""
    result = create_manifest_yaml_scaffold(
        api_name="Test API",
        stream_name="users",
        endpoint="/users",
        url_root="https://api.example.com",
        auth_method="api_key",
    )

    print("Generated YAML manifest:")
    print("=" * 50)
    print(result)
    print("=" * 50)

    # Basic validation
    assert "Test API" in result
    assert "users" in result
    assert "https://api.example.com" in result
    assert "ApiKeyAuthenticator" in result
    assert "api_key" in result
    print("✅ Basic validation passed!")


if __name__ == "__main__":
    test_scaffold_generation()
