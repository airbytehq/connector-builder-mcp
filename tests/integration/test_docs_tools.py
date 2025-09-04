"""Integration tests for Builder MCP using real manifest examples."""

import pytest
import requests

from connector_builder_mcp._guidance import TOPIC_MAPPING
from connector_builder_mcp.connector_builder import (
    get_connector_builder_docs,
)


def test_get_connector_builder_docs_overview() -> None:
    """Test that overview is returned when no topic is specified."""
    result = get_connector_builder_docs()

    assert "# Connector Builder Documentation" in result
    assert "get_connector_builder_checklist()" in result
    assert "For detailed guidance on specific components and features" in result


@pytest.mark.parametrize("topic", list(TOPIC_MAPPING.keys()))
def test_topic_urls_are_accessible( topic) -> None:
    """Test that all topic URLs in the mapping are accessible."""
    if topic in ["stream-templates-yaml", "dynamic-streams-yaml"]:
        pytest.skip(f"Skipping {topic} - URL points to non-existent branch")

    relative_path, _ = TOPIC_MAPPING[topic]
    raw_github_url = (
        f"https://raw.githubusercontent.com/airbytehq/airbyte/master/{relative_path}"
    )

    response = requests.get(raw_github_url, timeout=30)
    assert response.status_code == 200, (
        f"Topic '{topic}' URL {raw_github_url} returned status {response.status_code}"
    )
    assert len(response.text) > 0, f"Topic '{topic}' returned empty content"


def test_get_connector_builder_docs_specific_topic() -> None:
    """Test that specific topic documentation is returned correctly."""
    result = get_connector_builder_docs("overview")

    assert "# 'overview' Documentation" in result
    assert len(result) > 100


def test_get_connector_builder_docs_invalid_topic() -> None:
    """Test handling of invalid topic requests."""
    result = get_connector_builder_docs("nonexistent-topic")

    assert "Topic 'nonexistent-topic' not found" in result
    assert "Available topics:" in result
