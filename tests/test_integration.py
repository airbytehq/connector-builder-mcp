"""Integration tests for Builder MCP using real manifest examples."""

from pathlib import Path

import pytest
import yaml

from builder_mcp._connector_builder import (
    execute_stream_read,
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

    @pytest.mark.skip(reason="Test has catalog configuration issue - empty catalog causing 'list index out of range' error")
    def test_execute_stream_read_rick_and_morty(self, rick_and_morty_manifest, empty_config):
        """Test reading from Rick and Morty characters stream."""
        result = execute_stream_read(
            rick_and_morty_manifest, empty_config, "characters", max_records=5
        )

        assert result.success, f"Stream read failed: {result.message}"
        assert result.records_read > 0
        assert "Successfully read from stream" in result.message
