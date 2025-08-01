"""Integration tests for Builder MCP using real manifest examples."""

import concurrent.futures
import time
from pathlib import Path

import pytest
import requests
import yaml

from builder_mcp._connector_builder import (
    _get_topic_mapping,
    StreamTestResult,
    execute_stream_read,
    get_connector_builder_docs,
    get_resolved_manifest,
    validate_manifest,
)


@pytest.fixture
def rick_and_morty_manifest():
    """Load the Rick and Morty API manifest for testing."""
    manifest_path = Path(__file__).parent / "resources" / "rick_and_morty_manifest.yaml"
    with manifest_path.open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def simple_api_manifest():
    """Load the simple API manifest for testing."""
    manifest_path = Path(__file__).parent / "resources" / "simple_api_manifest.yaml"
    with manifest_path.open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def invalid_manifest():
    """Invalid manifest for error testing."""
    return {"invalid": "manifest", "missing": "required_fields"}


@pytest.fixture
def empty_config():
    """Empty configuration for testing."""
    return {}


class TestManifestIntegration:
    """Integration tests using real manifest examples."""

    def test_validate_rick_and_morty_manifest(self, rick_and_morty_manifest, empty_config):
        """Test validation of Rick and Morty API manifest."""
        result = validate_manifest(rick_and_morty_manifest, empty_config)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.resolved_manifest is not None

    def test_resolve_rick_and_morty_manifest(self, rick_and_morty_manifest, empty_config):
        """Test resolution of Rick and Morty API manifest."""
        result = get_resolved_manifest(rick_and_morty_manifest, empty_config)

        assert isinstance(result, dict)
        assert "streams" in result, f"Expected 'streams' key in resolved manifest, got: {result}"

    def test_execute_stream_read_rick_and_morty(self, rick_and_morty_manifest, empty_config):
        """Test reading from Rick and Morty characters stream."""
        result = execute_stream_read(
            rick_and_morty_manifest, empty_config, "characters", max_records=5
        )

        assert result.success, f"Stream read failed: {result.message}"
        assert result.records_read > 0
        assert "Successfully read from stream" in result.message


class TestConnectorBuilderDocs:
    """Test connector builder documentation functionality."""

    def test_get_connector_builder_docs_overview(self):
        """Test that overview is returned when no topic is specified."""
        result = get_connector_builder_docs()

        assert "# Connector Builder Documentation" in result
        assert "Use the manifest YAML JSON schema" in result
        assert "For detailed documentation on specific components" in result

    @pytest.mark.parametrize("topic", list(_get_topic_mapping().keys()))
    def test_topic_urls_are_accessible(self, topic):
        """Test that all topic URLs in the mapping are accessible."""
        topic_mapping = _get_topic_mapping()
        relative_path, description = topic_mapping[topic]
        raw_github_url = (
            f"https://raw.githubusercontent.com/airbytehq/airbyte/master/{relative_path}"
        )

        response = requests.get(raw_github_url, timeout=30)
        assert response.status_code == 200, (
            f"Topic '{topic}' URL {raw_github_url} returned status {response.status_code}"
        )
        assert len(response.text) > 0, f"Topic '{topic}' returned empty content"

    def test_get_connector_builder_docs_specific_topic(self):
        """Test that specific topic documentation is returned correctly."""
        result = get_connector_builder_docs("overview")

        assert "# overview Documentation" in result
        assert len(result) > 100

    def test_get_connector_builder_docs_invalid_topic(self):
        """Test handling of invalid topic requests."""
        result = get_connector_builder_docs("nonexistent-topic")

        assert "Topic 'nonexistent-topic' not found" in result
        assert "Available topics:" in result


