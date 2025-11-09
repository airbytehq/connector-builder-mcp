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


logger = logging.getLogger(__name__)

_REGISTRY_URL = "https://connectors.airbyte.com/files/registries/v0/oss_registry.json"
_MANIFEST_ONLY_LANGUAGE = "manifest-only"
_HTTP_OK = 200


def _is_manifest_only_connector(connector_name: str) -> bool:
    """Check if a connector is manifest-only by querying the registry.

    Args:
        connector_name: Name of the connector (e.g., 'source-faker')

    Returns:
        True if the connector is manifest-only, False otherwise or on error
    """
    try:
        response = requests.get(_REGISTRY_URL, timeout=30)
        response.raise_for_status()
        registry_data = response.json()

        for connector_list in [
            registry_data.get("sources", []),
            registry_data.get("destinations", []),
        ]:
            for connector in connector_list:
                docker_repo = connector.get("dockerRepository", "")
                repo_connector_name = docker_repo.replace("airbyte/", "")

                if repo_connector_name == connector_name:
                    language = connector.get("language")
                    tags = connector.get("tags", [])

                    return (
                        language == _MANIFEST_ONLY_LANGUAGE
                        or f"language:{_MANIFEST_ONLY_LANGUAGE}" in tags
                    )

    except Exception as e:
        logger.warning(f"Failed to fetch registry data for {connector_name}: {e}")
        return False
    else:
        # No exception and no match found.
        logger.info(f"Connector {connector_name} was not found in the registry.")
        return False


def get_connector_manifest(
    connector_name: Annotated[
        str,
        Field(description="Name of the connector (e.g., 'source-stripe')"),
    ],
    version: Annotated[
        str,
        Field(
            description="Version of the connector manifest to retrieve. If not provided, defaults to 'latest'"
        ),
    ] = "latest",
) -> str:
    """Get the raw connector manifest YAML from connectors.airbyte.com.

    Args:
        connector_name: Name of the connector (e.g., 'source-stripe')
        version: Version of the connector manifest to retrieve (defaults to 'latest')

    Returns:
        Raw YAML content of the connector manifest
    """
    logger.info(f"Getting connector manifest for {connector_name} version {version}")

    cleaned_version = version.removeprefix("v")
    is_manifest_only = _is_manifest_only_connector(connector_name)

    logger.info(
        f"Connector {connector_name} is {'manifest-only' if is_manifest_only else 'not manifest-only'}."
    )
    if not is_manifest_only:
        return "ERROR: This connector is not manifest-only."

    manifest_url = f"https://connectors.airbyte.com/metadata/airbyte/{connector_name}/{cleaned_version}/manifest.yaml"

    try:
        response = requests.get(manifest_url, timeout=30)
        response.raise_for_status()

        return response.text

    except Exception as e:
        logger.error(f"Error fetching connector manifest for {connector_name}: {e}")
        return (
            f"# Error fetching manifest for connector '{connector_name}' version "
            f"'{version}' from {manifest_url}\n\nError: {str(e)}"
        )


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
    from connector_builder_mcp.mcp.guidance import (
        find_connectors_by_class_name,
        get_connector_builder_checklist,
        get_connector_builder_docs,
        get_manifest_yaml_json_schema,
    )
    from connector_builder_mcp.mcp.manifest_checks import validate_manifest
    from connector_builder_mcp.mcp.manifest_edits import (
        create_connector_manifest_scaffold,
        diff_session_manifest_versions,
        get_session_manifest_version,
        list_session_manifest_versions,
        register_session_manifest_tools,
        restore_session_manifest_version,
    )
    from connector_builder_mcp.mcp.manifest_tests import (
        execute_dynamic_manifest_resolution_test,
        execute_stream_test_read,
        run_connector_readiness_test_report,
    )
    from connector_builder_mcp.mcp.secrets_config import register_secrets_tools

    app.tool(get_manifest_yaml_json_schema)
    app.tool(get_connector_builder_checklist)
    app.tool(get_connector_builder_docs)
    app.tool(get_connector_manifest)
    app.tool(find_connectors_by_class_name)

    app.tool(validate_manifest)

    app.tool(execute_stream_test_read)
    app.tool(run_connector_readiness_test_report)
    app.tool(execute_dynamic_manifest_resolution_test)

    register_session_manifest_tools(app)

    register_secrets_tools(app)
