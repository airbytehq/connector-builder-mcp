# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Guidance and configuration for the Connector Builder MCP.

This module provides constants, error definitions, and topic mappings for the Connector Builder MCP.
"""

DOTENV_FILE_URI_DESCRIPTION = """
Optional paths/URLs to local .env files or Privatebin.net URLs for secret
hydration. Can be a single string, comma-separated string, or list of strings.

Privatebin secrets may be created at privatebin.net, and must:
- Contain text formatted as a dotenv file.
- Use a password sent via the `PRIVATEBIN_PASSWORD` env var.
- Do not include password text in the URL.
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

CONNECTOR_BUILDER_CHECKLIST = """# Connector Builder Development Checklist

Use this checklist to guide you through the process of building a declarative (yaml) source connector using the Connector Builder MCP Server.

Steps marked with "📝" have outputs which should be shared with your user, or in a log file if no user is available.


These steps ensure you understand roughly the work to do before diving in.

- [ ] 📝 Locate API reference docs using online search.
- [ ] 📝 Identify required authentication methods. If multiple auth methods are available, decide which to build first.
- [ ] If the user or the API itself appear to require advanced features, check the docs tool to understand how those features might be implemented before you start.


These prereq steps should be performed before you start work - so you can leave the user alone while you work, and so that you won't be blocked waiting for more info after you start.

- [ ] 📝 **Enumerate all available streams first**: Before beginning work on any stream, research the API documentation to identify and list ALL available streams/endpoints. Share this complete list with your user (or the message thread) so they can provide guidance on priorities or exclusions.
- [ ] If you do need secrets for authentication, and if user is able to create a .env file for you, ask them to provide you a path to the file.
- [ ] Use your tools to populate required variables to your dotenv file, then let the user enter them, then use your tools to verify they are set. (You will pass the dotenv file to other tools.)
- [ ] **Important**: Secrets should not be sent directly to or through the LLM.
- [ ] 📝 After enumerating streams, ask the user to confirm the list before you start. They can: (1) optionally suggest what the 'first stream' should be, or (2) inform you about specific streams they'd like you to ignore.


Follow steps for one stream at a time. Lessons learned from one stream are generally applicable to subsequent streams. Moving in small steps reduces wasted efforts and prevents hard-to-diagnose issues.

- [ ] Validate that authentication works for the stream, without pagination, and that you can see records.
- [ ] Add pagination next. (See steps below.)
- [ ] If other advanced topics are needed, such as custom error handling, address these issues for each stream as needed.


- [ ] Add pagination logic after working stream is established.
- [ ] Confirm you can read a few pages.
- [ ] Confirm you can reach the end of the stream and that stream counts are not suspect.
      - Use a suitably high record limit to get a total record count, while keeping context window manageable by opting not to returning records data or raw responses.
      - Counts are suspect if they are an even multiple of 10 or 25, or if they are an even multiple of the page size.
      - If counts are suspect, you can sometimes get helpful info from raw responses data, inspecting the headers and returned content body for clues.
- [ ] 📝 Record the total records count for each stream, as you go. This is information the user will want to audit when the connector is complete.

**Important**: When streaming to end of stream to get record counts, disable records and raw responses to avoid overloading the LLM context window.


- [ ] Only add additional streams after first stream is fully validated.
- [ ] Test each new stream individually before proceeding, repeat until all streams are complete.
- [ ] 📝 Double-check the list of completed streams with the list of planned streams (if available) or against your API docs. If you've omitted any streams, consider if they should be added. Otherwise document what was excluded as well as what was included.
- [ ] 📝 If performance will permit, run a full 'smoke test' operation on all streams, validating record counts and sharing the final counts with your user.


- [ ] All streams pass individual tests.
- [ ] Smoke test extracts expected total records.
- [ ] No record counts are suspicious multiples.
- [ ] Use validate manifest tool to confirm JSON schema is correct.
- [ ] Documentation is complete.

Rules:
- Custom Python components are not supported (for security reasons).
- All MCP tools support receiving .env file path - please pass it without parsing secrets yourself.
- Call connector builder docs tool for specific component topics as needed.
- YAML anchors are not supported, although other means are available, such as ref pointers.
- The connector spec should be included in the manifest, not as a separate file.
- If manifest validation fails, review the errors and relevant documentation and then attempt to resolve the errors.


For detailed guidance on specific components, use the connector builder docs tool. If called with no inputs, it will provide you an index of all available topics.
"""
OVERVIEW_PROMPT = f"""# Connector Builder Documentation

**Important**: Before starting development, call the `get_connector_builder_checklist()` tool first to get the comprehensive development checklist.

The checklist provides step-by-step guidance for building connectors and helps avoid common pitfalls like pagination issues and incomplete validation.


For detailed guidance on specific components and features, you can request documentation for any of these topics:

{NEWLINE.join(f"- `{key}` - {desc}" for key, (_, desc) in TOPIC_MAPPING.items())}

"""
