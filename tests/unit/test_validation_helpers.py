"""Unit tests for validation helper functions."""

import connector_builder_mcp._validation_helpers as vh
from connector_builder_mcp._validation_helpers import validate_manifest_content


def test_schema_load_failure_is_fatal(monkeypatch):
    """Test that schema loading failures result in fatal validation errors."""

    def boom():
        raise ValueError("Schema file not found")

    monkeypatch.setattr(vh, "_get_declarative_component_schema", boom)

    # Use a minimal valid manifest
    manifest_yaml = """
version: 6.51.0
type: DeclarativeSource
check:
  type: CheckStream
  stream_names: []
streams: []
spec:
  type: Spec
  connection_specification:
    type: object
    properties: {}
"""

    is_valid, errors, warnings, resolved = validate_manifest_content(manifest_yaml)

    # Validation should fail
    assert not is_valid
    # Should have an error about schema loading
    assert any("Could not load declarative component schema" in e for e in errors)
    # Error should mention it's fatal
    assert any("Fatal" in e for e in errors)


def test_schema_validation_unexpected_error_is_fatal(monkeypatch):
    """Test that unexpected errors during validation result in fatal errors."""

    def boom_validate(instance, schema):
        raise RuntimeError("Unexpected validation error")

    monkeypatch.setattr(vh, "validate", boom_validate)

    # Use a minimal valid manifest
    manifest_yaml = """
version: 6.51.0
type: DeclarativeSource
check:
  type: CheckStream
  stream_names: []
streams: []
spec:
  type: Spec
  connection_specification:
    type: object
    properties: {}
"""

    is_valid, errors, warnings, resolved = validate_manifest_content(manifest_yaml)

    # Validation should fail
    assert not is_valid
    # Should have an error about unexpected validation error
    assert any("Unexpected error during JSON schema validation" in e for e in errors)
    # Error should mention it's fatal
    assert any("Fatal" in e for e in errors)
