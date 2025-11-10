# Copyright (c) 2024 Airbyte, Inc., all rights reserved.
"""Deferred MCP capability registration for tools, prompts, and resources.

This module provides a decorator to tag tool functions with MCP annotations
for deferred registration.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from fastmcp import FastMCP

from connector_builder_mcp._annotations import (
    DESTRUCTIVE_HINT,
    IDEMPOTENT_HINT,
    OPEN_WORLD_HINT,
    READ_ONLY_HINT,
)
from connector_builder_mcp.constants import REQUIRE_SESSION_MANIFEST_IN_TOOL_CALLS


F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class PromptDef:
    """Definition of a deferred MCP prompt."""

    name: str
    description: str
    func: Callable[..., list[dict[str, str]]]


@dataclass
class ResourceDef:
    """Definition of a deferred MCP resource."""

    uri: str
    description: str
    mime_type: str
    func: Callable[..., Any]


class ToolDomain(str, Enum):
    """Tool domain categories for the Connector Builder MCP server.

    These domains correspond to the main functional areas of the server.
    """

    GUIDANCE = "guidance"
    """Checklist and docs tools (get_connector_builder_checklist, find_connectors_by_class_name, etc.)"""

    MANIFEST_CHECKS = "manifest_checks"
    """Testing that doesn't run the connector (validate_manifest)"""

    MANIFEST_TESTS = "manifest_tests"
    """Testing that runs the connector (execute_stream_test_read, run_connector_readiness_test_report, execute_dynamic_manifest_resolution_test)"""

    MANIFEST_EDITS = "manifest_edits"
    """Tools to create, edit, or clear the manifest (set_session_manifest_text, get_session_manifest_text, create_connector_manifest_scaffold)"""

    MANIFEST_HISTORY = "manifest_history"
    """Tools to view or manage manifest revision history (list_manifest_revisions, get_manifest_revision)."""

    SECRETS_CONFIG = "secrets_config"
    """Tools to view, edit, inspect, or set secrets"""

    SERVER_INFO = "server_info"
    """Server information and version resources"""

    PROMPTS = "prompts"
    """Prompt templates for common workflows"""


_REGISTERED_TOOLS: list[tuple[Callable[..., Any], dict[str, Any]]] = []
_REGISTERED_RESOURCES: list[tuple[Callable[..., Any], dict[str, Any]]] = []
_REGISTERED_PROMPTS: list[tuple[Callable[..., Any], dict[str, Any]]] = []
# PROMPT_REGISTRY: dict[str, PromptDef] = {}
# RESOURCE_REGISTRY: dict[str, ResourceDef] = {}


def should_register_tool(annotations: dict[str, Any]) -> bool:
    """Check if a tool should be registered.

    Args:
        annotations: Tool annotations dict

    Returns:
        Always returns True (no filtering applied)
    """
    return True


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
        if extra_help_text:
            func.__doc__ = ((func.__doc__ or "") + "\n\n" + (extra_help_text or "")).rstrip()

        _REGISTERED_TOOLS.append((func, annotations))
        return func

    return decorator


def mcp_prompt(
    name: str,
    description: str,
    domain: ToolDomain | str | None = None,
):
    """Decorator for deferred MCP prompt registration.

    Args:
        name: Unique name for the prompt
        description: Human-readable description of the prompt
        domain: Optional domain for filtering (e.g., ToolDomain.PROMPTS)

    Returns:
        Decorator function that registers the prompt

    Raises:
        ValueError: If a prompt with the same name is already registered
    """

    def decorator(func: Callable[..., list[dict[str, str]]]):
        domain_str = domain.value if isinstance(domain, ToolDomain) else domain
        annotations = {
            "name": name,
            "description": description,
        }
        if domain_str is not None:
            annotations["domain"] = domain_str
        _REGISTERED_PROMPTS.append((func, annotations))
        return func

    return decorator


