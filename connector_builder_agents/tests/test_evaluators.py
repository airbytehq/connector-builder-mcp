# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Unit tests for evaluator functions."""

import json
from collections.abc import Mapping
from unittest.mock import patch

import pandas as pd
import pytest
import yaml
from src.evals.evaluators import (
    manifest_validation_eval,
    primary_key_eval,
    readiness_eval,
    streams_eval,
)


@pytest.fixture
def valid_manifest_yaml_simple():
    """Return a valid manifest YAML string with simple streams."""
    return """
version: "4.3.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names:
    - users
streams:
  - type: DeclarativeStream
    name: users
    primary_key:
        - id
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/users"
        http_method: GET
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
  - type: DeclarativeStream
    name: posts
    primary_key:
        - id
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/posts"
        http_method: GET
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
  - type: DeclarativeStream
    name: comments
    primary_key:
        - id
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/comments"
        http_method: GET
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
spec:
  type: Spec
  documentation_url: https://example.com/docs
  connection_specification:
    $schema: http://json-schema.org/draft-07/schema#
    type: object
    additionalProperties: true
    properties: {}
"""


@pytest.fixture
def valid_manifest_yaml_partial():
    """Return a valid manifest YAML with only 2 out of 4 expected streams."""
    return """
version: "4.3.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names:
    - users
streams:
  - type: DeclarativeStream
    name: users
    primary_key:
        - id
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/users"
        http_method: GET
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
  - type: DeclarativeStream
    name: posts
    primary_key:
        - id
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/posts"
        http_method: GET
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
spec:
  type: Spec
  documentation_url: https://example.com/docs
  connection_specification:
    $schema: http://json-schema.org/draft-07/schema#
    type: object
    additionalProperties: true
    properties: {}
"""


@pytest.fixture
def invalid_manifest_yaml():
    """Return an invalid manifest YAML."""
    return """
version: "4.3.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names:
    - users
streams:
  - type: DeclarativeStream
    name: users
    primary_key:
        - id
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/users"
        http_method: GET
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
  - type: DeclarativeStream
    name: posts
    primary_key:
        - id
    retriever:
      type: SimpleRetriever
    requester:
    type: HttpRequester
    url_base: "https://api.example.com"
    path: "/posts"
    http_method: GET
    record_selector:
    type: RecordSelector
    extractor:
        type: DpathExtractor
        field_path: []
spec:
  type: Spec
  documentation_url: https://example.com/docs
  connection_specification:
    $schema: http://json-schema.org/draft-07/schema#
    type: object
    additionalProperties: true
    properties: {}
"""


@pytest.fixture
def valid_readiness_report_passed():
    """Return a readiness report string with passing indicators."""
    return """
# Connector Readiness Report

## Summary
✅ All streams tested successfully

## Stream Results

### users
✅ Status: PASSED
- Records extracted: 150
- No errors

### posts
✅ Status: PASSED
- Records extracted: 200
- No errors

### comments
✅ Status: PASSED
- Records extracted: 500
- No errors

## Conclusion
All tests completed successfully. Connector is ready for use.
"""


@pytest.fixture
def valid_readiness_report_failed():
    """Return a readiness report string with failing indicators."""
    return """
# Connector Readiness Report

## Summary
❌ Tests failed

## Stream Results

### users
❌ Status: FAILED
- Error: Connection timeout
- Records extracted: 0

### posts
❌ Status: FAILED
- Error: Authentication failed
- Records extracted: 0

## Conclusion
Critical errors preventing data extraction. Connector is not ready.
"""


def create_connector_builder_eval_task_output_dict(readiness_report=None, manifest=None) -> dict:
    """Helper to create properly structured output dict."""
    return {
        "workspace_dir": "/tmp/test",
        "success": True,
        "final_output": "Build completed",
        "num_turns": 5,
        "artifacts": {
            "readiness_report": readiness_report,
            "manifest": manifest,
        },
    }


def create_expected_dict(expected_streams: list[Mapping]):
    """Helper to create properly structured expected dict.

    Args:
        expected_streams: Mapping of expected streams
    """
    expected_obj = {"expected_streams": expected_streams}
    return {"expected": json.dumps(expected_obj)}


def test_manifest_validation_eval_success(valid_manifest_yaml_simple):
    """Test manifest_validation_eval returns 1 when manifest is valid."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_simple)
    result = manifest_validation_eval(output)
    assert result == 1


def test_manifest_validation_eval_failure(valid_manifest_yaml_partial):
    """Test manifest_validation_eval returns 0 when manifest is invalid."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_partial)
    result = manifest_validation_eval(output)
    assert result == 0


