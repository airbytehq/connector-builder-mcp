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
  MCP resource instead of the get_session_manifest_text tool for better performance
  and caching. The resource URI format is '<MCP_SERVER_NAME>://session/manifest'
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
  (URI: '<MCP_SERVER_NAME>://session/manifest').
- **Fallback**: Use the `get_session_manifest_text` tool if your client does not
  support MCP resources.

**Next steps:**
1. Review the manifest content
2. Update TODO placeholders with actual values from the API documentation
3. Test the first stream with `execute_stream_test_read`
4. Add pagination if needed

**Note:** The manifest includes inline TODO comments marking fields that need attention.
"""

CONNECTOR_BUILD_PROMPT = """# Build a Test Connector (MCP Server Debug)

Build a working connector to verify the Connector Builder MCP server is functioning correctly.

## API Connector Specifications

**Target API**: {api_name}
**Secrets File** (if applicable): {dotenv_path}
**Additional Requirements** (if applicable): {additional_requirements}

**Note**: You will discover the API base URL and authentication requirements by:
1. Using web search to find the API documentation
2. Using `list_dotenv_secrets(dotenv_path='{dotenv_path}')` to see what secret keys are available (if .env file provided)
3. The tools let you view secret key names without exposing the actual values

## Critical Guidelines

**IMPORTANT - Read Before Starting:**

1. **Track Time**: Note your start time now. At the end, report the total duration of the process.
   - Exception: If you are not able to view the current time, you may skip this step.

2. **Tool Testing Focus**: The goal is to work using the MCP tools, not work around them.
   - ❌ DO NOT get creative or find workarounds if tools fail (unless your use explicitly allows it)
   - ❌ DO NOT manually edit files or use alternative approaches
   - ✅ DO report any tool that malfunctions or behaves unexpectedly
   - ✅ DO stop and report if you cannot proceed with the provided tools

3. **Mandatory First Step**: Always start by calling `get_connector_builder_checklist()`
   - Review the full checklist before beginning work
   - Use it to guide your development process

4. **Completion Criteria**: This task is NOT complete until:
   - ✅ You have added all streams that the API supports (unless the user specified otherwise)
   - ✅ The `run_connector_readiness_test_report` tool executes successfully
   - ✅ The readiness report shows passing results, with no unexpected errors or warnings
   - ✅ You provide the report results AND file path as evidence
   - ✅ You report the total time elapsed from start to finish

5. **Reporting Malfunctions**: Immediately report if any tool:
   - Returns unexpected errors
   - Produces invalid output
   - Fails to perform its documented function
   - Behaves inconsistently

6. **Version Tracking**
- If you make a mistake which you cannot readily fix, use your tools to list, diff
  or recall prior versions of the session's manifest.yaml resource.

## Build Steps

### 0. Review Checklist (MANDATORY FIRST STEP)
- Call `get_connector_builder_checklist()` to get the comprehensive development checklist
- Review the entire checklist before proceeding
- Keep the checklist guidance in mind throughout the process

### 1. Research API & Discover Configuration
- Use web search to find official API documentation
- Discover the base URL from the documentation
- Identify authentication requirements (API key, OAuth, Bearer token, etc.)
- Enumerate all available endpoints/streams
- Share findings with user

### 2. Decide on Authentication Strategy

**If auth not required:**
- Simply note to the user that no authentication is provided and continue

**If .env file provided:**
- Use `list_dotenv_secrets(dotenv_path='{dotenv_path}')` to see what secret keys are available
- This shows you the key names (e.g., "API_KEY", "CLIENT_ID") without exposing values
- Infer the authentication type from the key names
- The tools will automatically use these secrets when needed

**If auth is required but you do not have a .env file:**
- 🛑 STOP! Ask your user to select between options and give them instructions to create a .env file
  before continuing.
- 🛑 Important: DO NOT attempt to build a connector that you don't have credentials to test. This
  would waste your time and your users' time.

- If the API requires secrets which are not yet in the .env file:
  - First use `list_dotenv_secrets` to ensure they don't exist by another name
  - Use `populate_dotenv_missing_secrets_stubs(dotenv_path='{dotenv_path}')` to add missing key stubs
  - Wait for user to populate the new secrets
  - Use `list_dotenv_secrets(dotenv_path='{dotenv_path}')` to verify they were added

### 3. Create Connector Scaffold
- Use `create_connector_manifest_scaffold` with appropriate parameters
- For JSONPlaceholder, use:
  - connector_name: "source-jsonplaceholder"
  - api_base_url: "https://jsonplaceholder.typicode.com"
  - initial_stream_name: "posts"
  - initial_stream_path: "/posts"
  - authentication_type: "NoAuth"

