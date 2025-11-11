"""Base class for build strategies.

This module defines the abstract BuildStrategy class that serves as a registration
utility for different connector build strategies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

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
    def register_all_variable_domains(cls, app: FastMCP) -> None:
        """Register all variable domain tools for this strategy.

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
        Default implementation returns path based on strategy name.

        Returns:
            Path to checklist YAML file relative to _guidance/checklists/
        """
        return f"{cls.name}/base.yaml"

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
