"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def resources_path() -> Path:
    """Fixture for the resources directory path."""
    return Path(__file__).parent / "resources"
