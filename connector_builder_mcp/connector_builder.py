"""Builder MCP - Model Context Protocol server for Airbyte connector building.

This module provides the main registration function for all MCP tools,
organized by functional domain (guidance, manifest_checks, manifest_tests,
manifest_edits, secrets_config).
"""

import logging
from typing import Annotated

import requests
from fastmcp import FastMCP
from pydantic import Field
from connector_builder_mcp.mcp.guidance import register_guidance_tools
from connector_builder_mcp.mcp.manifest_checks import register_manifest_check_tools
from connector_builder_mcp.mcp.manifest_edits import register_manifest_edit_tools
from connector_builder_mcp.mcp.manifest_tests import register_manifest_test_tools
from connector_builder_mcp.mcp.secrets_config import register_secrets_tools

logger = logging.getLogger(__name__)

_REGISTRY_URL = "https://connectors.airbyte.com/files/registries/v0/oss_registry.json"
_MANIFEST_ONLY_LANGUAGE = "manifest-only"
_HTTP_OK = 200



def register_connector_builder_tools(app: FastMCP) -> None:
    """Register all connector builder tools with the FastMCP app.

    This function registers tools from all domains:
    - GUIDANCE: Checklist, docs, schema, find connectors
    - MANIFEST_CHECKS: Validation without running connector
    - MANIFEST_TESTS: Testing that runs the connector
    - MANIFEST_EDITS: Create, edit, manage manifests
    - SECRETS_CONFIG: Manage secrets and configuration

    Args:
        app: FastMCP application instance
    """
    register_guidance_tools(app)
    register_manifest_edit_tools(app)
    register_manifest_check_tools(app)
    register_manifest_test_tools(app)
    register_session_manifest_tools(app)
    register_secrets_tools(app)
    register_secrets_tools(app)
