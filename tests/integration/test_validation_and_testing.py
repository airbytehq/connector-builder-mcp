"""Integration tests for Builder MCP using real manifest examples."""

import concurrent.futures
import time
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from connector_builder_mcp.mcp.manifest_edits import (
    get_session_manifest_content,
    set_session_manifest_content,
)
from connector_builder_mcp.mcp.manifest_tests import (
    StreamTestResult,
    execute_dynamic_manifest_resolution_test,
    execute_stream_test_read,
    run_connector_readiness_test_report,
    validate_manifest,
)


# Test manifest constants
MALFORMED_MANIFEST_WITH_STRING_STREAMS = """
version: 4.6.2
type: DeclarativeSource
check:
  type: CheckStream
  stream_names:
    - test_stream
streams:
  - test_stream
  - another_stream
spec:
  type: Spec
  connection_specification:
    type: object
    properties: {}
"""

MANIFEST_WITHOUT_SCHEMA = """
version: 4.6.2
type: DeclarativeSource
check:
  type: CheckStream
  stream_names:
    - test_stream
streams:
  - type: DeclarativeStream
    name: test_stream
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: https://rickandmortyapi.com/api
        path: /character
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path:
            - results
spec:
  type: Spec
  connection_specification:
    type: object
    properties: {}
"""

MANIFEST_WITH_SCHEMA = """
version: 4.6.2
type: DeclarativeSource
check:
  type: CheckStream
  stream_names:
    - test_stream
streams:
  - type: DeclarativeStream
    name: test_stream
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: https://rickandmortyapi.com/api
        path: /character
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path:
            - results
    schema:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
spec:
  type: Spec
  connection_specification:
    type: object
    properties: {}
"""


@pytest.fixture
def rick_and_morty_manifest_yaml(
    resources_path: Path,
) -> str:
    """Load the Rick and Morty API manifest for testing."""
    manifest_path: Path = resources_path / "rick_and_morty_manifest.yaml"
    return manifest_path.read_text(encoding="utf-8")


@pytest.fixture
def rick_and_morty_manifest_dict(
    rick_and_morty_manifest_yaml: str,
) -> dict[str, Any]:
    """Load the Rick and Morty API manifest as a dictionary."""
    return cast(dict[str, Any], yaml.safe_load(rick_and_morty_manifest_yaml))


@pytest.fixture
def simple_api_manifest_yaml(
    resources_path: Path,
) -> str:
    """Load the simple API manifest for testing."""
    manifest_path: Path = resources_path / "simple_api_manifest.yaml"
    return manifest_path.read_text(encoding="utf-8")


@pytest.fixture
def invalid_manifest_yaml() -> str:
    """Invalid manifest for error testing."""
    return "invalid: manifest\nmissing: required_fields"


@pytest.fixture
def malformed_manifest_with_string_streams() -> str:
    """Malformed manifest with streams as list of strings."""
    return MALFORMED_MANIFEST_WITH_STRING_STREAMS


@pytest.fixture
def manifest_without_schema() -> str:
    """Test manifest without schema definition."""
    return MANIFEST_WITHOUT_SCHEMA


@pytest.fixture
def manifest_with_schema() -> str:
    """Test manifest with schema definition."""
    return MANIFEST_WITH_SCHEMA


def test_validate_rick_and_morty_manifest(
    ctx,
    rick_and_morty_manifest_yaml,
) -> None:
    """Test validation of Rick and Morty API manifest."""
    result = validate_manifest(ctx, manifest=rick_and_morty_manifest_yaml)

    assert result.is_valid
    assert len(result.errors) == 0
    assert result.resolved_manifest is not None


def test_resolve_rick_and_morty_manifest(
    ctx,
    rick_and_morty_manifest_yaml,
) -> None:
    """Test resolution of Rick and Morty API manifest."""
    result = execute_dynamic_manifest_resolution_test(
        ctx, manifest=rick_and_morty_manifest_yaml, config={}
    )

    assert isinstance(result, dict)
    assert "streams" in result, f"Expected 'streams' key in resolved manifest, got: {result}"


def test_execute_stream_test_read_rick_and_morty(
    ctx,
    rick_and_morty_manifest_yaml,
) -> None:
    """Test reading from Rick and Morty characters stream."""
    result = execute_stream_test_read(
        ctx,
        stream_name="characters",
        manifest=rick_and_morty_manifest_yaml,
        config={},
        max_records=5,
    )

    assert isinstance(result, StreamTestResult)
    assert result.message is not None
    if result.success:
        assert result.records_read > 0
        assert "Successfully read" in result.message and "records from stream" in result.message


