"""Connector builder MCP tools.

This module provides MCP tools for connector building operations, including
manifest validation, stream testing, and configuration management.
"""

import logging
import pkgutil
from pathlib import Path
from typing import Annotated, Any, Literal

import requests
import yaml
from fastmcp import FastMCP
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel, Field

from airbyte_cdk import ConfiguredAirbyteStream
from airbyte_cdk.connector_builder.connector_builder_handler import (
    TestLimits,
    create_source,
    get_limits,
    read_stream,
    resolve_manifest,
)
from airbyte_cdk.models import (
    AirbyteStream,
    ConfiguredAirbyteCatalog,
    DestinationSyncMode,
    SyncMode,
)
from connector_builder_mcp._secrets import hydrate_config, register_secrets_tools
from connector_builder_mcp._util import filter_config_secrets, validate_manifest_structure


_REGISTRY_URL = "https://connectors.airbyte.com/files/registries/v0/oss_registry.json"
_MANIFEST_ONLY_LANGUAGE = "manifest-only"

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
    records: list[dict[str, Any]] | None = Field(
        default=None, description="Actual record data from the stream"
    )
    raw_api_responses: list[dict[str, Any]] | None = Field(
        default=None, description="Raw request/response data and metadata from CDK"
    )


def _get_dummy_catalog(stream_name: str) -> ConfiguredAirbyteCatalog:
    """Create a dummy configured catalog for one stream.

    We shouldn't have to do this. We should push it into the CDK code instead.

    For now, we have to create this (with no schema) or the read operation will fail.
    """
    return ConfiguredAirbyteCatalog(
        streams=[
            ConfiguredAirbyteStream(
                stream=AirbyteStream(
                    name=stream_name,
                    json_schema={},
                    supported_sync_modes=[SyncMode.full_refresh],
                ),
                sync_mode=SyncMode.full_refresh,
                destination_sync_mode=DestinationSyncMode.append,
            ),
        ]
    )


_DECLARATIVE_COMPONENT_SCHEMA: dict[str, Any] | None = None


def _get_declarative_component_schema() -> dict[str, Any]:
    """Load the declarative component schema from the CDK package (cached)."""
    global _DECLARATIVE_COMPONENT_SCHEMA

    if _DECLARATIVE_COMPONENT_SCHEMA is not None:
        return _DECLARATIVE_COMPONENT_SCHEMA

    try:
        raw_component_schema = pkgutil.get_data(
            "airbyte_cdk", "sources/declarative/declarative_component_schema.yaml"
        )
        if raw_component_schema is not None:
            _DECLARATIVE_COMPONENT_SCHEMA = yaml.load(raw_component_schema, Loader=yaml.SafeLoader)
            return _DECLARATIVE_COMPONENT_SCHEMA  # type: ignore
        else:
            raise RuntimeError(
                "Failed to read manifest component json schema required for validation"
            )
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Failed to read manifest component json schema required for validation: {e}"
        ) from e


def _format_validation_error(error: ValidationError) -> str:
    """Format a ValidationError with detailed field path and constraint information."""
    field_path = ".".join(map(str, error.path)) if error.path else "root"

    error_message = error.message

    if field_path == "root":
        detailed_error = f"JSON schema validation failed: {error_message}"
    else:
        detailed_error = f"JSON schema validation failed at field '{field_path}': {error_message}"

    if hasattr(error, "instance") and error.instance is not None:
        try:
            instance_str = str(error.instance)
            if len(instance_str) > 200:
                instance_str = instance_str[:200] + "..."
            detailed_error += f" (received: {instance_str})"
        except Exception:
            pass

    if hasattr(error, "schema") and isinstance(error.schema, dict):
        schema_info = []
        if "type" in error.schema:
            schema_info.append(f"expected type: {error.schema['type']}")
        if "enum" in error.schema:
            enum_values = error.schema["enum"]
            if len(enum_values) <= 5:
                schema_info.append(f"allowed values: {enum_values}")
        if "required" in error.schema:
            required_fields = error.schema["required"]
            if len(required_fields) <= 10:
                schema_info.append(f"required fields: {required_fields}")

        if schema_info:
            detailed_error += f" ({', '.join(schema_info)})"

    return detailed_error


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

        try:
            schema = _get_declarative_component_schema()
            validate(manifest, schema)
            logger.info("JSON schema validation passed")
        except ValidationError as schema_error:
            detailed_error = _format_validation_error(schema_error)
            logger.error(f"JSON schema validation failed: {detailed_error}")
            errors.append(detailed_error)
            return ManifestValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as schema_load_error:
            logger.warning(f"Could not load schema for pre-validation: {schema_load_error}")

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

    except ValidationError as e:
        logger.error(f"CDK validation error: {e}")
        detailed_error = _format_validation_error(e)
        errors.append(detailed_error)
    except Exception as e:
        logger.error(f"Error validating manifest: {e}")
        errors.append(f"Validation error: {str(e)}")

    is_valid = len(errors) == 0

    return ManifestValidationResult(
        is_valid=is_valid, errors=errors, warnings=warnings, resolved_manifest=resolved_manifest
    )


