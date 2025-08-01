"""Integration tests for Builder MCP using real manifest examples."""

from pathlib import Path

import pytest
import requests
import yaml

from builder_mcp._connector_builder import (
    _get_topic_mapping,
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

    @pytest.mark.skip(
        reason="Test has catalog configuration issue - empty catalog causing 'list index out of range' error"
    )
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