def mcp_resource(
    uri: str,
    description: str,
    mime_type: str,
    domain: ToolDomain | str | None = None,
):
    """Decorator for deferred MCP resource registration.

    Args:
        uri: Unique URI for the resource
        description: Human-readable description of the resource
        mime_type: MIME type of the resource content
        domain: Optional domain for filtering (e.g., ToolDomain.SERVER_INFO)

    Returns:
        Decorator function that registers the resource

    Raises:
        ValueError: If a resource with the same URI is already registered
    """

    def decorator(func: Callable[..., Any]):
        domain_str = domain.value if isinstance(domain, ToolDomain) else domain
        annotations = {
            "uri": uri,
            "description": description,
            "mime_type": mime_type,
        }
        if domain_str is not None:
            annotations["domain"] = domain_str
        _REGISTERED_RESOURCES.append((func, annotations))
        return func

    return decorator


def _register_mcp_callables(
    *,
    app: FastMCP,
    domain: ToolDomain | str,
    resource_list: list[tuple[Callable, dict]],
    register_fn: Callable,
) -> None:
    """Register resources and tools with the FastMCP app, filtered by domain.

    Args:
        app: The FastMCP app instance
        domain: The domain to register tools for (e.g., ToolDomain.SESSION, "session")
        resource_list: List of (callable, annotations) tuples to register
        register_fn: Function to call for each registration
    """
    domain_str = domain.value if isinstance(domain, ToolDomain) else domain

    filtered_callables = [
        (func, ann) for func, ann in resource_list if ann.get("domain") == domain_str
    ]

    for callable_fn, callable_annotations in filtered_callables:
        register_fn(app, callable_fn, callable_annotations)


def register_mcp_tools(
    app: FastMCP,
    domain: ToolDomain | str,
) -> None:  # noqa: ANN401
    """Register tools with the FastMCP app, filtered by domain.

    Args:
        app: The FastMCP app instance
        domain: The domain to register for (e.g., ToolDomain.SESSION, "session")
    """

    def _register_fn(
        app: FastMCP,
        callable_fn: Callable,
        annotations: dict[str, Any],
    ):
        exclude_args: list[str] | None = None
        if REQUIRE_SESSION_MANIFEST_IN_TOOL_CALLS:
            params = set(inspect.signature(callable_fn).parameters.keys())
            excluded = [name for name in ["manifest"] if name in params]
            exclude_args = excluded if excluded else None

        app.tool(
            callable_fn,
            annotations=annotations,
            exclude_args=exclude_args,
        )

    _register_mcp_callables(
        app=app,
        domain=domain,
        resource_list=_REGISTERED_TOOLS,
        register_fn=_register_fn,
    )


def register_mcp_prompts(
    app: FastMCP,
    domain: ToolDomain | str,
) -> None:  # noqa: ANN401
    """Register prompt callables with the FastMCP app, filtered by domain.

    Args:
        app: The FastMCP app instance
        domain: The domain to register for (e.g., ToolDomain.SESSION, "session")
    """

    def _register_fn(
        app: FastMCP,
        callable_fn: Callable,
        annotations: dict[str, Any],
    ):
        app.prompt(
            name=annotations["name"],
            description=annotations["description"],
        )(callable_fn)

    _register_mcp_callables(
        app=app,
        domain=domain,
        resource_list=_REGISTERED_PROMPTS,
        register_fn=_register_fn,
    )


def register_mcp_resources(
    app: FastMCP,
    domain: ToolDomain | str,
) -> None:  # noqa: ANN401
    """Register resource callables with the FastMCP app, filtered by domain.

    Args:
        app: The FastMCP app instance
        domain: The domain to register for (e.g., ToolDomain.SESSION, "session")
    """

    def _register_fn(
        app: FastMCP,
        callable_fn: Callable,
        annotations: dict[str, Any],
    ):
        _ = annotations
        app.resource(
            annotations["uri"],
            description=annotations["description"],
            mime_type=annotations["mime_type"],
        )(callable_fn)

    _register_mcp_callables(
        app=app,
        domain=domain,
        resource_list=_REGISTERED_RESOURCES,
        register_fn=_register_fn,
    )
