"""Validation and testing tools for Airbyte connector manifests."""

import logging
import pkgutil
import time
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from airbyte_cdk.sources.declarative.models import DeclarativeSource
from jsonschema import ValidationError, validate
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
from airbyte_cdk.sources.declarative.parsers.manifest_component_transformer import (
    ManifestComponentTransformer,
)
from airbyte_cdk.sources.declarative.parsers.manifest_reference_resolver import (
    ManifestReferenceResolver,
)

from connector_builder_mcp._util import (
    as_bool,
    as_dict,
    filter_config_secrets,
    is_valid_declarative_source_manifest,
    parse_manifest_input,
    validate_manifest_structure,
)
from connector_builder_mcp.secrets import hydrate_config


logger = logging.getLogger(__name__)


class ManifestValidationResult(BaseModel):
    """Result of manifest validation."""

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
    logs: list[dict[str, Any]] | None = Field(
        default=None, description="Logs returned by the test read operation (if applicable)."
    )
    record_stats: dict[str, Any] | None = None
    raw_api_responses: list[dict[str, Any]] | None = Field(
        default=None, description="Raw request/response data and metadata from CDK"
    )


class StreamSmokeTest(BaseModel):
    """Result of a single stream smoke test."""

    stream_name: str
    success: bool
    records_read: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None
    field_count_warnings: list[str] = []


class MultiStreamSmokeTest(BaseModel):
    """Result of multi-stream smoke testing."""

    success: bool
    total_streams_tested: int
    total_streams_successful: int
    total_records_count: int
    duration_seconds: float
    stream_results: dict[str, StreamSmokeTest]