class TestHighLevelMCPWorkflows:
    """High-level integration tests for complete MCP workflows."""

    @pytest.mark.parametrize(
        "manifest_fixture,expected_valid",
        [
            ("rick_and_morty_manifest", True),
            ("simple_api_manifest", True),
            ("invalid_manifest", False),
        ],
    )
    def test_manifest_validation_scenarios(
        self, manifest_fixture, expected_valid, request, empty_config
    ):
        """Test validation of different manifest scenarios."""
        manifest = request.getfixturevalue(manifest_fixture)
        config = {} if manifest_fixture == "invalid_manifest" else empty_config

        result = validate_manifest(manifest, config)
        assert result.is_valid == expected_valid

        if expected_valid:
            assert result.resolved_manifest is not None
            assert len(result.errors) == 0
        else:
            assert len(result.errors) > 0

    def test_complete_connector_workflow(self, rick_and_morty_manifest, empty_config):
        """Test complete workflow: validate -> resolve -> test stream read."""
        validation_result = validate_manifest(rick_and_morty_manifest, empty_config)
        assert validation_result.is_valid
        assert validation_result.resolved_manifest is not None

        resolved_manifest = get_resolved_manifest(rick_and_morty_manifest, empty_config)
        assert isinstance(resolved_manifest, dict)
        assert "streams" in resolved_manifest

        stream_result = execute_stream_read(
            rick_and_morty_manifest, empty_config, "characters", max_records=3
        )
        assert isinstance(stream_result, StreamTestResult)
        assert stream_result.message is not None

    def test_error_handling_scenarios(self, rick_and_morty_manifest, empty_config):
        """Test various error handling scenarios."""
        result = execute_stream_read(
            rick_and_morty_manifest, empty_config, "nonexistent_stream", max_records=1
        )
        assert isinstance(result, StreamTestResult)

    def test_manifest_with_authentication_config(self):
        """Test manifest validation with authentication configuration."""
        auth_manifest = self._create_auth_manifest()
        config_with_auth = {"api_token": "test_token_123"}

        result = validate_manifest(auth_manifest, config_with_auth)
        assert hasattr(result, "is_valid")
        assert hasattr(result, "errors")
        assert isinstance(result.errors, list)

    def _create_auth_manifest(self):
        """Helper to create a manifest with authentication configuration."""
        return {
            "version": "4.6.2",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream", "stream_names": ["test"]},
            "streams": [
                {
                    "type": "DeclarativeStream",
                    "name": "test",
                    "primary_key": ["id"],
                    "retriever": {
                        "type": "SimpleRetriever",
                        "requester": {
                            "type": "HttpRequester",
                            "url_base": "https://api.example.com",
                            "path": "/test",
                            "http_method": "GET",
                            "authenticator": {
                                "type": "BearerAuthenticator",
                                "api_token": "{{ config['api_token'] }}",
                            },
                        },
                        "record_selector": {
                            "type": "RecordSelector",
                            "extractor": {"type": "DpathExtractor", "field_path": []},
                        },
                    },
                    "schema_loader": {
                        "type": "InlineSchemaLoader",
                        "schema": {
                            "$schema": "http://json-schema.org/draft-07/schema#",
                            "type": "object",
                            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                        },
                    },
                }
            ],
            "spec": {
                "type": "Spec",
                "connection_specification": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "Test API Source Spec",
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {"api_token": {"type": "string", "airbyte_secret": True}},
                    "required": ["api_token"],
                },
            },
        }

    @pytest.mark.requires_creds
    def test_performance_multiple_tool_calls(self, rick_and_morty_manifest, empty_config):
        """Test performance with multiple rapid tool calls."""
        start_time = time.time()

        for _ in range(5):
            validate_manifest(rick_and_morty_manifest, empty_config)
            get_resolved_manifest(rick_and_morty_manifest, empty_config)

        end_time = time.time()
        duration = end_time - start_time

        assert duration < 15.0, f"Multiple tool calls took too long: {duration}s"

    def test_simple_api_manifest_workflow(self, simple_api_manifest, empty_config):
        """Test workflow with simple API manifest."""
        validation_result = validate_manifest(simple_api_manifest, empty_config)
        assert validation_result.is_valid

        resolved_manifest = get_resolved_manifest(simple_api_manifest, empty_config)
        assert isinstance(resolved_manifest, dict)
        assert "streams" in resolved_manifest


class TestMCPServerIntegration:
    """Integration tests for MCP server functionality."""

    def test_concurrent_tool_execution(self, rick_and_morty_manifest, empty_config):
        """Test concurrent execution of multiple tools."""

        def run_validation():
            return validate_manifest(rick_and_morty_manifest, empty_config)

        def run_resolution():
            return get_resolved_manifest(rick_and_morty_manifest, empty_config)

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
