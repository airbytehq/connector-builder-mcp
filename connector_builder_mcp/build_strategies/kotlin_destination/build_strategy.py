"""Kotlin Destination build strategy.

This strategy supports building Airbyte destination connectors using Kotlin.
"""

from __future__ import annotations

import shutil
import subprocess

from fastmcp import FastMCP

from connector_builder_mcp.build_strategies.base.build_strategy import BuildStrategy
from connector_builder_mcp.build_strategies.kotlin_destination import (
    guidance,
    manifest_checks,
    manifest_tests,
    prompts,
)


class KotlinDestinationStrategy(BuildStrategy):
    """Build strategy for Kotlin destination connectors.

    This is a stateless registration utility that orchestrates registration
    of MCP tools for Kotlin-based destination connectors.
    """

    name = "kotlin_destination"
    version = "1.0"
    is_default = False

    @classmethod
    def is_available(cls) -> bool:
        """Check if Java 21 is available.

        Returns True if Java 21 is installed and available.
        """
        java_path = shutil.which("java")
        if not java_path:
            return False

        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version_output = result.stderr + result.stdout
            return "21" in version_output or "openjdk 21" in version_output.lower()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

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
