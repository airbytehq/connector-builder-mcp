# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Deferred MCP capability registration for prompts and resources.

This module provides decorators and registries for deferred registration of
MCP prompts and resources, following the same pattern used for tools.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastmcp import FastMCP


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


@dataclass
class ToolDef:
    """Definition of a deferred MCP tool."""

    func: Callable[..., Any]


PROMPT_REGISTRY: dict[str, PromptDef] = {}
RESOURCE_REGISTRY: dict[str, ResourceDef] = {}
TOOL_REGISTRY: list[ToolDef] = []


def mcp_prompt(name: str, description: str):
    """Decorator for deferred MCP prompt registration.

    Args:
        name: Unique name for the prompt
        description: Human-readable description of the prompt

    Returns:
        Decorator function that registers the prompt

    Raises:
        ValueError: If a prompt with the same name is already registered
    """

    def decorator(func: Callable[..., list[dict[str, str]]]):
        if name in PROMPT_REGISTRY:
            raise ValueError(f"Duplicate prompt name: {name}")
        PROMPT_REGISTRY[name] = PromptDef(name, description, func)
        return func

    return decorator


def mcp_resource(uri: str, description: str, mime_type: str):
    """Decorator for deferred MCP resource registration.

    Args:
        uri: Unique URI for the resource
        description: Human-readable description of the resource
        mime_type: MIME type of the resource content

    Returns:
        Decorator function that registers the resource

    Raises:
        ValueError: If a resource with the same URI is already registered
    """

    def decorator(func: Callable[..., Any]):
        if uri in RESOURCE_REGISTRY:
            raise ValueError(f"Duplicate resource URI: {uri}")
        RESOURCE_REGISTRY[uri] = ResourceDef(uri, description, mime_type, func)
        return func

    return decorator


def mcp_tool():
    """Decorator for deferred MCP tool registration.

    Returns:
        Decorator function that registers the tool
    """

    def decorator(func: Callable[..., Any]):
        TOOL_REGISTRY.append(ToolDef(func=func))
        return func

    return decorator


def register_deferred_prompts(app: FastMCP) -> None:
    """Register all deferred prompts with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    for defn in PROMPT_REGISTRY.values():
        app.prompt(name=defn.name, description=defn.description)(defn.func)


def register_deferred_resources(app: FastMCP) -> None:
    """Register all deferred resources with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    for defn in RESOURCE_REGISTRY.values():
        app.resource(defn.uri, description=defn.description, mime_type=defn.mime_type)(defn.func)


def register_deferred_tools(app: FastMCP) -> None:
    """Register all deferred tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    for defn in TOOL_REGISTRY:
        app.tool(defn.func)