### 4. View and Validate Manifest
- Use `get_session_manifest_text()` to retrieve the scaffold
- Use `validate_manifest()` to check structure
- Review any TODO placeholders that need updating

### 5. Test First Stream
- Use `execute_stream_test_read(stream_name='posts', max_records=5)` to test
- Verify records are returned successfully
- Check data structure looks correct

### 6. Add Pagination
- Edit manifest to add proper pagination configuration
- Use `set_session_manifest_text()` to update manifest
- Test with more records to verify pagination works
- Read to end of stream to get total count

### 7. Add Remaining Streams (One at a time)
- Repeat your previous steps for each stream
- Test each stream individually after adding, and before moving on to the next stream

### 8. Final Validation & Readiness Report (MANDATORY)
- Use `validate_manifest()` to ensure manifest is valid
- **CRITICAL**: Run `run_connector_readiness_test_report()`
  - This tool generates a comprehensive test report
  - It MUST complete successfully for the task to be considered done
  - The report is saved to a file - you MUST provide the file path
- Review the readiness report results thoroughly
- If any streams fail, investigate and fix issues before proceeding

### 10. Final Summary & Evidence (MANDATORY)
**You MUST provide all of the following:**
- ✅ Total time elapsed (from start to finish)
- ✅ Connector readiness report file path
- ✅ Full results from the readiness report
- ✅ List of streams added and their record counts
- ✅ Any tool malfunctions encountered (or note "None")
- ✅ Overall success status

## Reporting Guidelines

Report progress as you go:
- ✅ Steps completed successfully
- ⚠️ Tool malfunctions or unexpected behavior (REPORT IMMEDIATELY)
- ❌ Blocking errors that prevent progress (STOP and REPORT)
- 📊 Ongoing statistics: streams, total records, validation status

**Remember**: The goal is to test the tools, not to be clever. If a tool doesn't work, report it - don't work around it.

## Success Criteria

**ALL of the following must be met:**
- ✅ Checklist reviewed at start
- ✅ Manifest validates successfully
- ✅ All streams working and returning data
- ✅ Pagination tested and verified
- ✅ `run_connector_readiness_test_report()` executed and passes
- ✅ Report file path and results provided
- ✅ Total time duration reported (if tools permit)
- ✅ No tool malfunctions left unreported

## Important Notes

- **Start with checklist tool** - This is mandatory, not optional
- **End with readiness report tool** - Provide file path and results
- **Report time elapsed** - Track from start to finish
- **Report tool issues** - Don't work around them, report them
- **Don't get creative** - Stick to the MCP tools provided
- Keep the scope manageable - 2-4 streams is sufficient for testing

## Key Tools Reference

**Documentation & Guidance:**
- `get_connector_builder_checklist()` - Get comprehensive development checklist
- `get_connector_builder_docs(topic)` - Get detailed docs on specific topics

**Connector Examples:**
- `get_connector_manifest(connector_name)` - Get example manifests from existing connectors
- `find_connectors_by_class_name(class_names)` - Find connectors using specific features

**Manifest Operations:**
- `create_connector_manifest_scaffold()` - Create initial connector scaffold
- `get_session_manifest_text()` - Retrieve current manifest
- `set_session_manifest_text()` - Edit manifest content
- `validate_manifest()` - Validate manifest structure and schema

**Testing & Validation:**
- `execute_stream_test_read()` - Test individual streams and verify data
- `run_connector_readiness_test_report()` - Generate comprehensive test report

**Secret Management:**
- `list_dotenv_secrets(dotenv_path)` - List secret keys without exposing values
- `populate_dotenv_missing_secrets_stubs()` - Create .env template

**Version Control:**
- `list_session_manifest_versions()` - List manifest version history
- `diff_session_manifest_versions()` - Compare versions
"""

NON_CREATIVE_MODE_NOTE = """

---

**Note**: This prompt is configured in **non-creative mode** (default). You should:
- ✅ Stick strictly to the MCP tools provided
- ✅ Report tool failures immediately without attempting workarounds
- ❌ Do NOT use manual file editing or alternative approaches
- ❌ Do NOT get creative if tools don't work as expected

This ensures we properly test the MCP tools and identify any issues.
"""

CREATIVE_MODE_NOTE = """

---

**Note**: This prompt is configured in **creative mode**. You may:
- ✅ Use creative solutions and workarounds if MCP tools fail
- ✅ Manually edit files if needed to unblock progress
- ✅ Find alternative approaches to achieve the goal
- ⚠️ Still report any tool malfunctions, but proceed with workarounds

**Warning**: Creative mode is less reliable and may lead to mistakes. Use only for complex scenarios.
"""