@pytest.mark.parametrize(
    "manifest_fixture,expected_valid",
    [
        ("rick_and_morty_manifest_yaml", True),
        ("simple_api_manifest_yaml", True),
        ("invalid_manifest_yaml", False),
    ],
)
def test_manifest_validation_scenarios(
    ctx,
    manifest_fixture,
    expected_valid,
    request,
):
    """Test validation of different manifest scenarios."""
    manifest = request.getfixturevalue(manifest_fixture)

    result = validate_manifest(ctx, manifest=manifest)
    assert result.is_valid == expected_valid

    if expected_valid:
        assert result.resolved_manifest is not None
        assert len(result.errors) == 0
    else:
        assert len(result.errors) > 0


def test_complete_connector_workflow(
    ctx,
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test complete workflow: validate -> resolve -> test stream read."""
    validation_result = validate_manifest(ctx, manifest=rick_and_morty_manifest_yaml)
    assert validation_result.is_valid
    assert validation_result.resolved_manifest is not None

    resolved_manifest = execute_dynamic_manifest_resolution_test(
        ctx, manifest=rick_and_morty_manifest_yaml, config={}
    )
    assert isinstance(resolved_manifest, dict)
    assert "streams" in resolved_manifest

    stream_result = execute_stream_test_read(
        ctx,
        stream_name="characters",
        manifest=rick_and_morty_manifest_yaml,
        config={},
        max_records=3,
    )
    assert isinstance(stream_result, StreamTestResult)
    assert stream_result.message is not None


def test_error_handling_scenarios(
    ctx,
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test various error handling scenarios."""
    result = execute_stream_test_read(
        ctx,
        stream_name="nonexistent_stream",
        manifest=rick_and_morty_manifest_yaml,
        config={},
        max_records=1,
    )
    assert isinstance(result, StreamTestResult)


@pytest.mark.requires_creds
def test_performance_multiple_tool_calls(
    ctx,
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test performance with multiple rapid tool calls."""
    start_time = time.time()

    for _ in range(5):
        validate_manifest(ctx, manifest=rick_and_morty_manifest_yaml)
        execute_dynamic_manifest_resolution_test(
            ctx, manifest=rick_and_morty_manifest_yaml, config={}
        )

    end_time = time.time()
    duration = end_time - start_time

    assert duration < 20.0, f"Multiple tool calls took too long: {duration}s"


def test_simple_api_manifest_workflow(
    ctx,
    simple_api_manifest_yaml,
) -> None:
    """Test workflow with simple API manifest."""
    validation_result = validate_manifest(ctx, manifest=simple_api_manifest_yaml)
    assert validation_result.is_valid

    resolved_manifest = execute_dynamic_manifest_resolution_test(
        ctx, manifest=simple_api_manifest_yaml, config={}
    )
    assert isinstance(resolved_manifest, dict)
    assert "streams" in resolved_manifest


def test_malformed_manifest_streams_validation(
    ctx,
    malformed_manifest_with_string_streams: str,
) -> None:
    """Test that malformed manifest with streams as list of strings raises clear error."""
    with pytest.raises(
        ValueError,
        match=r"Invalid manifest structure.*streams.*must be a list of stream definition objects",
    ):
        run_connector_readiness_test_report(
            ctx, manifest=malformed_manifest_with_string_streams, config={}, max_records=5
        )


@pytest.mark.parametrize(
    "manifest_fixture,stream_name",
    [
        ("rick_and_morty_manifest_yaml", "characters"),
        ("simple_api_manifest_yaml", "users"),
    ],
)
def test_sample_manifests_with_both_tools(
    ctx,
    manifest_fixture,
    stream_name,
    request,
):
    """Test that both execute_stream_test_read and run_connector_readiness_test_report work with sample manifests."""
    manifest = request.getfixturevalue(manifest_fixture)

    stream_result = execute_stream_test_read(
        ctx,
        stream_name=stream_name,
        manifest=manifest,
        config={},
        max_records=5,
    )
    assert isinstance(stream_result, StreamTestResult)
    assert stream_result.message is not None
    if stream_result.success:
        assert stream_result.records_read >= 0
        assert (
            "Successfully read" in stream_result.message
            and "records from stream" in stream_result.message
        )

    readiness_result = run_connector_readiness_test_report(
        ctx,
        manifest=manifest,
        config={},
        max_records=10,
    )
    assert isinstance(readiness_result, str)
    assert "# Connector Readiness Test Report" in readiness_result
    assert stream_name in readiness_result

    if "FAILED" in readiness_result:
        assert "Failed streams" in readiness_result
        assert "Total duration" in readiness_result
    else:
        assert "Records Extracted" in readiness_result


def test_concurrent_tool_execution(
    ctx,
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test concurrent execution of multiple tools."""

    def run_validation():
        return validate_manifest(ctx, manifest=rick_and_morty_manifest_yaml)

    def run_resolution():
        return execute_dynamic_manifest_resolution_test(
            ctx,
            manifest=rick_and_morty_manifest_yaml,
            config={},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(run_validation),
            executor.submit(run_resolution),
            executor.submit(run_validation),
        ]

        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    assert len(results) == 3
    for result in results:
        assert result is not None


def test_schema_validation_with_missing_schema(
    ctx,
    manifest_without_schema: str,
) -> None:
    """Test that schema validation detects missing schemas in manifest."""
    result = execute_stream_test_read(
        ctx,
        stream_name="test_stream",
        manifest=manifest_without_schema,
        config={},
        max_records=5,
    )

    assert isinstance(result, StreamTestResult)
    assert result.inferred_json_schema is not None or result.records_read == 0

    if result.records_read > 0:
        assert len(result.schema_warnings) > 0
        assert any(
            "missing a schema definition" in warning.lower() for warning in result.schema_warnings
        )


def test_schema_validation_returns_inferred_schema(
    ctx,
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test that inferred schema is returned from stream test read when requested."""
    result = execute_stream_test_read(
        ctx,
        stream_name="characters",
        manifest=rick_and_morty_manifest_yaml,
        config={},
        max_records=5,
        include_inferred_json_schema=True,
    )

    assert isinstance(result, StreamTestResult)

    if result.success and result.records_read > 0:
        assert result.inferred_json_schema is not None
        assert isinstance(result.inferred_json_schema, dict)

        if "properties" in result.inferred_json_schema:
            assert isinstance(result.inferred_json_schema["properties"], dict)


def test_readiness_report_includes_schema_warnings(
    ctx,
    manifest_without_schema: str,
) -> None:
    """Test that readiness report includes schema warnings."""
    report = run_connector_readiness_test_report(
        ctx,
        manifest=manifest_without_schema,
        config={},
        max_records=10,
    )

    assert isinstance(report, str)
    assert "# Connector Readiness Test Report" in report

    if (
        "Records Extracted" in report
        and "0" not in report.split("Records Extracted")[1].split("\n")[0]
    ):
        assert "Schema:" in report or "schema" in report.lower()


def test_include_inferred_schema_parameter(
    ctx,
    manifest_without_schema: str,
) -> None:
    """Test include_inferred_json_schema parameter controls schema inclusion."""
    result_always = execute_stream_test_read(
        ctx,
        stream_name="test_stream",
        manifest=manifest_without_schema,
        config={},
        max_records=5,
        include_inferred_json_schema=True,
    )
    assert isinstance(result_always, StreamTestResult)
    if result_always.records_read > 0:
        assert result_always.inferred_json_schema is not None

    result_never = execute_stream_test_read(
        ctx,
        stream_name="test_stream",
        manifest=manifest_without_schema,
        config={},
        max_records=5,
        include_inferred_json_schema=False,
    )
    assert isinstance(result_never, StreamTestResult)
    assert result_never.inferred_json_schema is None

    result_default = execute_stream_test_read(
        ctx,
        stream_name="test_stream",
        manifest=manifest_without_schema,
        config={},
        max_records=5,
        include_inferred_json_schema=None,
    )
    assert isinstance(result_default, StreamTestResult)
    if result_default.records_read > 0 and len(result_default.schema_warnings) > 0:
        assert result_default.inferred_json_schema is not None


def test_auto_update_schema_with_session_manifest(
    ctx,
    manifest_without_schema: str,
) -> None:
    """Test auto_update_schema parameter updates session manifest."""
    session_id = ctx.session_id
    set_session_manifest_content(manifest_without_schema, session_id)

    result = execute_stream_test_read(
        ctx,
        stream_name="test_stream",
        manifest=None,
        config={},
        max_records=5,
        auto_update_schema=True,
    )

    assert isinstance(result, StreamTestResult)
    if result.records_read > 0:
        assert result.inferred_json_schema is not None or len(result.schema_warnings) > 0, (
            "Expected either inferred_json_schema or schema_warnings when records were read"
        )

        has_update_msg = any("Auto-updated schema" in warning for warning in result.schema_warnings)
        has_error_msg = any(
            "Failed to auto-update" in warning or "Cannot auto-update" in warning
            for warning in result.schema_warnings
        )

        assert has_update_msg or has_error_msg, (
            f"Expected auto-update success or error message, got: {result.schema_warnings}"
        )

        if has_update_msg:
            updated_manifest = get_session_manifest_content(session_id)
            assert updated_manifest is not None
            assert "schema:" in updated_manifest or "properties:" in updated_manifest


def test_auto_update_schema_none_only_fixes_problems(ctx, manifest_with_schema: str) -> None:
    """Test auto_update_schema=None only updates when there are schema issues."""
    session_id = ctx.session_id
    set_session_manifest_content(manifest_with_schema, session_id)
    original_manifest = get_session_manifest_content(session_id)

    result = execute_stream_test_read(
        ctx,
        stream_name="test_stream",
        manifest=None,
        config={},
        max_records=5,
        auto_update_schema=None,
    )

    assert isinstance(result, StreamTestResult)

    updated_manifest = get_session_manifest_content(session_id)
    if result.records_read > 0 and len(result.schema_warnings) == 0:
        assert updated_manifest == original_manifest
