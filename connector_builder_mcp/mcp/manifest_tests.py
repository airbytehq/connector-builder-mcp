"""MANIFEST_TESTS domain tools - Testing that runs the connector.

This module contains tools for testing connectors by actually running them.
"""

import logging

# Import all the tool functions from validation_testing.py
# These will be decorated with @mcp_tool when moved here
from connector_builder_mcp.validation_testing import (
    execute_dynamic_manifest_resolution_test,
    execute_stream_test_read,
    run_connector_readiness_test_report,
)


logger = logging.getLogger(__name__)


__all__ = [
    "execute_stream_test_read",
    "run_connector_readiness_test_report",
    "execute_dynamic_manifest_resolution_test",
]
