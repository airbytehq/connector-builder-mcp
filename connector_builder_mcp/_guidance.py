# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Guidance and configuration for the Connector Builder MCP.

This module provides constants, error definitions, and topic mappings for the Connector Builder MCP.
"""

TOPIC_MAPPING: dict[str, tuple[str, str]] = {
    "overview": (
        "docs/platform/connector-development/connector-builder-ui/overview.md",
        "Connector Builder overview and introduction",
    ),
    "tutorial": (
        "docs/platform/connector-development/connector-builder-ui/tutorial.mdx",
        "Step-by-step tutorial for building connectors",
    ),
    "authentication": (
        "docs/platform/connector-development/connector-builder-ui/authentication.md",
        "Authentication configuration",
    ),
    "incremental-sync": (
        "docs/platform/connector-development/connector-builder-ui/incremental-sync.md",
        "Setting up incremental data synchronization",
    ),
    "pagination": (
        "docs/platform/connector-development/connector-builder-ui/pagination.md",
        "Handling paginated API responses",
    ),
    "partitioning": (
        "docs/platform/connector-development/connector-builder-ui/partitioning.md",
        "Configuring partition routing for complex APIs",
    ),
    "record-processing": (
        "docs/platform/connector-development/connector-builder-ui/record-processing.mdx",
        "Processing and transforming records",
    ),
    "error-handling": (
        "docs/platform/connector-development/connector-builder-ui/error-handling.md",
        "Handling API errors and retries",
    ),
    "ai-assist": (
        "docs/platform/connector-development/connector-builder-ui/ai-assist.md",
        "Using AI assistance in the Connector Builder",
    ),
    "stream-templates": (
        "docs/platform/connector-development/connector-builder-ui/stream-templates.md",
        "Using stream templates for faster development",
    ),
    "custom-components": (
        "docs/platform/connector-development/connector-builder-ui/custom-components.md",
        "Working with custom components",
    ),
    "async-streams": (
        "docs/platform/connector-development/connector-builder-ui/async-streams.md",
        "Configuring asynchronous streams",
    ),
    "yaml-overview": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/yaml-overview.md",
        "Understanding the YAML file structure",
    ),
    "reference": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/reference.md",
        "Complete YAML reference documentation",
    ),
    "yaml-incremental-syncs": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/incremental-syncs.md",
        "Incremental sync configuration in YAML",
    ),
    "yaml-pagination": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/pagination.md",
        "Pagination configuration options",
    ),
    "yaml-partition-router": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/partition-router.md",
        "Partition routing in YAML manifests",
    ),
    "yaml-record-selector": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/record-selector.md",
        "Record selection and transformation",
    ),
    "yaml-error-handling": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/error-handling.md",
        "Error handling configuration",
    ),
    "yaml-authentication": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/authentication.md",
        "Authentication methods in YAML",
    ),
    "requester": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/requester.md",
        "HTTP requester configuration",
    ),
    "request-options": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/request-options.md",
        "Request parameter configuration",
    ),
    "rate-limit-api-budget": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/rate-limit-api-budget.md",
        "Rate limiting and API budget management",
    ),
    "file-syncing": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/file-syncing.md",
        "File synchronization configuration",
    ),
    "property-chunking": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/property-chunking.md",
        "Property chunking for large datasets",
    ),
    "stream-templates-yaml": (
        "https://raw.githubusercontent.com/airbytehq/airbyte/refs/heads/devin/1754521580-stream-templates-docs/docs/platform/connector-development/config-based/understanding-the-yaml-file/stream-templates.md",
        "Using stream templates in YAML manifests",
    ),
    "dynamic-streams-yaml": (
        "https://raw.githubusercontent.com/airbytehq/airbyte/refs/heads/devin/1754521580-stream-templates-docs/docs/platform/connector-development/config-based/understanding-the-yaml-file/dynamic-streams.md",
        "Dynamic stream configuration in YAML manifests",
    ),
}
"""Curated topics mapping with relative paths and descriptions."""

NEWLINE = "\n"
OVERVIEW_PROMPT = f"""# Connector Builder Documentation

**Important**: Before starting development, call the `get_connector_builder_checklist()` tool first to get the comprehensive development checklist.

The checklist provides step-by-step guidance for building connectors and helps avoid common pitfalls like pagination issues and incomplete validation.


For detailed guidance on specific components and features, you can request documentation for any of these topics:

{NEWLINE.join(f"- `{key}` - {desc}" for key, (_, desc) in TOPIC_MAPPING.items())}

"""
