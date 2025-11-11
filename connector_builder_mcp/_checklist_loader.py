"""Checklist loader that reads strategy-specific YAML files.

The checklist tools remain global, but the YAML content varies per strategy.
For Phase 1, directly imports DeclarativeYamlV1Strategy (keeping it simple).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from connector_builder_mcp.build_strategies.declarative_yaml_v1.build_strategy import (
    DeclarativeYamlV1Strategy,
)


def load_checklist_yaml() -> dict[str, Any]:
    """Load checklist YAML for the current build strategy.

    For Phase 1, hardcoded to use DeclarativeYamlV1Strategy.
    Can be made more sophisticated in a later PR.

    Returns:
        Parsed checklist YAML as dictionary

    Raises:
        FileNotFoundError: If checklist file doesn't exist
    """
    strategy = DeclarativeYamlV1Strategy
    checklist_path = strategy.get_checklist_path()

    base_dir = Path(__file__).parent / "_guidance" / "checklists"
    full_path = base_dir / checklist_path

    if not full_path.exists():
        raise FileNotFoundError(
            f"Checklist file not found for strategy '{strategy.name}': {full_path}"
        )

    return yaml.safe_load(full_path.read_text())
