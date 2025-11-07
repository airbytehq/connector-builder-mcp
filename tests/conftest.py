"""Shared test fixtures."""

from pathlib import Path
from uuid import uuid4

import pytest


class FakeContext:
    """Fake FastMCP Context for testing."""

    def __init__(self, session_id: str):
        self.session_id = session_id


@pytest.fixture
def ctx() -> FakeContext:
    """Fixture for a fake FastMCP context with unique session ID."""
    return FakeContext(session_id=str(uuid4()))


@pytest.fixture
def resources_path() -> Path:
    """Fixture for the resources directory path."""
    return Path(__file__).parent / "resources"