def _calculate_record_stats(
    records_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate statistics for record properties.

    Args:
        records_data: List of record dictionaries to analyze

    Returns:
        Dictionary containing property statistics including counts and types
    """
    property_stats: dict[str, dict[str, Any]] = {}

    for record in records_data:
        if isinstance(record, dict):
            for key, value in record.items():
                if key not in property_stats:
                    property_stats[key] = {
                        "type": type(value).__name__,
                        "num_null": 0,
                        "num_non_null": 0,
                    }

                if value is None:
                    property_stats[key]["num_null"] += 1
                else:
                    property_stats[key]["num_non_null"] += 1
                    property_stats[key]["type"] = type(value).__name__

    return {
        "num_properties": len(property_stats),
        "properties": property_stats,
    }


def _get_dummy_catalog(
    stream_name: str,
) -> ConfiguredAirbyteCatalog:
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


def _get_declarative_component_schema() -> dict[str, Any]:
    """Get the declarative component schema for validation."""
    try:
        schema_text = pkgutil.get_data(
            "airbyte_cdk.sources.declarative", "declarative_component_schema.yaml"
        )
        if schema_text is None:
            raise FileNotFoundError("Could not load declarative component schema")

        import yaml

        schema_data = yaml.safe_load(schema_text.decode("utf-8"))
        if isinstance(schema_data, dict):
            return schema_data
        return {}
    except Exception as e:
        logger.warning(f"Could not load declarative component schema: {e}")
        return {}


def _format_validation_error(
    error: ValidationError,
) -> str:
    """Format a validation error with context."""
    path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"

    detailed_error = f"Validation error at '{path}': {error.message}"

    if error.context:
        context_errors = [
            f"\n    - At '{' -> '.join(str(p) for p in ctx_error.absolute_path) if ctx_error.absolute_path else 'root'}': {ctx_error.message}"
            for ctx_error in error.context
        ]
        detailed_error += "\n  Context errors:" + "".join(context_errors)

    additional_info = []
    if hasattr(error, "schema") and error.schema:
        schema = error.schema
        if isinstance(schema, dict):
            if "description" in schema:
                additional_info.append(f"\n  Expected: {schema['description']}")
            elif "type" in schema:
                additional_info.append(f"\n  Expected type: {schema['type']}")

    if error.instance is not None:
        instance_str = str(error.instance)
        if len(instance_str) > 100:
            instance_str = instance_str[:100] + "..."
        additional_info.append(f"\n  Actual value: {instance_str}")

    detailed_error += "".join(additional_info)

    logger.warning(f"⚠️ Length of detailed_error: {len(detailed_error)}")

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
        manifest_dict, _ = parse_manifest_input(manifest)

        is_valid, error_message = validate_manifest_structure(manifest_dict)
        # is_valid, error_message = is_valid_declarative_source_manifest(manifest_dict)
        if not is_valid:
            errors.append(error_message)
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


def execute_stream_test_read(  # noqa: PLR0914
    manifest: Annotated[
        str,
        Field(description="The connector manifest. Can be raw a YAML string or path to YAML file"),
    ],
    stream_name: Annotated[
        str,
        Field(description="Name of the stream to test"),
    ],
    config: Annotated[
        dict[str, Any] | str | None,
        Field(description="Connector configuration dictionary."),
    ] = None,
    *,
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read", ge=1),
    ] = 10,
    include_records_data: Annotated[
        bool | str,
        Field(description="Include actual record data from the stream read"),
    ] = True,
    include_record_stats: Annotated[
        bool | str,
        Field(description="Include basic statistics on record properties"),
    ] = True,
    include_raw_responses_data: Annotated[
        bool | str | None,
        Field(
            description="Include raw API responses and request/response metadata. "
            "Defaults to 'None', which auto-enables raw data when an error occurs or zero records are returned. "
            "If set to 'True', raw data is always included. "
            "If set to 'False', raw data is excluded UNLESS zero records are returned (in which case it's auto-enabled for debugging)."
        ),
    ] = None,
    dotenv_file_uris: Annotated[
        list[str] | str | None,
        Field(
            description="Optional paths/URLs to local .env files or Privatebin.net URLs for secret hydration. Can be a single string, comma-separated string, or list of strings. Privatebin secrets may be created at privatebin.net, and must: contain text formatted as a dotenv file, use a password sent via the `PRIVATEBIN_PASSWORD` env var, and not include password text in the URL."
        ),
    ] = None,
) -> StreamTestResult:
    """Execute reading from a connector stream.

    Return record data and/or raw request/response metadata from the stream test.
    We attempt to automatically sanitize raw data to prevent exposure of secrets.
    We do not attempt to sanitize record data, as it is expected to be user-defined.
    """
    success: bool = True
    include_records_data = as_bool(
        include_records_data,
        default=False,
    )
    include_record_stats = as_bool(
        include_record_stats,
        default=False,
    )
    include_raw_responses_data = as_bool(
        include_raw_responses_data,
        default=False,
    )
    logger.info(f"Testing stream read for stream: {stream_name}")
    config = as_dict(config, default={})

    manifest_dict, _ = parse_manifest_input(manifest)

    config = hydrate_config(config, dotenv_file_uris=dotenv_file_uris)
    config_with_manifest = {
        **config,
        "__injected_declarative_manifest": manifest_dict,
        "__test_read_config": {
            "max_streams": 1,
            "max_records": max_records,
            # We actually don't want to limit pages or slices.
            # But if we don't provide a value they default
            # to very low limits, which is not what we want.
            "max_pages_per_slice": max(1, max_records),
            "max_slices": max(1, max_records),
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

    error_msgs: list[str] = []
    execution_logs: list[dict[str, Any]] = []
    if hasattr(result, "trace") and result.trace and result.trace.error:
        # We received a trace message instead of a record message.
        # Probably this was fatal, but we defer setting 'success=False', just in case.
        error_msgs.append(result.trace.error.message)

    slices: list[dict[str, Any]] = []
    stream_data: dict[str, Any] = {}
    if result.record and result.record.data:
        stream_data = result.record.data
        slices_from_stream = stream_data.get("slices", [])
        # auxiliary_requests may contain HTTP request/response data when slices is empty
        if (
            include_raw_responses_data
            and not slices_from_stream
            and "auxiliary_requests" in stream_data
        ):
            slices_from_stream = stream_data.get("auxiliary_requests", [])

        slices = cast(
            list[dict[str, Any]],
            filter_config_secrets(slices_from_stream),
        )
    else:
        success = False
        error_msgs.append("Source failed to return a test read response record.")

    execution_logs += stream_data.pop("logs", [])
    if not slices:
        success = False
        error_msgs.append(f"No API output returned for stream '{stream_name}'.")

    records_data: list[dict[str, Any]] = []
    for slice_obj in slices:
        if isinstance(slice_obj, dict) and "pages" in slice_obj:
            for page in slice_obj["pages"]:
                if isinstance(page, dict) and "records" in page:
                    records_data.extend(page.pop("records"))

    record_stats = None
    if include_record_stats and records_data:
        record_stats = _calculate_record_stats(records_data)

    if len(records_data) == 0 and success:
        execution_logs.append(
            {
                "level": "WARNING",
                "message": "Read attempt returned zero records. Please review the included raw responses to ensure the zero-records result is correct.",
            }
        )
        # Override include_raw_responses_data to ensure caller confirms correctness:
        include_raw_responses_data = True

    # Toggle to include_raw_responses=True if we had an error
    include_raw_responses_data = include_raw_responses_data or not success

    return StreamTestResult(
        success=success,
        message=(
            f"Successfully read {len(records_data)} records from stream {stream_name}"
            if success and records_data
            else f"Failed to read records from stream {stream_name}"
        ),
        records_read=len(records_data),
        records=records_data if include_records_data else None,
        record_stats=record_stats,
        errors=error_msgs,
        logs=execution_logs,
        raw_api_responses=[stream_data] if include_raw_responses_data else None,
    )


def _as_saved_report(
    report_text: str,
    file_path: str | Path | None,
) -> str:
    """Save the test report to a file."""
    if file_path:
        file_path = Path(file_path)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(report_text)
        except Exception:
            logger.exception(f"Failed to save report to {file_path}")
            report_text = "\n".join(
                [
                    f"Failed to save report to: {file_path.expanduser().resolve()}",
                    "=" * 40,
                    report_text,
                ]
            )
        else:
            # No error occurred
            logger.info(f"Report saved to: {file_path.expanduser().resolve()}")
            report_text = "\n".join(
                [
                    f"Report saved to: {file_path.expanduser().resolve()}",
                    "=" * 40,
                    report_text,
                ]
            )

    return report_text


def run_connector_readiness_test_report(  # noqa: PLR0912, PLR0914, PLR0915 (too complex)
    manifest: Annotated[
        str,
        Field(description="The connector manifest. Can be raw a YAML string or path to YAML file"),
    ],
    config: Annotated[
        dict[str, Any] | None,
        Field(description="Connector configuration"),
    ] = None,
    streams: Annotated[
        str | None,
        Field(
            description="Optional CSV-delimited list of streams to test."
            "If not provided, tests all streams in the manifest (recommended)."
        ),
    ] = None,
    *,
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read per stream", ge=1, le=50000),
    ] = 10000,
    dotenv_file_uris: Annotated[
        str | list[str] | None,
        Field(
            description="Optional paths/URLs to local .env files or Privatebin.net URLs for secret hydration. Can be a single string, comma-separated string, or list of strings. Privatebin secrets may be created at privatebin.net, and must: contain text formatted as a dotenv file, use a password sent via the `PRIVATEBIN_PASSWORD` env var, and not include password text in the URL."
        ),
    ] = None,
) -> str:
    """Execute a connector readiness test and generate a comprehensive markdown report.

    This function is meant to be run after individual streams have been tested with the test read tool,
    to validate things are working properly and generate a report that can be shared with the end user.

    It tests all available streams by reading records up to the specified limit and returns a
    markdown-formatted readiness report with validation warnings and statistics.

    Returns:
        Markdown-formatted readiness report with per-stream statistics and validation warnings
    """
    logger.info("Starting connector readiness test")
    start_time = time.time()
    total_streams_tested = 0
    total_streams_successful = 0
    total_records_count = 0
    stream_results: dict[str, StreamSmokeTest] = {}

    manifest_dict, manifest_path = parse_manifest_input(manifest)
    session_artifacts_dir: Path | None = None
    if manifest_path:
        session_artifacts_dir = Path(manifest_path).parent

    report_output_path: Path | None = (
        Path(session_artifacts_dir) / "connector-readiness-report.md"
        if session_artifacts_dir
        else None
    )

    config = hydrate_config(
        config or {},
        dotenv_file_uris=dotenv_file_uris,
    )

    available_streams = manifest_dict.get("streams", [])
    total_available_streams = len(available_streams)

    stream_names: list[str]
    if isinstance(streams, str):
        stream_names = [s.strip() for s in streams.split(",") if s.strip()]
    else:
        if available_streams:
            invalid_streams = [s for s in available_streams if not isinstance(s, dict)]
            if invalid_streams:
                raise ValueError(
                    f"Invalid manifest structure: 'streams' must be a list of stream definition objects (dicts), "
                    f"but found {len(invalid_streams)} invalid entry(ies). "
                    f"Each stream should be an object with at least a 'name' field and stream configuration. "
                    f"Invalid entries: {invalid_streams[:3]}"
                )

        stream_names = [
            stream.get("name", f"stream_{i}") for i, stream in enumerate(available_streams)
        ]

    logger.info(f"Testing {len(stream_names)} streams: {stream_names}")

    for stream_name in stream_names:
        stream_start_time = time.time()
        total_streams_tested += 1

        try:
            result = execute_stream_test_read(
                manifest=manifest,
                stream_name=stream_name,
                config=config,
                max_records=max_records,
                include_records_data=False,
                include_record_stats=True,
                include_raw_responses_data=False,
                dotenv_file_uris=dotenv_file_uris,
            )

            stream_duration = time.time() - stream_start_time
            records_read = result.records_read

            if result.success:
                total_streams_successful += 1
                total_records_count += records_read

                field_count_warnings = []

                if result.record_stats and result.record_stats.get("num_properties", 0) < 2:
                    field_count_warnings.append(
                        f"Records have only {result.record_stats.get('num_properties', 0)} field(s), expected at least 2"
                    )

                smoke_test_result = StreamSmokeTest(
                    stream_name=stream_name,
                    success=True,
                    records_read=records_read,
                    duration_seconds=stream_duration,
                )
                smoke_test_result.field_count_warnings = field_count_warnings
                stream_results[stream_name] = smoke_test_result
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

        except Exception as ex:
            logger.exception(f"❌ {stream_name}: Exception occurred.")
            stream_results[stream_name] = StreamSmokeTest(
                stream_name=stream_name,
                success=False,
                records_read=0,
                duration_seconds=time.time() - stream_start_time,
                error_message=str(ex),
            )

    total_duration = time.time() - start_time
    overall_success = total_streams_successful == total_streams_tested

    logger.info(
        f"Readiness test completed: {total_streams_successful}/{total_streams_tested} streams successful, "
        f"{total_records_count} total records in {total_duration:.2f}s"
    )

    if not overall_success:
        failed_streams = [name for name, result in stream_results.items() if not result.success]
        error_details = []
        for name, smoke_result in stream_results.items():
            if not smoke_result.success:
                error_msg = getattr(smoke_result, "error_message", "Unknown error")
                error_details.append(f"- **{name}**: {error_msg}")

        report_lines: list[str] = [
            "# Connector Readiness Test Report - FAILED",
            f"**Status**: {total_streams_successful}/{total_streams_tested} streams successful",
            f"**Failed streams**: {', '.join(failed_streams)}",
            f"**Total duration**: {total_duration:.2f}s",
            "\n".join(error_details),
        ]
        return _as_saved_report(
            report_text="\n".join(report_lines),
            file_path=report_output_path,
        )

    report_lines = [
        "# Connector Readiness Test Report",
        "",
        "## Summary",
        "",
        f"- **Streams Tested**: {total_streams_tested} out of {total_available_streams} total streams",
        f"- **Successful Streams**: {total_streams_successful}/{total_streams_tested}",
        f"- **Total Records Extracted**: {total_records_count:,}",
        f"- **Total Duration**: {total_duration:.2f}s",
        "",
        "## Stream Results",
        "",
    ]

    for stream_name, smoke_result in stream_results.items():
        if smoke_result.success:
            warnings = []
            if smoke_result.records_read == 0:
                warnings.append("⚠️ No records extracted")
            elif smoke_result.records_read == 1:
                warnings.append("⚠️ Only 1 record extracted - may indicate pagination issues")
            elif smoke_result.records_read % 10 == 0:
                warnings.append("⚠️ Record count is multiple of 10 - may indicate pagination limit")

            # TODO: Add page size validation
            # if page_size is specified in config, check if records_read is multiple of page_size (important-comment)

            field_warnings = getattr(smoke_result, "field_count_warnings", [])
            if field_warnings:
                warnings.append(f"⚠️ Field count issues: {'; '.join(field_warnings[:2])}")

            report_lines.extend(
                [
                    f"### `{stream_name}` ✅",
                    "",
                    f"- **Records Extracted**: {smoke_result.records_read:,}",
                    f"- **Duration**: {smoke_result.duration_seconds:.2f}s",
                ]
            )

            if warnings:
                report_lines.append(f"- **Warnings**: {' | '.join(warnings)}")
            else:
                report_lines.append("- **Status**: No issues detected")

            report_lines.append("")
        else:
            error_msg = getattr(
                smoke_result,
                "error_message",
                "Unknown error",
            )
            report_lines.extend(
                [
                    f"### `{stream_name}` ❌",
                    "",
                    "- **Status**: Failed",
                    f"- **Error**: {error_msg}",
                    "",
                ]
            )

    return _as_saved_report(
        report_text="\n".join(report_lines),
        file_path=report_output_path,
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
        manifest_dict, _ = parse_manifest_input(manifest)

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
