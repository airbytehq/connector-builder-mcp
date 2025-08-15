"""Validation and testing tools for Airbyte connector manifests."""

import csv
import json
import logging
import pkgutil
import time
from pathlib import Path
from typing import Annotated, Any, Literal

import requests
from airbyte_cdk.sources.declarative.manifest_declarative_source import ManifestDeclarativeSource
from airbyte_cdk.sources.declarative.parsers.manifest_component_transformer import (
    ManifestComponentTransformer,
)
from airbyte_cdk.sources.declarative.parsers.manifest_reference_resolver import (
    ManifestReferenceResolver,
)
from airbyte_cdk.test.catalog_builder import CatalogBuilder
from airbyte_cdk.test.entrypoint_wrapper import EntrypointOutput, read
from airbyte_cdk.test.state_builder import StateBuilder
from airbyte_cdk.utils.traced_exception import AirbyteTracedException
from airbyte_cdk.models import AirbyteMessage, ConfiguredAirbyteCatalog, Type
from jsonschema import ValidationError, validate
from pydantic import BaseModel, Field

from connector_builder_mcp._util import parse_manifest_input, validate_manifest_structure
from connector_builder_mcp._secrets import hydrate_config
from airbyte_cdk.connector_builder.connector_builder_handler import (
    TestLimits,
    create_source,
    full_resolve_manifest,
    get_limits,
    resolve_manifest,
)

logger = logging.getLogger(__name__)


class ManifestValidationResult(BaseModel):
    """Result of manifest validation."""

    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    resolved_manifest: dict[str, Any] | None = None


class StreamTestResult(BaseModel):
    """Result of stream testing."""

    success: bool
    message: str
    records_read: int = 0
    records: list[dict[str, Any]] | None = None
    errors: list[str] = []
    raw_api_responses: list[dict[str, Any]] | None = None


class StreamSmokeTest(BaseModel):
    """Result of a single stream smoke test."""

    stream_name: str
    success: bool
    records_read: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None


class MultiStreamSmokeTest(BaseModel):
    """Result of multi-stream smoke testing."""

    success: bool
    total_streams_tested: int
    total_streams_successful: int
    total_records_count: int
    duration_seconds: float
    stream_results: dict[str, StreamSmokeTest]


def _get_dummy_catalog(manifest_dict: dict[str, Any]) -> ConfiguredAirbyteCatalog:
    """Create a dummy catalog for testing purposes."""
    catalog_builder = CatalogBuilder()

    streams = manifest_dict.get("streams", [])
    for stream in streams:
        stream_name = stream.get("name", "unknown_stream")
        catalog_builder.with_stream(stream_name, {})

    return catalog_builder.build()


def _get_declarative_component_schema() -> dict[str, Any]:
    """Get the declarative component schema for validation."""
    try:
        schema_text = pkgutil.get_data(
            "airbyte_cdk.sources.declarative", "declarative_component_schema.yaml"
        )
        if schema_text is None:
            raise FileNotFoundError("Could not load declarative component schema")

        import yaml

        return yaml.safe_load(schema_text.decode("utf-8"))
    except Exception as e:
        logger.warning(f"Could not load declarative component schema: {e}")
        return {}


