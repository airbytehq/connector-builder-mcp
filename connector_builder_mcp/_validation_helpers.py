"""Validation helper functions for manifest validation.

This module provides shared validation logic that can be used by both
the validate_manifest tool and other tools that need validation feedback.
"""

import logging
from typing import Any

from jsonschema import Draft7Validator, ValidationError, validate

from airbyte_cdk.connector_builder.connector_builder_handler import (
    create_source,
    get_limits,
    resolve_manifest,
)
from airbyte_cdk.sources.declarative.parsers.manifest_component_transformer import (
    ManifestComponentTransformer,
)
from airbyte_cdk.sources.declarative.parsers.manifest_reference_resolver import (
    ManifestReferenceResolver,
)

from connector_builder_mcp._util import (
    is_valid_declarative_source_manifest,
    parse_manifest_input,
    validate_manifest_structure,
)


logger = logging.getLogger(__name__)


def _get_declarative_component_schema() -> dict[str, Any]:
    """Get the declarative component schema from the CDK.

    Returns:
        The JSON schema for declarative components
    """
    import pkgutil
    from typing import cast

    schema_text = pkgutil.get_data(
        "airbyte_cdk.sources.declarative.parsers",
        "schemas/declarative_component_schema.yaml",
    )
    if schema_text is None:
        raise ValueError("Could not load declarative component schema")

    import yaml

    return cast(dict[str, Any], yaml.safe_load(schema_text))


def _format_validation_error(error: ValidationError) -> str:
    """Format a JSON schema validation error into a readable message.

    Args:
        error: The validation error to format

    Returns:
        Formatted error message
    """
    path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
    message = error.message

    if error.context:
        context_messages = [f"  - {e.message}" for e in error.context]
        context_str = "\n".join(context_messages)
        return f"Validation error at {path}: {message}\nContext:\n{context_str}"

    return f"Validation error at {path}: {message}"


def _validate_stream_schemas(manifest_dict: dict[str, Any]) -> list[str]:
    """Validate that all stream schemas are valid JSON Schema objects.

    This is a workaround for https://github.com/airbytehq/airbyte-python-cdk/issues/832
    The CDK's declarative component schema doesn't validate that inline stream schemas
    are valid JSON Schemas, which can lead to cryptic errors at runtime.

    Args:
        manifest_dict: The manifest dictionary to validate

    Returns:
        List of validation error messages (empty if all schemas are valid)
    """
    errors: list[str] = []
    validator = Draft7Validator(Draft7Validator.META_SCHEMA)

    streams = manifest_dict.get("streams", [])
    if not streams:
        return errors

    for i, stream in enumerate(streams):
        if not isinstance(stream, dict):
            continue

        stream_name = stream.get("name", f"stream_{i}")

        # Check for inline schema (direct schema field)
        schema = stream.get("schema")

        # Check for schema_loader with inline schema
        if not schema and "schema_loader" in stream:
            schema_loader = stream.get("schema_loader")
            if isinstance(schema_loader, dict):
                loader_type = schema_loader.get("type", "")
                # Only validate InlineSchemaLoader schemas
                if loader_type == "InlineSchemaLoader":
                    schema = schema_loader.get("schema")

        # Skip if no schema to validate (might be using dynamic schema loader)
        if not schema:
            continue

        # Validate that schema is a dict
        if not isinstance(schema, dict):
            errors.append(
                f"Stream '{stream_name}': Schema must be an object (dict), got {type(schema).__name__}. "
                f"Invalid schemas can cause runtime errors."
            )
            continue

        # Validate against JSON Schema meta-schema
        schema_errors = list(validator.iter_errors(schema))
        if schema_errors:
            error_messages = []
            for error in schema_errors[:3]:  # Limit to first 3 errors
                path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                error_messages.append(f"  - At '{path}': {error.message}")

            errors.append(
                f"Stream '{stream_name}': Invalid JSON Schema definition.\n"
                + "\n".join(error_messages)
                + (f"\n  - ... and {len(schema_errors) - 3} more errors" if len(schema_errors) > 3 else "")
            )

    return errors


def validate_manifest_content(
    manifest_text: str,
) -> tuple[bool, list[str], list[str], dict[str, Any] | None]:
    """Validate manifest content and return validation results.

    This is a helper function that performs the core validation logic
    without requiring a session context. It can be called by both the
    validate_manifest tool and other tools that need validation feedback.

    Args:
        manifest_text: The manifest YAML content to validate

    Returns:
        Tuple of (is_valid, errors, warnings, resolved_manifest):
        - is_valid: bool - Whether validation passed
        - errors: list[str] - List of validation errors
        - warnings: list[str] - List of validation warnings
        - resolved_manifest: dict[str, Any] | None - Resolved manifest dict if successful
    """
    errors: list[str] = []
    warnings: list[str] = []
    resolved_manifest: dict[str, Any] | None = None

    manifest_dict, _ = parse_manifest_input(manifest_text)

    if not validate_manifest_structure(manifest_dict):
        errors.append(
            "Manifest missing required fields: version, type, check, and either streams or dynamic_streams"
        )
        return (False, errors, warnings, resolved_manifest)

    # Validate stream schemas BEFORE preprocessing
    # Workaround for https://github.com/airbytehq/airbyte-python-cdk/issues/832
    logger.info("Validating stream schemas against JSON Schema meta-schema")
    stream_schema_errors = _validate_stream_schemas(manifest_dict)
    if stream_schema_errors:
        logger.error(f"Found {len(stream_schema_errors)} invalid stream schema(s)")
        errors.extend(stream_schema_errors)
        return (False, errors, warnings, resolved_manifest)

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
        return (False, errors, warnings, resolved_manifest)

    try:
        is_valid, error = is_valid_declarative_source_manifest(manifest_dict)
        if not is_valid and error:
            errors.append(error)
            return (False, errors, warnings, resolved_manifest)
    except Exception as e:
        errors.append(f"Error validating manifest: {e}")
        return (False, errors, warnings, resolved_manifest)

    try:
        schema = _get_declarative_component_schema()
        validate(manifest_dict, schema)
        logger.info("JSON schema validation passed")
    except ValidationError as schema_error:
        detailed_error = _format_validation_error(schema_error)
        logger.error(f"JSON schema validation failed: {detailed_error}")
        errors.append(detailed_error)
        return (False, errors, warnings, resolved_manifest)
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

    is_valid = len(errors) == 0

    return (is_valid, errors, warnings, resolved_manifest)
