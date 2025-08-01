"""Connector builder MCP tools.

This module provides MCP tools for connector building operations, including
manifest validation, stream testing, and configuration management.
"""

import logging
from typing import Annotated, Any, Literal

import requests
from airbyte_cdk.connector_builder.connector_builder_handler import (
    TestLimits,
    create_source,
    get_limits,
    read_stream,
    resolve_manifest,
)
from airbyte_cdk.models import ConfiguredAirbyteCatalog
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from builder_mcp._util import validate_manifest_structure

logger = logging.getLogger(__name__)


class ManifestValidationResult(BaseModel):
    """Result of manifest validation operation."""

    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    resolved_manifest: dict[str, Any] | None = None


class StreamTestResult(BaseModel):
    """Result of stream testing operation."""

    success: bool
    message: str
    records_read: int = 0
    errors: list[str] = []


def validate_manifest(
    manifest: Annotated[
        dict[str, Any],
        Field(description="The connector manifest to validate"),
    ],
    config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional connector configuration for validation"),
    ] = None,
) -> ManifestValidationResult:
    """Validate a connector manifest structure and configuration.

    Args:
        manifest: The connector manifest dictionary to validate
        config: Optional configuration to use for validation

    Returns:
        Validation result with success status and any errors/warnings
    """
    logger.info("Validating connector manifest")

    errors: list[str] = []
    warnings: list[str] = []
    resolved_manifest = None

    try:
        if not validate_manifest_structure(manifest):
            errors.append("Manifest missing required fields: version, type, check, streams")
            return ManifestValidationResult(is_valid=False, errors=errors, warnings=warnings)

        if config is None:
            config = {}

        config_with_manifest = {**config, "__injected_declarative_manifest": manifest}

        limits = get_limits(config_with_manifest)
        source = create_source(config_with_manifest, limits)

        resolve_result = resolve_manifest(source)
        if (
            resolve_result.type.value == "RECORD"
            and resolve_result.record is not None
            and resolve_result.record.data is not None
        ):
            resolved_manifest = resolve_result.record.data.get("manifest")
        else:
            errors.append("Failed to resolve manifest")

    except Exception as e:
        logger.error(f"Error validating manifest: {e}")
        errors.append(f"Validation error: {str(e)}")

    is_valid = len(errors) == 0

    return ManifestValidationResult(
        is_valid=is_valid, errors=errors, warnings=warnings, resolved_manifest=resolved_manifest
    )


def execute_stream_read(
    manifest: Annotated[
        dict[str, Any],
        Field(description="The connector manifest"),
    ],
    config: Annotated[
        dict[str, Any],
        Field(description="Connector configuration"),
    ],
    stream_name: Annotated[
        str,
        Field(description="Name of the stream to test"),
    ],
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read", ge=1, le=1000),
    ] = 10,
) -> StreamTestResult:
    """Execute reading from a connector stream.

    Args:
        manifest: The connector manifest
        config: Connector configuration
        stream_name: Name of the stream to test
        max_records: Maximum number of records to read

    Returns:
        Test result with success status and details
    """
    logger.info(f"Testing stream read for stream: {stream_name}")

    try:
        config_with_manifest = {
            **config,
            "__injected_declarative_manifest": manifest,
            "__test_read_config": {
                "max_records": max_records,
                "max_pages_per_slice": 1,
                "max_slices": 1,
                "max_streams": 1,
            },
        }

        limits = get_limits(config_with_manifest)
        source = create_source(config_with_manifest, limits)

        catalog = ConfiguredAirbyteCatalog(streams=[])

        result = read_stream(source, config_with_manifest, catalog, [], limits)

        if result.type.value == "RECORD":
            return StreamTestResult(
                success=True,
                message=f"Successfully read from stream {stream_name}",
                records_read=max_records,
            )
        else:
            error_msg = "Failed to read from stream"
            if hasattr(result, "trace") and result.trace:
                error_msg = result.trace.error.message

            return StreamTestResult(success=False, message=error_msg, errors=[error_msg])

    except Exception as e:
        logger.error(f"Error testing stream read: {e}")
        error_msg = f"Stream test error: {str(e)}"
        return StreamTestResult(success=False, message=error_msg, errors=[error_msg])


