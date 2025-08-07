# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Connector builder MCP tools.

This module provides MCP tools for connector building operations, including
manifest validation, stream testing, and configuration management.
"""

import logging
import pkgutil
import time
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
    full_resolve_manifest,
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

from connector_builder_mcp._guidance import OVERVIEW_PROMPT, TOPIC_MAPPING
from connector_builder_mcp._secrets import hydrate_config, register_secrets_tools
from connector_builder_mcp._util import (
    filter_config_secrets,
    parse_manifest_input,
    validate_manifest_structure,
)


_MANIFEST_SCHEMA_URL: str = "https://raw.githubusercontent.com/airbytehq/airbyte-python-cdk/main/airbyte_cdk/sources/declarative/declarative_component_schema.yaml"
_REGISTRY_URL = "https://connectors.airbyte.com/files/registries/v0/oss_registry.json"
_MANIFEST_ONLY_LANGUAGE = "manifest-only"
_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401

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
    logs: list[dict[str, Any]] | None = Field(
        default=None, description="Logs returned by the test read operation (if applicable)."
    )


class StreamSmokeTest(BaseModel):
    """Result of a single stream smoke test."""

    stream_name: str
    success: bool
    records_count: int = 0
    max_records_limit: int
    errors: list[str] = []
    logs: list[dict[str, Any]] | None = Field(
        default=None, description="Logs from the stream test operation (if applicable)."
    )
    time_elapsed_seconds: float


class MultiStreamSmokeTest(BaseModel):
    """Result of multi-stream smoke test operation."""

    success: bool
    message: str
    total_streams_tested: int = 0
    total_streams_successful: int = 0
    total_records_count: int = 0
    total_time_elapsed_seconds: float
    stream_results: dict[str, StreamSmokeTest] = Field(
        description="Dictionary mapping stream names to their individual smoke test results"
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

        raise RuntimeError("Failed to read manifest component json schema required for validation")
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
        str,
        Field(
            description="The connector manifest to validate. "
            "Can be raw a YAML string or path to YAML file"
        ),
    ],
) -> ManifestValidationResult:
    """Validate a connector manifest structure and configuration.

    Returns:
        Validation result with success status and any errors/warnings
    """
    logger.info("Validating connector manifest")

    errors: list[str] = []
    warnings: list[str] = []
    resolved_manifest = None

    try:
        manifest_dict = parse_manifest_input(manifest)

        if not validate_manifest_structure(manifest_dict):
            errors.append("Manifest missing required fields: version, type, check, streams")
            return ManifestValidationResult(is_valid=False, errors=errors, warnings=warnings)

        try:
            schema = _get_declarative_component_schema()
            validate(manifest_dict, schema)
            logger.info("JSON schema validation passed")
        except ValidationError as schema_error:
            detailed_error = _format_validation_error(schema_error)
            logger.error(f"JSON schema validation failed: {detailed_error}")
            errors.append(detailed_error)
            return ManifestValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as schema_load_error:
            logger.warning(f"Could not load schema for pre-validation: {schema_load_error}")

        config_with_manifest = {"__injected_declarative_manifest": manifest_dict}

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
        str,
        Field(description="The connector manifest. Can be raw a YAML string or path to YAML file"),
    ],
    config: Annotated[
        dict[str, Any],
        Field(description="Connector configuration"),
    ],
    stream_name: Annotated[
        str,
        Field(description="Name of the stream to test"),
    ],
    *,
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read", ge=1, le=1000),
    ] = 10,
    include_records_data: Annotated[
        bool,
        Field(description="Include actual record data from the stream read"),
    ] = True,
    include_raw_responses_data: Annotated[
        bool | None,
        Field(
            description="Include raw API responses and request/response metadata. "
            "Defaults to 'None', which means raw data is included only if an error occurs. "
            "If set to 'False', raw data is not included even on errors."
        ),
    ] = None,
    dotenv_path: Annotated[
        Path | None,
        Field(description="Optional path to .env file for secret hydration"),
    ] = None,
) -> StreamTestResult:
    """Execute reading from a connector stream.

    Return record data and/or raw request/response metadata from the stream test.
    We attempt to automatically sanitize raw data to prevent exposure of secrets.
    We do not attempt to sanitize record data, as it is expected to be user-defined.
    """
    logger.info(f"Testing stream read for stream: {stream_name}")

    try:
        manifest_dict = parse_manifest_input(manifest)

        config = hydrate_config(config, dotenv_path=str(dotenv_path) if dotenv_path else None)
        config_with_manifest = {
            **config,
            "__injected_declarative_manifest": manifest_dict,
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

        if not (result.type.value == "RECORD" and result.record and result.record.data):
            error_msg = "Failed to read from stream"
            if hasattr(result, "trace") and result.trace:
                error_msg = result.trace.error.message

            return StreamTestResult(
                success=False,
                message=error_msg,
                errors=[error_msg],
            )

        stream_data = result.record.data
        slices = stream_data.get("slices", None)
        if not slices:
            logs = stream_data.pop("logs", [])
            return StreamTestResult(
                success=False,
                message=f"No API output returned for stream '{stream_name}'.",
                errors=[
                    f"No API output returned for stream '{stream_name}'.",
                    f"Result object: {stream_data!s}",
                ],
                logs=logs,
            )

        slices = stream_data.get("slices", []) if isinstance(stream_data, dict) else []
        slices = filter_config_secrets(slices)

        records_data = []
        for slice_obj in slices:
            if isinstance(slice_obj, dict) and "pages" in slice_obj:
                for page in slice_obj["pages"]:
                    if isinstance(page, dict) and "records" in page:
                        records_data.extend(page.pop("records"))

        raw_responses_data = None
        # Always include raw data when explicitly requested (True)
        if include_raw_responses_data is True and slices and isinstance(slices, list):
            raw_responses_data = slices

        return StreamTestResult(
            success=True,
            message=f"Successfully read {len(records_data)} records from stream {stream_name}",
            records_read=len(records_data),
            records=records_data if include_records_data else None,
            raw_api_responses=raw_responses_data,
        )

    except Exception as e:
        logger.error(f"Error testing stream read: {e}")
        error_msg = f"Stream test error: {str(e)}"

        # Include raw data on errors when not explicitly disabled (None or True)
        raw_responses_data = None
        if include_raw_responses_data is not False:
            # Try to extract some context from the error if possible
            raw_responses_data = [{"error": error_msg, "context": "Failed to read stream"}]

        return StreamTestResult(
            success=False,
            message=error_msg,
            errors=[error_msg],
            raw_api_responses=raw_responses_data,
        )


def execute_record_counts_smoke_test(
    manifest: Annotated[
        str,
        Field(description="The connector manifest. Can be raw a YAML string or path to YAML file"),
    ],
    config: Annotated[
        dict[str, Any],
        Field(description="Connector configuration"),
    ],
    streams: Annotated[
        str | None,
        Field(
            description="Optional CSV-delimited list of streams to test."
            "If not provided, tests all streams in the manifest."
        ),
    ] = None,
    *,
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read per stream", ge=1, le=50000),
    ] = 10000,
    dotenv_path: Annotated[
        Path | None,
        Field(description="Optional path to .env file for secret hydration"),
    ] = None,
) -> MultiStreamSmokeTest:
    """Execute a smoke test to count records from all streams in the connector.

    This function tests all available streams by reading records up to the specified limit
    and returns comprehensive statistics including record counts, errors, and timing information.

    Args:
        manifest: The connector manifest (YAML string or file path)
        config: Connector configuration
        max_records: Maximum number of records to read per stream (default: 10000)
        dotenv_path: Optional path to .env file for secret hydration

    Returns:
        MultiStreamSmokeTest result with per-stream statistics and overall summary
    """
    logger.info("Starting multi-stream smoke test")
    start_time = time.time()
    total_streams_tested = 0
    total_streams_successful = 0
    total_records_count = 0
    stream_results: dict[str, StreamSmokeTest] = {}

    manifest_dict = parse_manifest_input(manifest)

    # Hydrate config with secrets if dotenv_path is provided
    config = hydrate_config(config, dotenv_path=str(dotenv_path) if dotenv_path else None)
    config_with_manifest = {
        **config,
        "__injected_declarative_manifest": manifest_dict,
        "__test_read_config": {
            "max_records": max_records,
            "max_pages_per_slice": 10,
            "max_slices": 10,
            "max_streams": 100,
        },
    }

    limits = get_limits(config_with_manifest)
    source = create_source(config_with_manifest, limits)

    stream_names: list[str]
    if isinstance(streams, str):
        stream_names = [s.strip() for s in streams.split(",") if s.strip()]
    elif isinstance(streams, list):
        stream_names = [s.strip() for s in streams]
    else:
        # Test each stream individually
        stream_names = [
            stream_config.get("name")
            for stream_config in manifest_dict.get("streams", [])
            if stream_config.get("name")  # Filter out None values
        ]
        if not stream_names:
            return MultiStreamSmokeTest(
                success=False,
                message="No streams found in manifest",
                stream_results={},
                total_time_elapsed_seconds=time.time() - start_time,
            )

    for stream_name in stream_names:  # noqa: PLR1702
        stream_start_time = time.time()
        logger.info(f"Testing stream: {stream_name}")

        try:
            catalog = _get_dummy_catalog(stream_name)
            result = read_stream(
                source=source,
                config=config_with_manifest,
                configured_catalog=catalog,
                state=[],
                limits=limits,
            )

            stream_elapsed = time.time() - stream_start_time

            if result.type.value == "RECORD" and result.record and result.record.data:
                stream_data = result.record.data
                slices = stream_data.get("slices", [])
                logs = stream_data.get("logs", [])

                records_count = 0
                if slices:
                    for slice_obj in slices:
                        if isinstance(slice_obj, dict) and "pages" in slice_obj:
                            for page in slice_obj["pages"]:
                                if isinstance(page, dict) and "records" in page:
                                    records_count += len(page["records"])

                stream_results[stream_name] = StreamSmokeTest(
                    stream_name=stream_name,
                    success=True,
                    records_count=records_count,
                    max_records_limit=max_records,
                    logs=logs,
                    time_elapsed_seconds=stream_elapsed,
                )
                total_records_count += records_count
                total_streams_successful += 1

            else:
                error_msg = "Failed to read from stream"
                if hasattr(result, "trace") and result.trace and result.trace.error:
                    error_msg = result.trace.error.message or error_msg

                stream_results[stream_name] = StreamSmokeTest(
                    stream_name=stream_name,
                    success=False,
                    records_count=0,
                    max_records_limit=max_records,
                    errors=[error_msg],
                    time_elapsed_seconds=stream_elapsed,
                )

        except Exception as e:
            stream_elapsed = time.time() - stream_start_time
            error_msg = f"Error testing stream {stream_name}: {e!s}"
            logger.warning(error_msg)

            stream_results[stream_name] = StreamSmokeTest(
                stream_name=stream_name,
                success=False,
                records_count=0,
                max_records_limit=max_records,
                errors=[error_msg],
                time_elapsed_seconds=stream_elapsed,
            )

    total_time = time.time() - start_time
    total_streams_tested = len(stream_results)

    success = total_streams_successful > 0
    if success:
        message = f"Smoke test completed: {total_streams_successful}/{total_streams_tested} streams successful, {total_records_count} total records"
    else:
        message = f"Smoke test failed: No streams were successfully tested out of {total_streams_tested} streams"

    return MultiStreamSmokeTest(
        success=success,
        message=message,
        total_streams_tested=total_streams_tested,
        total_streams_successful=total_streams_successful,
        total_records_count=total_records_count,
        total_time_elapsed_seconds=total_time,
        stream_results=stream_results,
    )


def execute_dynamic_manifest_resolution_test(
    manifest: Annotated[
        str,
        Field(
            description="The connector manifest with dynamic elements to resolve. "
            "Can be raw YAML content or path to YAML file"
        ),
    ],
    config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional connector configuration"),
    ] = None,
) -> dict[str, Any] | Literal["Failed to resolve manifest"]:
    """Get the resolved connector manifest, expanded with detected dynamic streams and schemas.

    This tool is helpful for discovering dynamic streams and schemas. This should not replace the
    original manifest, but it can provide helpful information to understand how the manifest will
    be resolved and what streams will be available at runtime.

    Args:
        manifest: The connector manifest to resolve. Can be raw YAML content or path to YAML file
        config: Optional configuration for resolution

    TODO:
    - Research: Is there any reason to ever get the non-fully resolved manifest?

    Returns:
        Resolved manifest or error message
    """
    logger.info("Getting resolved manifest")

    try:
        manifest_dict = parse_manifest_input(manifest)

        if config is None:
            config = {}

        config_with_manifest = {
            **config,
            "__injected_declarative_manifest": manifest_dict,
        }

        limits = TestLimits(max_records=10, max_pages_per_slice=1, max_slices=1)

        source = create_source(config_with_manifest, limits)
        result = full_resolve_manifest(
            source,
            limits,
        )

        if (
            result.type.value == "RECORD"
            and result.record is not None
            and result.record.data is not None
        ):
            manifest_data = result.record.data.get("manifest", {})
            if isinstance(manifest_data, dict):
                return manifest_data
            return {}

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

    return OVERVIEW_PROMPT if not topic else _get_topic_specific_docs(topic)


def _get_topic_specific_docs(topic: str) -> str:
    """Get detailed documentation for a specific topic using raw GitHub URLs."""
    logger.info(f"Fetching detailed docs for topic: {topic}")

    if topic not in TOPIC_MAPPING:
        return f"# {topic} Documentation\n\nTopic '{topic}' not found. Please check the available topics list from the overview.\n\nAvailable topics: {', '.join(TOPIC_MAPPING.keys())}"

    full_url: str
    topic_path, _ = TOPIC_MAPPING[topic]
    if "https://" in topic_path:
        full_url = topic_path
    else:
        full_url = f"https://raw.githubusercontent.com/airbytehq/airbyte/master/{topic_path}"

    try:
        response = requests.get(full_url, timeout=30)
        response.raise_for_status()

        markdown_content = response.text
        return f"# '{topic}' Documentation\n\n{markdown_content}"

    except Exception as e:
        logger.error(f"Error fetching documentation for topic '{topic}': {e}")

        return (
            f"Unable to fetch detailed documentation for topic '{topic}' "
            f"using path '{topic_path}' and full URL '{full_url}'."
            f"\n\nError: {e!s}"
        )


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


# @mcp.tool() // Deferred
def get_manifest_yaml_json_schema() -> str:
    """Retrieve the connector manifest JSON schema from the Airbyte repository.

    This tool fetches the official JSON schema used to validate connector manifests.
    The schema defines the structure, required fields, and validation rules for
    connector YAML configurations.

    Returns:
        Response containing the schema in YAML format
    """
    # URL to the manifest schema in the Airbyte Python CDK repository

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "connector-schema-tool",
    }

    response = requests.get(
        _MANIFEST_SCHEMA_URL,
        headers=headers,
        timeout=30,
    )
    if response.status_code == _HTTP_OK:
        return response.text

    response.raise_for_status()  # Raise HTTPError for bad responses
    raise RuntimeError(
        "Something went wrong. Expected success or exception but neither occurred."
    )  # pragma: no cover # This line should not be reached


def register_connector_builder_tools(app: FastMCP) -> None:
    """Register connector builder tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool(validate_manifest)
    app.tool(execute_stream_test_read)
    app.tool(execute_record_counts_smoke_test)
    app.tool(execute_dynamic_manifest_resolution_test)
    app.tool(get_manifest_yaml_json_schema)
    app.tool(get_connector_builder_docs)
    app.tool(get_connector_manifest)
    register_secrets_tools(app)
