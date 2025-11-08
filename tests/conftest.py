"""Shared test fixtures."""

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest


@dataclass
class FakeContext:
    """Fake FastMCP Context for testing."""

    session_id: str


@pytest.fixture
def ctx() -> FakeContext:
    """Fixture for a fake FastMCP context with unique session ID."""
    return FakeContext(session_id=str(uuid4()))


@pytest.fixture
def resources_path() -> Path:
    """Fixture for the resources directory path."""
    return Path(__file__).parent / "resources"
