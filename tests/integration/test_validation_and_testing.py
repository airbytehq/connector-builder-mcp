"""Integration tests for Builder MCP using real manifest examples."""

import concurrent.futures
import time
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from connector_builder_mcp.validation_testing import (
    StreamTestResult,
    execute_dynamic_manifest_resolution_test,
    execute_stream_test_read,
    run_connector_readiness_test_report,
    validate_manifest,
)


@pytest.fixture
def rick_and_morty_manifest_yaml(resources_path: Path) -> str:
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
def simple_api_manifest_yaml(resources_path: Path) -> str:
    """Load the simple API manifest for testing."""
    manifest_path: Path = resources_path / "simple_api_manifest.yaml"
    return manifest_path.read_text(encoding="utf-8")


@pytest.fixture
def invalid_manifest_yaml() -> str:
    """Invalid manifest for error testing."""
    return "invalid: manifest\nmissing: required_fields"


def test_validate_rick_and_morty_manifest(
    rick_and_morty_manifest_yaml,
) -> None:
    """Test validation of Rick and Morty API manifest."""
    result = validate_manifest(rick_and_morty_manifest_yaml)

    assert result.is_valid
    assert len(result.errors) == 0
    assert result.resolved_manifest is not None


def test_resolve_rick_and_morty_manifest(
    rick_and_morty_manifest_yaml,
) -> None:
    """Test resolution of Rick and Morty API manifest."""
    result = execute_dynamic_manifest_resolution_test(rick_and_morty_manifest_yaml, {})

    assert isinstance(result, dict)
    assert "streams" in result, f"Expected 'streams' key in resolved manifest, got: {result}"


def test_execute_stream_test_read_rick_and_morty(
    rick_and_morty_manifest_yaml,
) -> None:
    """Test reading from Rick and Morty characters stream."""
    result = execute_stream_test_read(
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
    manifest_fixture,
    expected_valid,
    request,
):
    """Test validation of different manifest scenarios."""
    manifest = request.getfixturevalue(manifest_fixture)

    result = validate_manifest(manifest)
    assert result.is_valid == expected_valid

    if expected_valid:
        assert result.resolved_manifest is not None
        assert len(result.errors) == 0
    else:
        assert len(result.errors) > 0


def test_complete_connector_workflow(
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test complete workflow: validate -> resolve -> test stream read."""
    validation_result = validate_manifest(rick_and_morty_manifest_yaml)
    assert validation_result.is_valid
    assert validation_result.resolved_manifest is not None

    resolved_manifest = execute_dynamic_manifest_resolution_test(rick_and_morty_manifest_yaml, {})
    assert isinstance(resolved_manifest, dict)
    assert "streams" in resolved_manifest

    stream_result = execute_stream_test_read(
        stream_name="characters",
        manifest=rick_and_morty_manifest_yaml,
        config={},
        max_records=3,
    )
    assert isinstance(stream_result, StreamTestResult)
    assert stream_result.message is not None


def test_error_handling_scenarios(
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test various error handling scenarios."""
    result = execute_stream_test_read(
        stream_name="nonexistent_stream",
        manifest=rick_and_morty_manifest_yaml,
        config={},
        max_records=1,
    )
    assert isinstance(result, StreamTestResult)


@pytest.mark.requires_creds
def test_performance_multiple_tool_calls(
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test performance with multiple rapid tool calls."""
    start_time = time.time()

    for _ in range(5):
        validate_manifest(rick_and_morty_manifest_yaml)
        execute_dynamic_manifest_resolution_test(rick_and_morty_manifest_yaml, config={})

    end_time = time.time()
    duration = end_time - start_time

    assert duration < 20.0, f"Multiple tool calls took too long: {duration}s"


def test_simple_api_manifest_workflow(simple_api_manifest_yaml) -> None:
    """Test workflow with simple API manifest."""
    validation_result = validate_manifest(simple_api_manifest_yaml)
    assert validation_result.is_valid

    resolved_manifest = execute_dynamic_manifest_resolution_test(
        simple_api_manifest_yaml, config={}
    )
    assert isinstance(resolved_manifest, dict)
    assert "streams" in resolved_manifest


def test_malformed_manifest_streams_validation() -> None:
    """Test that malformed manifest with streams as list of strings raises clear error."""
    malformed_manifest = """
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

    with pytest.raises(
        ValueError,
        match=r"Invalid manifest structure.*streams.*must be a list of stream definition objects",
    ):
        run_connector_readiness_test_report(manifest=malformed_manifest, config={}, max_records=5)


@pytest.mark.parametrize(
    "manifest_fixture,stream_name",
    [
        ("rick_and_morty_manifest_yaml", "characters"),
        ("simple_api_manifest_yaml", "users"),
    ],
)
def test_sample_manifests_with_both_tools(
    manifest_fixture,
    stream_name,
    request,
):
    """Test that both execute_stream_test_read and run_connector_readiness_test_report work with sample manifests."""
    manifest = request.getfixturevalue(manifest_fixture)

    stream_result = execute_stream_test_read(
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
    rick_and_morty_manifest_yaml: str,
) -> None:
    """Test concurrent execution of multiple tools."""

    def run_validation():
        return validate_manifest(rick_and_morty_manifest_yaml)

    def run_resolution():
        return execute_dynamic_manifest_resolution_test(
            rick_and_morty_manifest_yaml,
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
