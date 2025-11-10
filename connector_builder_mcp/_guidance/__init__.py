# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Guidance module for Connector Builder MCP.

This module provides prompts, topic mappings, and checklists for connector development.
"""

from connector_builder_mcp._guidance.prompts import (
    ADD_STREAM_TO_CONNECTOR_PROMPT,
    CONNECTOR_BUILD_PROMPT,
    CONNECTOR_BUILDER_CHECKLIST,
    CREATIVE_MODE_NOTE,
    DOTENV_FILE_URI_DESCRIPTION,
    NON_CREATIVE_MODE_NOTE,
    OVERVIEW_PROMPT,
    SCAFFOLD_CREATION_SUCCESS_MESSAGE,
)
from connector_builder_mcp._guidance.topics import TOPIC_MAPPING


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
