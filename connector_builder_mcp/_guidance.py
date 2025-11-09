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
    "parameters": (
        "docs/platform/connector-development/config-based/advanced-topics/parameters.md",
        "Parameter propagation and inheritance in declarative manifests",
    ),
}
"""Curated topics mapping with relative paths and descriptions."""

NEWLINE = "\n"

CONNECTOR_BUILDER_CHECKLIST = """# Connector Builder Development Checklist

Use this checklist to guide you through the process of building a declarative
(yaml) source connector using the Connector Builder MCP Server.

Steps marked with "📝" have outputs which should be shared with your user,
or in a log file if no user is available.


These steps ensure you understand roughly the work to do before diving in.

- [ ] 📝 Locate API reference docs using online search.
- [ ] 📝 Identify required authentication methods. If multiple auth methods
      are available, decide which to build first.
- [ ] If the user or the API itself appear to require advanced features,
      check the docs tool to understand how those features might be
      implemented before you start.


These prereq steps should be performed before you start work - so you can
leave the user alone while you work, and so that you won't be blocked waiting
for more info after you start.

- [ ] 📝 **Enumerate all available streams first**: Before beginning work on
      any stream, research the API documentation to identify and list ALL
      available streams/endpoints. Share this complete list with your user
      (or the message thread) so they can provide guidance on priorities or
      exclusions.
- [ ] If you do need secrets for authentication, and if user is able to
      create a .env file for you, ask them to provide you a path to the file.
- [ ] Use your tools to populate required variables to your dotenv file,
      then let the user enter them, then use your tools to verify they are
      set. (You will pass the dotenv file to other tools.)
- [ ] **Important**: Secrets should not be sent directly to or through the LLM.
- [ ] 📝 After enumerating streams, ask the user to confirm the list before
      you start. They can: (1) optionally suggest what the 'first stream'
      should be, or (2) inform you about specific streams they'd like you to
      ignore.


Follow steps for one stream at a time. Lessons learned from one stream are
generally applicable to subsequent streams. Moving in small steps reduces
wasted efforts and prevents hard-to-diagnose issues.

- [ ] Validate that authentication works for the stream, without pagination,
      and that you can see records.
- [ ] Add pagination next. (See steps below.)
- [ ] If other advanced topics are needed, such as custom error handling,
      address these issues for each stream as needed.


- [ ] Add pagination logic after working stream is established.
- [ ] Confirm you can read a few pages.
- [ ] Confirm you can reach the end of the stream and that stream counts are
      not suspect.
      - Use a suitably high record limit to get a total record count, while
        keeping context window manageable by opting not to returning records
        data or raw responses.
      - Counts are suspect if they are an even multiple of 10 or 25, or if
        they are an even multiple of the page size.
      - If counts are suspect, you can sometimes get helpful info from raw
        responses data, inspecting the headers and returned content body
        for clues.
- [ ] 📝 Record the total records count for each stream, as you go. This is
      information the user will want to audit when the connector is complete.

**Important**: When streaming to end of stream to get record counts, disable
records and raw responses to avoid overloading the LLM context window.


- [ ] Only add additional streams after first stream is fully validated.
- [ ] Test each new stream individually before proceeding, repeat until all
      streams are complete.
- [ ] 📝 Double-check the list of completed streams with the list of planned
      streams (if available) or against your API docs. If you've omitted any
      streams, consider if they should be added. Otherwise document what was
      excluded as well as what was included.
- [ ] 📝 If performance will permit, run a full 'smoke test' operation on all
      streams, validating record counts and sharing the final counts with
      your user.


- [ ] All streams pass individual tests.
- [ ] Smoke test extracts expected total records.
- [ ] No record counts are suspicious multiples.
- [ ] Use validate manifest tool to confirm JSON schema is correct.
- [ ] Documentation is complete.

Rules:
- Custom Python components are not supported (for security reasons).
- All MCP tools support receiving .env file path - please pass it without
  parsing secrets yourself.
- Call connector builder docs tool for specific component topics as needed.
- YAML anchors are not supported, although other means are available, such
  as ref pointers.
- The connector spec should be included in the manifest, not as a separate
  file.
- If manifest validation fails, review the errors and relevant documentation
  and then attempt to resolve the errors.
- For reading manifest content, prefer using the 'session_manifest_yaml_contents'
  MCP resource instead of the get_session_manifest tool for better performance
  and caching. The resource URI format is '{server_name}://session/manifest'
  where server_name matches your MCP configuration.


For detailed guidance on specific components, use the connector builder docs
tool. If called with no inputs, it will provide you an index of all available
topics.
"""
OVERVIEW_PROMPT = f"""# Connector Builder Documentation

**Important**: Before starting development, call the
`get_connector_builder_checklist()` tool first to get the comprehensive
development checklist.

The checklist provides step-by-step guidance for building connectors and
helps avoid common pitfalls like pagination issues and incomplete validation.


For detailed guidance on specific components and features, you can request documentation for any of these topics:

{NEWLINE.join(f"- `{key}` - {desc}" for key, (_, desc) in TOPIC_MAPPING.items())}

"""

