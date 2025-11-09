"""MANIFEST_CHECKS domain tools - Validation that doesn't run the connector.

This module contains tools for validating manifest structure and syntax
without actually running the connector.
"""

from connector_builder_mcp.mcp.manifest_tests import validate_manifest


__all__ = ["validate_manifest"]
