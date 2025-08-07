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
OVERVIEW_PROMPT = f"""# Connector Builder Overview

1. It is generally advisable to only attempt to add one stream at a time.
2. Validate each stream's auth, pagination, and data retrieval before moving to the next.
3. Use the validate manifest tool to confirm JSON schema is correct.
4. Once the stream you are working on is confirmed to be working, you can add additional streams.
5. You have a smoke test tool which can be used to confirm all streams are working at the same time.
6. Call this docs tool again for info on specific topics, as needed.

## Dealing with Users' Connector Credentials

1. Ask for secrets to be populated up front, before you begin development. (You may need to
   first confirm which secrets are required by the source API.)
2. Generally, you will ask your user to create a .env file and then provide you its path.
3. You can use the dotenv tools to generate a form for your user, which the user can populate.
4. All of the tools you will use already support receiving a .env file path, so you can pass it to
   the tools without parsing the secrets yourself.
5. Secrets should not be sent directly to or through the LLM.

## Handling Pagination

1. Generally, it makes sense to add pagination _after_ you have a working stream that retrieves
   data.
2. It will often be helpful to opt-in to raw responses data with a row limit of page_size x 2.
   This should provide you with the raw headers and responses data needed to understand how
   pagination works, for instance: how page 1 should hand off to page 2.
3. Pagination generally should not be considered 'complete' until you can sync to the end of the
   stream and determine a total records count.
4. Record counts are generally suspect if they are an exact multiple of page_size or of 10, as
   either of these may indicate that the pagination logic is not working correctly.
5. When intentionally streaming to the end of a stream, its important to disable the option to
   return records and raw responses. Otherwise, you risk overloading the LLM with too much data.

## Smoke Testing

1. Use the smoke test tool to confirm that your connector is working.
2. Be suspect of record counts that are an exact multiple of 10 or of the page_size, as this may
   indicate that the pagination logic is not working correctly.

## Limitations

- Note that we don't yet support custom Python components (for security reasons).

## Detailed Topics List

For detailed docs on specific components, call this function again with one of these topics:

- {NEWLINE.join(f"- `{key}` - {desc}" for key, (_, desc) in TOPIC_MAPPING.items())}

"""