BUILD_CONNECTOR_FROM_SCRATCH_PROMPT = """# Build a Connector from Scratch

You are building a declarative (YAML) source connector using the Connector
Builder MCP Server.


1. **Research & Planning**
   - Locate API documentation for {api_name}
   - Identify authentication method (API key, OAuth, etc.)
   - List available API endpoints/streams
   - Check for advanced features (pagination, rate limiting, incremental sync)

2. **Setup Secrets** (if authentication required)
   - Use `populate_dotenv_missing_secrets_stubs` to create .env template
   - Have user populate secrets in .env file
   - Use `list_dotenv_secrets` to verify secrets are set
   - Pass dotenv_file_uris to all tools that need authentication

3. **Build First Stream**
   - Create minimal manifest with authentication and one stream
   - Use `validate_manifest` to check structure
   - Use `execute_stream_test_read` to test authentication and basic data retrieval
   - Verify you can read records successfully

4. **Add Pagination**
   - Add pagination configuration to manifest
   - Test reading multiple pages with `execute_stream_test_read`
   - Read to end of stream with high max_records to verify pagination works
     correctly
   - Check that record counts are not suspicious multiples (10, 25, page size)

5. **Add Remaining Streams**
   - Add one stream at a time
   - Test each stream individually before proceeding
   - Apply lessons learned from first stream

6. **Final Validation**
   - Use `run_connector_readiness_test_report` to test all streams
   - Use `validate_manifest` to confirm schema compliance
   - Review record counts and warnings


- `validate_manifest`: Check manifest structure and schema
- `execute_stream_test_read`: Test individual streams
- `run_connector_readiness_test_report`: Generate comprehensive test report
- `get_connector_builder_docs`: Get detailed documentation on specific topics
- `populate_dotenv_missing_secrets_stubs`: Create .env template
- `list_dotenv_secrets`: Verify secrets are configured
- `get_connector_manifest`: Get example manifests from existing connectors
- `find_connectors_by_class_name`: Find connectors using specific features


- Custom Python components are NOT supported
- Always pass dotenv_file_uris to tools that need secrets
- Never send secrets directly through the LLM
- Test one stream at a time
- Disable records/raw responses when reading large datasets
- YAML anchors are not supported (use $ref pointers instead)


Use `get_connector_builder_docs` without arguments to see available
documentation topics, or with a specific topic for detailed guidance.
"""

ADD_STREAM_TO_CONNECTOR_PROMPT = """# Add a New Stream to Existing Connector

You are adding a new stream to an existing declarative connector manifest.


1. **Review Existing Manifest**
   - Load the current manifest from {manifest_path}
   - Use `validate_manifest` to ensure it's valid
   - Review existing streams to understand patterns and conventions

2. **Identify Stream Requirements**
   - Determine API endpoint for {stream_name}
   - Check if authentication is already configured
   - Identify any special requirements (pagination, partitioning,
     transformations)

3. **Add Stream Definition**
   - Add new stream to manifest following existing patterns
   - Configure retriever with appropriate URL path
   - Set up record selector to extract data
   - Add pagination if needed (copy from existing streams if applicable)

4. **Test New Stream**
   - Use `validate_manifest` to check updated manifest
   - Use `execute_stream_test_read` to test the new stream
   - Verify records are returned correctly
   - Test pagination if applicable

5. **Validate Integration**
   - Ensure new stream doesn't break existing streams
   - Use `run_connector_readiness_test_report` to test all streams together
   - Review any warnings or errors


- `validate_manifest`: Check manifest structure
- `execute_stream_test_read`: Test the new stream
- `run_connector_readiness_test_report`: Test all streams together
- `get_connector_builder_docs`: Get documentation on specific topics
- `get_connector_manifest`: Get examples from similar connectors
- `find_connectors_by_class_name`: Find connectors with similar features


- Copy patterns from existing streams in the manifest
- Use the same authentication configuration
- Follow naming conventions from existing streams
- Test incrementally (basic read, then pagination, then edge cases)


Use `get_connector_builder_docs` with topics like 'pagination',
'record-processing', or 'partitioning' for detailed guidance.
"""


SCAFFOLD_CREATION_SUCCESS_MESSAGE = """✅ Manifest scaffold created successfully!

The manifest has been saved to your session and is ready to use.

**To view the manifest:**
- **Preferred**: Use the MCP resource `session_manifest_yaml_contents`
  (URI: '{MCP_SERVER_NAME}://session/manifest').
- **Fallback**: Use the `get_session_manifest` tool if your client does not
  support MCP resources.

**Next steps:**
1. Review the manifest content
2. Update TODO placeholders with actual values from the API documentation
3. Test the first stream with `execute_stream_test_read`
4. Add pagination if needed

**Note:** The manifest includes inline TODO comments marking fields that need attention.
"""
