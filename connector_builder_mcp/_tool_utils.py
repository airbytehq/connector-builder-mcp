# Copyright (c) 2024 Airbyte, Inc., all rights reserved.
"""MCP tool utility functions.

This module provides a decorator to tag tool functions with MCP annotations
for deferred registration.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

from connector_builder_mcp._annotations import (
    DESTRUCTIVE_HINT,
    IDEMPOTENT_HINT,
    OPEN_WORLD_HINT,
    READ_ONLY_HINT,
)


F = TypeVar("F", bound=Callable[..., Any])


class ToolDomain(str, Enum):
    """Tool domain categories for the Connector Builder MCP server.

    These domains correspond to the main functional areas of the server.
    """

    GUIDANCE = "guidance"
    """Checklist and docs tools (find_connectors_by_class_name, get_manifest_yaml_json_schema)"""

    MANIFEST_CHECKS = "manifest_checks"
    """Testing that doesn't run the connector (validate_manifest)"""

    MANIFEST_TESTS = "manifest_tests"
    """Testing that runs the connector (execute_stream_test_read, run_connector_readiness_test_report, execute_dynamic_manifest_resolution_test)"""

    MANIFEST_EDITS = "manifest_edits"
    """Tools to create, edit, or clear the manifest (set_session_manifest_text, get_session_manifest, create_connector_manifest_scaffold)"""

    SECRETS_CONFIG = "secrets_config"
    """Tools to view, edit, inspect, or set secrets"""


_REGISTERED_TOOLS: list[tuple[Callable[..., Any], dict[str, Any]]] = []


def should_register_tool(annotations: dict[str, Any]) -> bool:
    """Check if a tool should be registered.

    Args:
        annotations: Tool annotations dict

    Returns:
        Always returns True (no filtering applied)
    """
    return True


def get_registered_tools(
    domain: ToolDomain | str | None = None,
) -> list[tuple[Callable[..., Any], dict[str, Any]]]:
    """Get all registered tools, optionally filtered by domain.

    Args:
        domain: The domain to filter by (e.g., ToolDomain.GUIDANCE, "guidance").
            If None, returns all tools.

    Returns:
        List of tuples containing (function, annotations) for each registered tool
    """
    if domain is None:
        return _REGISTERED_TOOLS.copy()
    domain_str = domain.value if isinstance(domain, ToolDomain) else domain
    return [(func, ann) for func, ann in _REGISTERED_TOOLS if ann.get("domain") == domain_str]


def mcp_tool(
    domain: ToolDomain | str,
    *,
    read_only: bool = False,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = False,
    extra_help_text: str | None = None,
) -> Callable[[F], F]:
    """Decorator to tag an MCP tool function with annotations for deferred registration.

    This decorator stores the annotations on the function for later use during
    deferred registration. It does not register the tool immediately.

    Args:
        domain: The domain this tool belongs to (e.g., ToolDomain.SESSION, "session")
        read_only: If True, tool only reads without making changes (default: False)
        destructive: If True, tool modifies/deletes existing data (default: False)
        idempotent: If True, repeated calls have same effect (default: False)
        open_world: If True, tool interacts with external systems (default: False)
        extra_help_text: Optional text to append to the function's docstring
            with a newline delimiter

    Returns:
        Decorator function that tags the tool with annotations

    Example:
        @mcp_tool(ToolDomain.SESSION, read_only=True, idempotent=True)
        def list_sources():
            ...
    """
    domain_str = domain.value if isinstance(domain, ToolDomain) else domain
    annotations: dict[str, Any] = {
        "domain": domain_str,
        READ_ONLY_HINT: read_only,
        DESTRUCTIVE_HINT: destructive,
        IDEMPOTENT_HINT: idempotent,
        OPEN_WORLD_HINT: open_world,
    }

    def decorator(func: F) -> F:
        func._mcp_annotations = annotations  # type: ignore[attr-defined]  # noqa: SLF001
        func._mcp_domain = domain_str  # type: ignore[attr-defined]  # noqa: SLF001
        func._mcp_extra_help_text = extra_help_text  # type: ignore[attr-defined]  # noqa: SLF001
        _REGISTERED_TOOLS.append((func, annotations))
        return func

    return decorator


def register_tools(app: Any, domain: ToolDomain | str) -> None:  # noqa: ANN401
    """Register tools with the FastMCP app, filtered by domain.

    Args:
        app: The FastMCP app instance
        domain: The domain to register tools for (e.g., ToolDomain.SESSION, "session")
    """
    for func, tool_annotations in get_registered_tools(domain):
        if should_register_tool(tool_annotations):
            extra_help_text = getattr(func, "_mcp_extra_help_text", None)
            if extra_help_text:
                description = (func.__doc__ or "").rstrip() + "\n" + extra_help_text
                app.tool(func, annotations=tool_annotations, description=description)
            else:
                app.tool(func, annotations=tool_annotations)
