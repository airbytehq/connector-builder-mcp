"""Checklist loader that reads strategy-specific YAML files.

The checklist tools remain global, but the YAML content varies per strategy.
For Phase 1, directly imports DeclarativeYamlV1Strategy (keeping it simple).

This module now serves as a thin shim that delegates to the BuildStrategy
classmethod. The actual implementation lives in BuildStrategy.load_checklist_yaml().
"""

from __future__ import annotations

from typing import Any

from connector_builder_mcp.build_strategies.declarative_yaml_v1.build_strategy import (
    DeclarativeYamlV1Strategy,
)


def load_checklist_yaml() -> dict[str, Any]:
    """Load checklist YAML for the current build strategy.

    For Phase 1, hardcoded to use DeclarativeYamlV1Strategy.
    Delegates to the strategy's load_checklist_yaml() classmethod.

    Returns:
        Parsed checklist YAML as dictionary

    Raises:
        FileNotFoundError: If checklist file doesn't exist
        TypeError: If YAML root is not a dict with string keys
    """
    return DeclarativeYamlV1Strategy.load_checklist_yaml()