def _format_validation_error(error: ValidationError) -> str:
    """Format a validation error with context."""
    path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"

    detailed_error = f"Validation error at '{path}': {error.message}"

    if error.context:
        detailed_error += "\n  Context errors:"
        for ctx_error in error.context:
            ctx_path = " -> ".join(str(p) for p in ctx_error.absolute_path) if ctx_error.absolute_path else "root"
            detailed_error += f"\n    - At '{ctx_path}': {ctx_error.message}"

    if hasattr(error, "schema") and error.schema:
        if "description" in error.schema:
            detailed_error += f"\n  Expected: {error.schema['description']}"
        elif "type" in error.schema:
            detailed_error += f"\n  Expected type: {error.schema['type']}"

    if error.instance is not None:
        instance_str = str(error.instance)
        if len(instance_str) > 100:
            instance_str = instance_str[:100] + "..."
        detailed_error += f"\n  Actual value: {instance_str}"

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
            errors.append(
                "Manifest missing required fields: version, type, check, and either streams or dynamic_streams"
            )
            return ManifestValidationResult(is_valid=False, errors=errors, warnings=warnings)

        try:
            logger.info("Applying CDK preprocessing: resolving references")
            reference_resolver = ManifestReferenceResolver()
            resolved_manifest = reference_resolver.preprocess_manifest(manifest_dict)

            logger.info("Applying CDK preprocessing: propagating types and parameters")
            component_transformer = ManifestComponentTransformer()
            processed_manifest = component_transformer.propagate_types_and_parameters(
                "", resolved_manifest, {}
            )

            logger.info("CDK preprocessing completed successfully")
            manifest_dict = processed_manifest

        except Exception as preprocessing_error:
            logger.error(f"CDK preprocessing failed: {preprocessing_error}")
            errors.append(f"Preprocessing error: {str(preprocessing_error)}")
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
    stream_name: Annotated[str, Field(description="Name of the stream to test")],
    *,
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read", ge=1, le=50000),
    ] = 10000,
    include_records_data: Annotated[
        bool,
        Field(description="Whether to include actual record data in the response"),
    ] = False,
    include_raw_responses_data: Annotated[
        bool | None,
        Field(
            description="Whether to include raw API response data. "
            "True=always include, False=never include, None=include on errors only"
        ),
    ] = None,
    dotenv_path: Annotated[
        Path | None,
        Field(description="Optional path to .env file for secret hydration"),
    ] = None,
) -> StreamTestResult:
    """Test reading records from a specific stream in the connector.

    Args:
        manifest: The connector manifest (YAML string or file path)
        config: Connector configuration
        stream_name: Name of the stream to test
        max_records: Maximum number of records to read (default: 10000)
        include_records_data: Whether to include actual record data in response
        include_raw_responses_data: Whether to include raw API responses
        dotenv_path: Optional path to .env file for secret hydration

    Returns:
        StreamTestResult with success status, record count, and optional data
    """
    logger.info(f"Testing stream read for {stream_name}")

    try:
        manifest_dict = parse_manifest_input(manifest)

        config = hydrate_config(config, dotenv_path=str(dotenv_path) if dotenv_path else None)
        config_with_manifest = {
            **config,
            "__injected_declarative_manifest": manifest_dict,
            "__test_read_config": {
                "max_records": max_records,
                "max_pages_per_slice": 10,
                "max_slices": 10,
            },
        }

        limits = get_limits(config_with_manifest)
        source = create_source(config_with_manifest, limits)

        catalog = _get_dummy_catalog(manifest_dict)

        for configured_stream in catalog.streams:
            if configured_stream.stream.name == stream_name:
                configured_stream.sync_mode = "full_refresh"
                configured_stream.destination_sync_mode = "overwrite"
                break
        else:
            return StreamTestResult(
                success=False,
                message=f"Stream '{stream_name}' not found in manifest",
                errors=[f"Stream '{stream_name}' not found in available streams"],
            )

        state = StateBuilder().build()

        output: EntrypointOutput = read(source, config_with_manifest, catalog, state)

        records_data = []
        slices = []

        for message in output:
            if isinstance(message, AirbyteMessage):
                if message.type == Type.RECORD and message.record.stream == stream_name:
                    if include_records_data:
                        records_data.append(message.record.data)
                elif message.type == Type.TRACE and message.trace.type.value == "STREAM_STATUS":
                    if hasattr(message.trace, "stream_status") and message.trace.stream_status:
                        slice_data = getattr(message.trace.stream_status, "slice", None)
                        if slice_data:
                            slices.append(slice_data)

        raw_responses_data = None
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

        raw_responses_data = None
        if include_raw_responses_data is not False:
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
        available_streams = manifest_dict.get("streams", [])
        stream_names = [stream.get("name", f"stream_{i}") for i, stream in enumerate(available_streams)]

    logger.info(f"Testing {len(stream_names)} streams: {stream_names}")

    for stream_name in stream_names:
        stream_start_time = time.time()
        total_streams_tested += 1

        try:
            result = execute_stream_test_read(
                manifest=manifest,
                config=config,
                stream_name=stream_name,
                max_records=max_records,
                include_records_data=False,
                include_raw_responses_data=False,
                dotenv_path=dotenv_path,
            )

            stream_duration = time.time() - stream_start_time
            records_read = result.records_read

            if result.success:
                total_streams_successful += 1
                total_records_count += records_read
                stream_results[stream_name] = StreamSmokeTest(
                    stream_name=stream_name,
                    success=True,
                    records_read=records_read,
                    duration_seconds=stream_duration,
                )
                logger.info(f"✓ {stream_name}: {records_read} records in {stream_duration:.2f}s")
            else:
                error_message = result.message
                stream_results[stream_name] = StreamSmokeTest(
                    stream_name=stream_name,
                    success=False,
                    records_read=0,
                    duration_seconds=stream_duration,
                    error_message=error_message,
                )
                logger.warning(f"✗ {stream_name}: Failed - {error_message}")

        except Exception as e:
            stream_duration = time.time() - stream_start_time
            error_message = f"Unexpected error: {str(e)}"
            stream_results[stream_name] = StreamSmokeTest(
                stream_name=stream_name,
                success=False,
                records_read=0,
                duration_seconds=stream_duration,
                error_message=error_message,
            )
            logger.error(f"✗ {stream_name}: Exception - {error_message}")

    total_duration = time.time() - start_time
    overall_success = total_streams_successful == total_streams_tested

    logger.info(
        f"Smoke test completed: {total_streams_successful}/{total_streams_tested} streams successful, "
        f"{total_records_count} total records in {total_duration:.2f}s"
    )

    return MultiStreamSmokeTest(
        success=overall_success,
        total_streams_tested=total_streams_tested,
        total_streams_successful=total_streams_successful,
        total_records_count=total_records_count,
        duration_seconds=total_duration,
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
