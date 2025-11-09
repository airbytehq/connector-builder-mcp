"""SECRETS_CONFIG domain tools - Tools to view, edit, inspect, or set secrets.

This module contains tools for managing secrets and configuration.
"""

import logging

# Import all the tool functions from secrets.py
# These will be decorated with @mcp_tool when moved here
from connector_builder_mcp.secrets import (
    list_dotenv_secrets,
    populate_dotenv_missing_secrets_stubs,
    register_secrets_tools,
)


logger = logging.getLogger(__name__)


__all__ = [
    "list_dotenv_secrets",
    "populate_dotenv_missing_secrets_stubs",
    "register_secrets_tools",
]
