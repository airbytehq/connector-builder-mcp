"""Kotlin Destination build strategy.

This strategy supports building Airbyte destination connectors using Kotlin.
"""

from __future__ import annotations

from fastmcp import FastMCP

from connector_builder_mcp.build_strategies.base.build_strategy import BuildStrategy
from connector_builder_mcp.build_strategies.kotlin_destination_v1 import (
    guidance,
    manifest_checks,
    manifest_tests,
    prompts,
)


class KotlinDestinationV1Strategy(BuildStrategy):
    """Build strategy for Kotlin destination connectors.

    This is a stateless registration utility that orchestrates registration
    of MCP tools for Kotlin-based destination connectors.
    """

    name = "kotlin_destination_v1"
    version = "1.0"
    is_default = False

    @classmethod
    def is_available(cls) -> bool:
        """Check if Kotlin/JVM dependencies are available.

        Returns True if Kotlin-related modules might be available.
        """
        return True  # For now, always available

    @classmethod
    def register_guidance_tools(cls, app: FastMCP) -> None:
        """Register guidance tools by calling the registration function."""
        guidance.register_guidance_tools(app)

    @classmethod
    def register_manifest_check_tools(cls, app: FastMCP) -> None:
        """Register manifest check tools by calling the registration function."""
        manifest_checks.register_manifest_check_tools(app)

    @classmethod
    def register_manifest_test_tools(cls, app: FastMCP) -> None:
        """Register manifest test tools by calling the registration function."""
        manifest_tests.register_manifest_test_tools(app)

    @classmethod
    def register_prompts(cls, app: FastMCP) -> None:
        """Register prompts by calling the registration function."""
        prompts.register_prompts(app)