def execute_stream_test_read(
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
    include_records_data: Annotated[
        bool,
        Field(description="Include actual record data from the stream read"),
    ] = True,
    include_raw_responses_data: Annotated[
        bool,
        Field(description="Include raw API responses and request/response metadata"),
    ] = False,
    dotenv_path: Annotated[
        Path | None,
        Field(description="Optional path to .env file for secret hydration"),
    ] = None,
) -> StreamTestResult:
    """Execute reading from a connector stream.

    Returns both record data and raw request/response metadata from the stream test.
    Raw data is automatically sanitized to prevent exposure of secrets.
    """
    logger.info(f"Testing stream read for stream: {stream_name}")

    try:
        config = hydrate_config(config, dotenv_path=str(dotenv_path) if dotenv_path else None)
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
        catalog = _get_dummy_catalog(stream_name)

        result = read_stream(
            source=source,
            config=config_with_manifest,
            configured_catalog=catalog,
            state=[],
            limits=limits,
        )

        if result.type.value == "RECORD" and result.record and result.record.data:
            stream_data = result.record.data
            slices = stream_data.get("slices", []) if isinstance(stream_data, dict) else []

            records_data = []
            for slice_obj in slices:
                if isinstance(slice_obj, dict) and "pages" in slice_obj:
                    for page in slice_obj["pages"]:
                        if isinstance(page, dict) and "records" in page:
                            records_data.extend(page["records"])

            raw_responses_data = None
            if slices and include_raw_responses_data:
                filtered_slices = filter_config_secrets(slices.copy())
                if isinstance(filtered_slices, list):
                    raw_responses_data = filtered_slices

            return StreamTestResult(
                success=True,
                message=f"Successfully read {len(records_data)} records from stream {stream_name}",
                records_read=len(records_data),
                records=records_data if include_records_data else None,
                raw_api_responses=raw_responses_data,
            )

        error_msg = "Failed to read from stream"
        if hasattr(result, "trace") and result.trace:
            error_msg = result.trace.error.message

        return StreamTestResult(
            success=False,
            message=error_msg,
            errors=[error_msg],
        )

    except Exception as e:
        logger.error(f"Error testing stream read: {e}")
        error_msg = f"Stream test error: {str(e)}"
        return StreamTestResult(
            success=False,
            message=error_msg,
            errors=[error_msg],
        )


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


def _get_topic_mapping() -> dict[str, tuple[str, str]]:
    """Get the topic mapping with relative paths and descriptions."""
    return {
        "overview": (
            "docs/platform/connector-development/connector-builder-ui/overview.md",
            "Connector Builder overview and introduction",
        ),
        "tutorial": (
            "docs/platform/connector-development/connector-builder-ui/tutorial.mdx",
            "Step-by-step tutorial for building connectors",
        ),
        "authentication": (
            "docs/platform/connector-development/connector-builder-ui/authentication.md",
            "Authentication configuration",
        ),
        "incremental-sync": (
            "docs/platform/connector-development/connector-builder-ui/incremental-sync.md",
            "Setting up incremental data synchronization",
        ),
        "pagination": (
            "docs/platform/connector-development/connector-builder-ui/pagination.md",
            "Handling paginated API responses",
        ),
        "partitioning": (
            "docs/platform/connector-development/connector-builder-ui/partitioning.md",
            "Configuring partition routing for complex APIs",
        ),
        "record-processing": (
            "docs/platform/connector-development/connector-builder-ui/record-processing.mdx",
            "Processing and transforming records",
        ),
        "error-handling": (
            "docs/platform/connector-development/connector-builder-ui/error-handling.md",
            "Handling API errors and retries",
        ),
        "ai-assist": (
            "docs/platform/connector-development/connector-builder-ui/ai-assist.md",
            "Using AI assistance in the Connector Builder",
        ),
        "stream-templates": (
            "docs/platform/connector-development/connector-builder-ui/stream-templates.md",
            "Using stream templates for faster development",
        ),
        "custom-components": (
            "docs/platform/connector-development/connector-builder-ui/custom-components.md",
            "Working with custom components",
        ),
        "async-streams": (
            "docs/platform/connector-development/connector-builder-ui/async-streams.md",
            "Configuring asynchronous streams",
        ),
        "yaml-overview": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/yaml-overview.md",
            "Understanding the YAML file structure",
        ),
        "reference": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/reference.md",
            "Complete YAML reference documentation",
        ),
        "yaml-incremental-syncs": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/incremental-syncs.md",
            "Incremental sync configuration in YAML",
        ),
        "yaml-pagination": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/pagination.md",
            "Pagination configuration options",
        ),
        "yaml-partition-router": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/partition-router.md",
            "Partition routing in YAML manifests",
        ),
        "yaml-record-selector": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/record-selector.md",
            "Record selection and transformation",
        ),
        "yaml-error-handling": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/error-handling.md",
            "Error handling configuration",
        ),
        "yaml-authentication": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/authentication.md",
            "Authentication methods in YAML",
        ),
        "requester": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/requester.md",
            "HTTP requester configuration",
        ),
        "request-options": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/request-options.md",
            "Request parameter configuration",
        ),
        "rate-limit-api-budget": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/rate-limit-api-budget.md",
            "Rate limiting and API budget management",
        ),
        "file-syncing": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/file-syncing.md",
            "File synchronization configuration",
        ),
        "property-chunking": (
            "docs/platform/connector-development/config-based/understanding-the-yaml-file/property-chunking.md",
            "Property chunking for large datasets",
        ),
    }


