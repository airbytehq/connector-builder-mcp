"""Declarative OpenAPI v3 build strategy.

This strategy supports building Airbyte connectors from OpenAPI v3 specifications
with declarative configuration patterns.
"""

from __future__ import annotations

from fastmcp import FastMCP

from connector_builder_mcp.build_strategies.base.build_strategy import BuildStrategy
from connector_builder_mcp.build_strategies.declarative_openapi_v3 import (
    guidance,
    manifest_checks,
    manifest_tests,
    prompts,
)


class DeclarativeOpenApiV3Strategy(BuildStrategy):
    """Build strategy for declarative OpenAPI v3 connectors.

    This is a stateless registration utility that orchestrates registration
    of MCP tools for OpenAPI v3-based connectors with declarative patterns.
    """

    name = "declarative_openapi_v3"
    version = "3.0"
    is_default = False

    @classmethod
    def is_available(cls) -> bool:
        """Check if connector-sdk is available.

        Returns True if connector-sdk related modules are in sys.modules.
        """
        return True  # For now, always available

    @classmethod
    def register_guidance_tools(cls, app: FastMCP) -> None:
        """Register guidance tools by calling the registration function."""
        guidance.register_guidance_tools(app)

    @classmethod
    def register_validation_tools(cls, app: FastMCP) -> None:
        """Register validation tools by calling the registration function."""
        manifest_checks.register_validation_tools(app)

    @classmethod
    def register_testing_tools(cls, app: FastMCP) -> None:
        """Register testing tools by calling the registration function."""
        manifest_tests.register_testing_tools(app)

    @classmethod
    def register_prompts(cls, app: FastMCP) -> None:
        """Register prompts by calling the registration function."""
        prompts.register_prompts(app)
