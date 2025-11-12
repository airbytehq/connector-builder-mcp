"""Base class for build strategies.

This module defines the abstract BuildStrategy class that serves as a registration
utility for different connector build strategies.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, cast

import yaml
from fastmcp import FastMCP


class BuildStrategy(ABC):
    """Stateless registration utility for connector build strategies.

    This class orchestrates registration of MCP tools for different connector types.
    It does NOT implement tools - tools remain bare functions in mcp modules.

    This is a utility class for registering resources, with ability to branch
    registration behavior without changing the behavior of the caller.

    Variable domains (strategy-specific):
    - Guidance: Documentation and examples
    - Manifest Checks: Validation without running connector
    - Manifest Tests: Testing that runs the connector
    - Prompts: Workflow templates

    Global domains (shared, not in strategy):
    - Server Info: Version and metadata
    - Secrets Config: Secret management
    - Manifest History: Version control
    - Checklist: Task tracking (tools global, YAML files variable)
    - Manifest Edits: Manifest operations (tools global, content variable)
    """

    name: ClassVar[str]
    """Unique identifier for this build strategy."""

    version: ClassVar[str]
    """Version of this build strategy."""

    is_default: ClassVar[bool] = False
    """Whether this is the default strategy when none is specified."""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this strategy's dependencies are available.

        Checks if required dependencies are in sys.modules.
        Not referenced anywhere yet, but part of class signature.

        Returns:
            True if dependencies are available, False otherwise.
        """
        ...

    @classmethod
    @abstractmethod
    def register_guidance_tools(cls, app: FastMCP) -> None:
        """Register guidance domain tools by calling registration functions.

        This method should import the relevant mcp module at the top of the
        strategy file and call its registration function here.

        Args:
            app: FastMCP application instance
        """
        ...

    @classmethod
    @abstractmethod
    def register_manifest_check_tools(cls, app: FastMCP) -> None:
        """Register manifest check domain tools by calling registration functions.

        Args:
            app: FastMCP application instance
        """
        ...

    @classmethod
    @abstractmethod
    def register_manifest_test_tools(cls, app: FastMCP) -> None:
        """Register manifest test domain tools by calling registration functions.

        Args:
            app: FastMCP application instance
        """
        ...

    @classmethod
    @abstractmethod
    def register_prompts(cls, app: FastMCP) -> None:
        """Register prompt templates by calling registration functions.

        Args:
            app: FastMCP application instance
        """
        ...

    @classmethod
    def register_all_mcp_callables(cls, app: FastMCP) -> None:
        """Register all MCP callables (tools, prompts, resources) for this strategy.

        This is a convenience method that calls all the abstract registration
        methods in a fixed order. Strategies can override this if they need
        custom registration logic.

        Args:
            app: FastMCP application instance
        """
        cls.register_guidance_tools(app)
        cls.register_manifest_check_tools(app)
        cls.register_manifest_test_tools(app)
        cls.register_prompts(app)

    @classmethod
    def get_checklist_path(cls) -> str:
        """Get the path to this strategy's checklist YAML file.

        Override to provide strategy-specific checklist location.
        Default implementation returns "checklist.yaml" in the strategy directory.

        Returns:
            Filename of the checklist YAML file (default: "checklist.yaml")
        """
        return "checklist.yaml"

    @classmethod
    def load_checklist_yaml(cls) -> dict[str, Any]:
        """Load checklist YAML for this build strategy.

        Calls cls.get_checklist_path() to get the strategy-specific filename,
        then loads and validates the YAML file from the strategy's directory.

        Returns:
            Parsed checklist YAML as dictionary

        Raises:
            FileNotFoundError: If checklist file doesn't exist
            TypeError: If YAML root is not a dict with string keys
            RuntimeError: If strategy module is not loaded
        """
        checklist_filename = cls.get_checklist_path()

        module = sys.modules.get(cls.__module__)
        if module is None:
            raise RuntimeError(f"Strategy module '{cls.__module__}' is not loaded")
        if not hasattr(module, "__file__") or module.__file__ is None:
            raise RuntimeError(f"Strategy module '{cls.__module__}' has no __file__ attribute")

        strategy_dir = Path(module.__file__).parent
        full_path = strategy_dir / checklist_filename

        if not full_path.exists():
            raise FileNotFoundError(
                f"Checklist file not found for strategy '{cls.name}': {full_path}"
            )

        data = yaml.safe_load(full_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError(f"Expected mapping at YAML root, got {type(data).__name__}")
        if not all(isinstance(k, str) for k in data.keys()):
            raise TypeError("Checklist YAML must have string keys at the root")
        return cast(dict[str, Any], data)

    @classmethod
    def get_scaffold_template(cls, auth_type: str) -> str:
        """Get scaffold template content for this strategy.

        Override to provide strategy-specific scaffold templates.
        Default implementation returns empty string (no scaffold support).

        Args:
            auth_type: Authentication type (e.g., "NoAuth", "ApiKeyAuthenticator")

        Returns:
            Scaffold template content as string, or empty string if not supported
        """
        return ""
