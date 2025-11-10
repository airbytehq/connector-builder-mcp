# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Guidance and configuration for the Connector Builder MCP.

This module provides constants, error definitions, and topic mappings for the Connector Builder MCP.
Re-exports from the _guidance submodule for backward compatibility.
"""

# Re-export all guidance constants for backward compatibility
from connector_builder_mcp._guidance import (
    ADD_STREAM_TO_CONNECTOR_PROMPT,
    CONNECTOR_BUILD_PROMPT,
    CONNECTOR_BUILDER_CHECKLIST,
    CREATIVE_MODE_NOTE,
    NON_CREATIVE_MODE_NOTE,
    OVERVIEW_PROMPT,
    SCAFFOLD_CREATION_SUCCESS_MESSAGE,
    TOPIC_MAPPING,
)


__all__ = [
    "ADD_STREAM_TO_CONNECTOR_PROMPT",
    "CONNECTOR_BUILDER_CHECKLIST",
    "CONNECTOR_BUILD_PROMPT",
    "CREATIVE_MODE_NOTE",
    "DOTENV_FILE_URI_DESCRIPTION",
    "NON_CREATIVE_MODE_NOTE",
    "OVERVIEW_PROMPT",
    "SCAFFOLD_CREATION_SUCCESS_MESSAGE",
    "TOPIC_MAPPING",
]

DOTENV_FILE_URI_DESCRIPTION = """
Optional paths/URLs to local .env files or Privatebin.net URLs for secret
hydration. Can be a single string, comma-separated string, or list of strings.

Privatebin secrets may be created at privatebin.net, and must:
- Contain text formatted as a dotenv file.
- Use a password sent via the `PRIVATEBIN_PASSWORD` env var.
- Do not include password text in the URL.
"""
