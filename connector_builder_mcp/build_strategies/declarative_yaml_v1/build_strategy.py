"""Declarative YAML v1 build strategy.

This strategy supports Airbyte's declarative connector framework where
connectors are defined entirely in YAML manifests without custom Python code.
"""

from __future__ import annotations

import sys

from fastmcp import FastMCP

from connector_builder_mcp.build_strategies.base.build_strategy import BuildStrategy
from connector_builder_mcp.build_strategies.declarative_yaml_v1 import (
    guidance,
    manifest_checks,
    manifest_tests,
    prompts,
)


class DeclarativeYamlV1Strategy(BuildStrategy):
    """Build strategy for declarative YAML connectors.

    This is a stateless registration utility that orchestrates registration
    of MCP tools for declarative YAML connectors. It does NOT implement tools -
    tools remain bare functions in the mcp modules.
    """

    name = "declarative_yaml_v1"
    version = "1.0"
    is_default = True

    @classmethod
    def is_available(cls) -> bool:
        """Check if airbyte-cdk is available.

        Returns True if airbyte-cdk is in sys.modules.
        Not referenced anywhere yet, but part of class signature.
        """
        return "airbyte_cdk" in sys.modules

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