def test_readiness_eval_passing_report(valid_readiness_report_passed):
    """Test readiness_eval returns 1 when report indicates PASSED."""
    output = create_connector_builder_eval_task_output_dict(
        readiness_report=valid_readiness_report_passed
    )

    mock_df = pd.DataFrame([{"label": "PASSED", "explanation": "All tests passed successfully"}])

    with patch("src.evals.evaluators.llm_classify") as mock_llm_classify:
        mock_llm_classify.return_value = mock_df
        result = readiness_eval(output)
        assert result == 1


def test_readiness_eval_failing_report(valid_readiness_report_failed):
    """Test readiness_eval returns 0 when report indicates FAILED."""
    output = create_connector_builder_eval_task_output_dict(
        readiness_report=valid_readiness_report_failed
    )

    mock_df = pd.DataFrame(
        [{"label": "FAILED", "explanation": "Tests failed due to critical errors"}]
    )

    with patch("src.evals.evaluators.llm_classify") as mock_llm_classify:
        mock_llm_classify.return_value = mock_df
        result = readiness_eval(output)
        assert result == 0


def test_streams_eval_perfect_match(valid_manifest_yaml_simple):
    """Test streams_eval returns 1.0 when all expected streams are present."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_simple)
    expected_streams = [
        {"name": "users", "primary_key": ["id"]},
        {"name": "posts", "primary_key": ["id"]},
        {"name": "comments", "primary_key": ["id"]},
    ]
    expected = create_expected_dict(expected_streams)
    result = streams_eval(expected, output)

    assert result == 1.0


def test_streams_eval_partial_match(valid_manifest_yaml_partial):
    """Test streams_eval returns 0.5 when 2 out of 4 expected streams are present."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_partial)
    expected_streams = [
        {"name": "users", "primary_key": ["id"]},
        {"name": "posts", "primary_key": ["id"]},
        {"name": "comments", "primary_key": ["id"]},
        {"name": "todos", "primary_key": ["id"]},
    ]
    expected = create_expected_dict(expected_streams)
    result = streams_eval(expected, output)

    assert result == 0.5


def test_streams_eval_no_match(valid_manifest_yaml_simple):
    """Test streams_eval returns 0.0 when none of the expected streams are present."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_simple)
    # Manifest has users, posts, comments; we expect completely different streams
    expected_streams = [
        {"name": "products", "primary_key": ["id"]},
        {"name": "orders", "primary_key": ["id"]},
    ]
    expected = create_expected_dict(expected_streams)
    result = streams_eval(expected, output)

    assert result == 0.0


def test_streams_eval_extra_streams_in_output(valid_manifest_yaml_simple):
    """Test streams_eval returns 1.0 when all expected streams are present even with extras."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_simple)
    expected_streams = [
        {"name": "users", "primary_key": ["id"]},
    ]
    expected = create_expected_dict(expected_streams)
    result = streams_eval(expected, output)

    assert result == 1.0


@pytest.mark.parametrize(
    "primary_key",
    [
        (None),
        (""),
        (["id"]),
        ([["id"]]),
        (["id", "user_id"]),
        ([["id"], ["user_id"]]),
    ],
)
def test_primary_key_eval_various_formats(valid_manifest_yaml_simple, primary_key):
    """Test primary_key_eval returns 1.0 for various primary key formats."""
    manifest_dict = yaml.safe_load(valid_manifest_yaml_simple)
    for stream in manifest_dict["streams"]:
        if stream["name"] == "users":
            stream["primary_key"] = primary_key

    # rebuild YAML string
    manifest_modified = yaml.dump(manifest_dict)
    output = create_connector_builder_eval_task_output_dict(manifest=manifest_modified)
    expected_streams = [
        {"name": "users", "primary_key": primary_key},
    ]
    expected = create_expected_dict(expected_streams)
    result = primary_key_eval(expected, output)
    assert result == 1.0


def test_primary_key_eval_no_match(valid_manifest_yaml_simple):
    """Test primary_key_eval returns 0.0 when no expected streams are present."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_simple)
    expected_streams = [
        {"name": "products", "primary_key": ["id"]},
    ]
    expected = create_expected_dict(expected_streams)
    result = primary_key_eval(expected, output)
    assert result == 0.0


def test_primary_key_partial_match(valid_manifest_yaml_simple):
    """Test primary_key_eval returns 0.5 when 1 out of 2 expected streams are present."""
    output = create_connector_builder_eval_task_output_dict(manifest=valid_manifest_yaml_simple)
    expected_streams = [
        {"name": "users", "primary_key": ["id"]},
        {"name": "posts", "primary_key": ["uuid"]},
    ]
    expected = create_expected_dict(expected_streams)
    result = primary_key_eval(expected, output)
    assert result == 0.5