def get_resolved_manifest(
    manifest: Annotated[
        dict[str, Any],
        Field(description="The connector manifest to resolve"),
    ],
    config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional connector configuration"),
    ] = None,
) -> dict[str, Any] | Literal["Failed to resolve manifest"]:
    """Get the resolved connector manifest.

    Args:
        manifest: The connector manifest to resolve
        config: Optional configuration for resolution

    Returns:
        Resolved manifest or error message
    """
    logger.info("Getting resolved manifest")

    try:
        if config is None:
            config = {}

        config_with_manifest = {**config, "__injected_declarative_manifest": manifest}

        limits = TestLimits(max_records=10, max_pages_per_slice=1, max_slices=1)

        source = create_source(config_with_manifest, limits)
        result = resolve_manifest(source)

        if (
            result.type.value == "RECORD"
            and result.record is not None
            and result.record.data is not None
        ):
            manifest_data = result.record.data.get("manifest", {})
            if isinstance(manifest_data, dict):
                return manifest_data
            return {}
        else:
            return "Failed to resolve manifest"

    except Exception as e:
        logger.error(f"Error resolving manifest: {e}")
        return "Failed to resolve manifest"


def get_connector_builder_docs(
    topic: Annotated[
        str | None,
        Field(
            description="Specific YAML reference topic to get detailed documentation for. If not provided, returns high-level overview and topic list."
        ),
    ] = None,
) -> str:
    """Get connector builder documentation and guidance.

    Args:
        topic: Optional specific topic from YAML reference documentation

    Returns:
        High-level overview with topic list, or detailed topic-specific documentation
    """
    logger.info(f"Getting connector builder docs for topic: {topic}")

    if topic is None:
        return _get_high_level_overview()
    else:
        return _get_topic_specific_docs(topic)


def _get_high_level_overview() -> str:
    """Return high-level connector building process and available topics."""
    overview = """# Connector Builder Documentation

1. Use the manifest YAML JSON schema for high-level guidelines
2. Use the validate manifest tool to confirm JSON schema is correct
3. Start with one stream or (better) a stream template that maps to a single stream
4. Make sure you have working authentication and data retrieval before moving onto pagination and other components
5. When all is confirmed working on the first stream, you can add additional streams. It is generally safest to add one stream at a time, and test each one before moving to the next

- `validate_manifest`: Validate connector manifest structure and configuration
- `execute_stream_read`: Test reading from a connector stream
- `get_resolved_manifest`: Get the resolved connector manifest

We use the Declarative YAML Connector convention for building connectors. Note that we don't yet support custom Python components.

For detailed documentation on specific components, request one of these topics:

- overview - Connector Builder overview and introduction
- tutorial - Step-by-step tutorial for building connectors
- authentication - Authentication configuration
- incremental-sync - Setting up incremental data synchronization
- pagination - Handling paginated API responses
- partitioning - Configuring partition routing for complex APIs
- record-processing - Processing and transforming records
- error-handling - Handling API errors and retries
- ai-assist - Using AI assistance in the Connector Builder
- stream-templates - Using stream templates for faster development
- custom-components - Working with custom components
- async-streams - Configuring asynchronous streams

- yaml-overview - Understanding the YAML file structure
- reference - Complete YAML reference documentation
- yaml-incremental-syncs - Incremental sync configuration in YAML
- yaml-pagination - Pagination configuration options
- yaml-partition-router - Partition routing in YAML manifests
- yaml-record-selector - Record selection and transformation
- yaml-error-handling - Error handling configuration
- yaml-authentication - Authentication methods in YAML
- requester - HTTP requester configuration
- request-options - Request parameter configuration
- rate-limit-api-budget - Rate limiting and API budget management
- file-syncing - File synchronization configuration
- property-chunking - Property chunking for large datasets

For detailed information on any topic, call this function again with the topic name.
"""
    return overview