def _get_high_level_overview() -> str:
    """Return high-level connector building process and available topics."""
    topic_mapping = _get_topic_mapping()

    topic_list = []
    for topic_key, (_, description) in topic_mapping.items():
        topic_list.append(f"- {topic_key} - {description}")

    topics_section = "\n".join(topic_list)

    overview = f"""# Connector Builder Documentation

1. Use the manifest YAML JSON schema for high-level guidelines
2. Use the validate manifest tool to confirm JSON schema is correct
3. Start with one stream or (better) a stream template that maps to a single stream
4. Make sure you have working authentication and data retrieval before moving onto pagination and other components
5. When all is confirmed working on the first stream, you can add additional streams. It is generally safest to add one stream at a time, and test each one before moving to the next

We use the Declarative YAML Connector convention for building connectors. Note that we don't yet support custom Python components.

For detailed documentation on specific components, request one of these topics:

{topics_section}

For detailed information on any topic, call this function again with the topic name.
"""
    return overview


def _get_topic_specific_docs(topic: str) -> str:
    """Get detailed documentation for a specific topic using raw GitHub URLs."""
    logger.info(f"Fetching detailed docs for topic: {topic}")

    topic_mapping = _get_topic_mapping()

    if topic not in topic_mapping:
        return f"# {topic} Documentation\n\nTopic '{topic}' not found. Please check the available topics list from the overview.\n\nAvailable topics: {', '.join(topic_mapping.keys())}"

    relative_path, description = topic_mapping[topic]
    raw_github_url = f"https://raw.githubusercontent.com/airbytehq/airbyte/master/{relative_path}"

    try:
        response = requests.get(raw_github_url, timeout=30)
        response.raise_for_status()

        markdown_content = response.text
        return f"# {topic} Documentation\n\n{markdown_content}"

    except Exception as e:
        logger.error(f"Error fetching documentation for topic {topic}: {e}")

        if relative_path.endswith(".md"):
            docs_path = relative_path[:-3]
        elif relative_path.endswith(".mdx"):
            docs_path = relative_path[:-4]
        else:
            docs_path = relative_path
        docs_url = f"https://docs.airbyte.com/{docs_path}"

        return f"# {topic} Documentation\n\nUnable to fetch detailed documentation from GitHub. Please refer to the full reference: {docs_url}\n\nError: {str(e)}"


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

        return False

    except Exception as e:
        logger.warning(f"Failed to fetch registry data for {connector_name}: {e}")
        return False


def get_connector_manifest(
    connector_name: Annotated[
        str,
        Field(description="Name of the connector (e.g., 'source-faker', 'source-github')"),
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
        connector_name: Name of the connector (e.g., 'source-faker', 'source-github')
        version: Version of the connector manifest to retrieve (defaults to 'latest')

    Returns:
        Raw YAML content of the connector manifest
    """
    logger.info(f"Getting connector manifest for {connector_name} version {version}")

    cleaned_version = version.removeprefix("v")

    is_manifest_only = _is_manifest_only_connector(connector_name)
    file_type = "manifest.yaml" if is_manifest_only else "metadata.yaml"

    logger.info(
        f"Connector {connector_name} is {'manifest-only' if is_manifest_only else 'not manifest-only'}, fetching {file_type}"
    )

    manifest_url = f"https://connectors.airbyte.com/metadata/airbyte/{connector_name}/{cleaned_version}/{file_type}"

    try:
        response = requests.get(manifest_url, timeout=30)
        response.raise_for_status()

        return response.text

    except Exception as e:
        logger.error(f"Error fetching connector {file_type} for {connector_name}: {e}")
        return f"# Error fetching connector {file_type}\n\nUnable to fetch {file_type} for connector '{connector_name}' version '{version}' from {manifest_url}\n\nError: {str(e)}"


def register_connector_builder_tools(app: FastMCP) -> None:
    """Register connector builder tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool(validate_manifest)
    app.tool(execute_stream_test_read)
    app.tool(get_resolved_manifest)
    app.tool(get_connector_builder_docs)
    app.tool(get_connector_manifest)
    register_secrets_tools(app)
