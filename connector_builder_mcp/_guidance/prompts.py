# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Prompt templates for Connector Builder guidance."""

from pathlib import Path

import yaml

from connector_builder_mcp._guidance.topics import TOPIC_MAPPING


NEWLINE = "\n"

DOTENV_FILE_URI_DESCRIPTION = """
Optional paths/URLs to local .env files or Privatebin.net URLs for secret
hydration. Can be a single string, comma-separated string, or list of strings.

Privatebin secrets may be created at privatebin.net, and must:
- Contain text formatted as a dotenv file.
- Use a password sent via the `PRIVATEBIN_PASSWORD` env var.
- Do not include password text in the URL.
"""

_CHECKLIST_YAML_PATH = Path(__file__).parent / "connector_build_checklist.yml"


def _load_checklist_from_yaml() -> str:
    """Load and format the connector builder checklist from YAML file.

    Returns:
        Formatted markdown checklist string
    """
    with open(_CHECKLIST_YAML_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    lines = ["# Connector Builder Development Checklist", ""]
    lines.append("Use this checklist to guide you through the process of building a declarative")
    lines.append("(yaml) source connector using the Connector Builder MCP Server.")
    lines.append("")
    lines.append('Steps marked with "📝" have outputs which should be shared with your user,')
    lines.append("or in a log file if no user is available.")
    lines.append("")

    if data.get("basic_connector_tasks"):
        lines.append("## Basic Connector Tasks")
        lines.append("")
        for task in data["basic_connector_tasks"]:
            task_name = task.get("name", task["id"])
            lines.append(f"- [ ] **{task_name}**: {task['description']}")
        lines.append("")

    if data.get("stream_tasks"):
        lines.append("## Stream Tasks")
        lines.append("")
        if isinstance(data["stream_tasks"], dict) and data["stream_tasks"]:
            for stream_name, tasks in data["stream_tasks"].items():
                lines.append(f"### Stream: {stream_name}")
                for task in tasks:
                    task_name = task.get("name", task["id"])
                    lines.append(f"- [ ] **{task_name}**: {task['description']}")
                lines.append("")
        else:
            lines.append("*(Stream tasks will be added dynamically as streams are implemented)*")
            lines.append("")

    if data.get("special_requirements"):
        lines.append("## Special Requirements")
        lines.append("")
        if data["special_requirements"]:
            for task in data["special_requirements"]:
                task_name = task.get("name", task["id"])
                lines.append(f"- [ ] **{task_name}**: {task.get('description', '')}")
        else:
            lines.append("*(Special requirements will be added by agents as needed)*")
        lines.append("")

    if data.get("acceptance_tests"):
        lines.append("## Acceptance Tests")
        lines.append("")
        if data["acceptance_tests"]:
            for task in data["acceptance_tests"]:
                task_name = task.get("name", task["id"])
                lines.append(f"- [ ] **{task_name}**: {task.get('description', '')}")
        else:
            lines.append("*(Acceptance test tasks will be added as needed)*")
        lines.append("")

    if data.get("finalization_tasks"):
        lines.append("## Finalization Tasks")
        lines.append("")
        for task in data["finalization_tasks"]:
            task_name = task.get("name", task["id"])
            lines.append(f"- [ ] **{task_name}**: {task['description']}")
        lines.append("")

    return "\n".join(lines)


CONNECTOR_BUILDER_CHECKLIST = _load_checklist_from_yaml()

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
- ❌ DO NOT use manual file editing or alternative approaches
- ❌ DO NOT get creative if tools don't work as expected

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