def _get_topic_specific_docs(topic: str) -> str:
    """Get detailed documentation for a specific topic using raw GitHub URLs."""
    logger.info(f"Fetching detailed docs for topic: {topic}")

    topic_mapping = {
        "overview": ("docs/platform/connector-development/connector-builder-ui/overview.md", "md"),
        "tutorial": (
            "docs/platform/connector-development/connector-builder-ui/tutorial.mdx",
            "mdx",
        ),
        "authentication": (
            "docs/platform/connector-development/connector-builder-ui/authentication.md",
            "md",
        ),
        "incremental-sync": (
            "docs/platform/connector-development/connector-builder-ui/incremental-sync.md",
            "md",
        ),
        "pagination": (
            "docs/platform/connector-development/connector-builder-ui/pagination.md",
            "md",
        ),
        "partitioning": (
            "docs/platform/connector-development/connector-builder-ui/partitioning.md",
            "md",
        ),
        "record-processing": (
            "docs/platform/connector-development/connector-builder-ui/record-processing.mdx",
            "mdx",
        ),
        "error-handling": (
            "docs/platform/connector-development/connector-builder-ui/error-handling.md",
            "md",
        ),
        "ai-assist": (
            "docs/platform/connector-development/connector-builder-ui/ai-assist.md",
            "md",
        ),
        "stream-templates": (
            "docs/platform/connector-development/connector-builder-ui/stream-templates.md",
            "md",
        ),
        "custom-components": (
            "docs/platform/connector-development/connector-builder-ui/custom-components.md",
            "md",
        ),
        "async-streams": (
            "docs/platform/connector-development/connector-builder-ui/async-streams.md",
            "md",
        ),
        "yaml-overview": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/yaml-overview.md",
            "md",
        ),
        "reference": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/reference.md",
            "md",
        ),
        "yaml-incremental-syncs": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/incremental-syncs.md",
            "md",
        ),
        "yaml-pagination": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/pagination.md",
            "md",
        ),
        "yaml-partition-router": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/partition-router.md",
            "md",
        ),
        "yaml-record-selector": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/record-selector.md",
            "md",
        ),
        "yaml-error-handling": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/error-handling.md",
            "md",
        ),
        "yaml-authentication": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/authentication.md",
            "md",
        ),
        "requester": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/requester.md",
            "md",
        ),
        "request-options": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/request-options.md",
            "md",
        ),
        "rate-limit-api-budget": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/rate-limit-api-budget.md",
            "md",
        ),
        "file-syncing": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/file-syncing.md",
            "md",
        ),
        "property-chunking": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/property-chunking.md",
            "md",
        ),
    }

    if topic not in topic_mapping:
        return f"# {topic} Documentation\n\nTopic '{topic}' not found. Please check the available topics list from the overview.\n\nAvailable topics: {', '.join(topic_mapping.keys())}"

    relative_path, file_ext = topic_mapping[topic]
    raw_github_url = f"https://raw.githubusercontent.com/airbytehq/airbyte/master/{relative_path}"

    try:
        response = requests.get(raw_github_url, timeout=30)
        response.raise_for_status()

        markdown_content = response.text
        return f"# {topic} Documentation\n\n{markdown_content}"

    except Exception as e:
        logger.error(f"Error fetching documentation for topic {topic}: {e}")
        docs_url = f"https://docs.airbyte.com/platform/connector-development/config-based/understanding-the-yaml-file/{topic}"
        return f"# {topic} Documentation\n\nUnable to fetch detailed documentation from GitHub. Please refer to the full reference: {docs_url}\n\nError: {str(e)}"


def register_connector_builder_tools(app: FastMCP) -> None:
    """Register connector builder tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool(validate_manifest)
    app.tool(execute_stream_read)
    app.tool(get_resolved_manifest)
    app.tool(get_connector_builder_docs)
