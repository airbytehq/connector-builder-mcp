# Contributing to Builder MCP

Thank you for your interest in contributing to the Builder MCP project! This guide will help you get started with development and testing.

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python package management and follows modern Python development practices.

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for package management (`brew install uv`)

### Installing Dependencies

```bash
uv sync --all-extras
# Or:
poe sync
# Verify installation:
uv run connector-builder-mcp --help
```

_(Note: Unlike Poetry, uv will generally auto-run a sync whenever you use `uv run`. Running `uv sync` explicitly
may not be strictly necessary.)_

### Installing Poe

For convenience, install [Poe the Poet](https://poethepoet.natn.io/) task runner:

```bash
# Install Poe
uv tool install poethepoet

# View all available commands
poe --help
```

## Helpful Poe Shortcuts

Note: The below is _not_ a full list of poe commands. For a full list, run `poe --help`.

```bash
# MCP server operations
poe mcp-serve-local # Serve with STDIO transport
poe mcp-serve-http  # Serve over HTTP
poe mcp-serve-sse   # Serve over SSE
poe inspect         # Inspect the MCP server. Use --help for options.
poe inspect --tools # Inspect the tools.
poe test-tool       # Spin up server, pass a tool call, then spin down the server.
poe agent-run       # Run a connector build using the Pytest test script.
```

You can see what any Poe task does by checking the `poe_tasks.toml` file at the root of the repo.

## Testing with MCP Clients

To test the MCP server with various clients, you can configure the clients to point to your local or development server.

### Development Version (Main Branch)

This version pulls the latest code from the main branch of the repository:

```json
{
  "mcpServers": {
    "connector-builder-mcp--dev-main": {
      "command": "uvx",
      "args": [
        "--from=git+https://github.com/airbytehq/connector-builder-mcp.git@main",
        "airbyte-connector-builder-mcp"
      ]
    }
  }
}
```

### Local Development

This version runs the MCP server from your local clone of the repository. Make sure to replace `/path/to/repos/connector-builder-mcp` with the actual path to your local repository.

```json
{
  "mcpServers": {
    "connector-builder-mcp--local-dev": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/repos/connector-builder-mcp",
        "airbyte-connector-builder-mcp"
      ]
    }
  }
}
```

## Testing with GitHub Models

```bash
brew install gh
gh auth login
gh extension install https://github.com/github/gh-models
gh models --help
```

## Running Pytest Tests

```bash
# Make sure dependencies are up-to-date
poe sync

# Run all tests
poe test

# Run only integration tests
uv run pytest tests/test_integration.py -v

# Run tests requiring credentials (skipped by default)
uv run pytest tests/ -v -m requires_creds

# Run fast tests only (skip slow integration tests)
uv run pytest tests/ -v -m "not requires_creds"
```

## MCP Server Inspection

Inspect the MCP server to see available tools, resources, and prompts:

```bash
# Inspect the server structure (generates comprehensive JSON report)
poe inspect
# Equivalent to: uv run fastmcp inspect connector_builder_mcp/server.py:app

# Save inspection report to custom file
poe inspect --output my-server-report.json
# Equivalent to: uv run fastmcp inspect connector_builder_mcp/server.py:app --output my-server-report.json

# View help for inspection options
poe inspect --help
# Shows available options for the inspect command
```

The inspection generates a comprehensive JSON report containing: **Tools**, **Prompts**, **Resources**, **Templates**, and **Capabilities**.

### Inspecting Specific Tools

After running `poe inspect`, you can examine the generated `server-info.json` file to see detailed information about each tool:

```bash
# View the complete inspection report
cat server-info.json

# Extract just the tools information using jq
cat server-info.json | jq '.tools'

# Get details for a specific tool
cat server-info.json | jq '.tools[] | select(.name == "validate_manifest")'
```

## Testing MCP Tools

Test individual MCP tools directly with JSON arguments using the `test-tool` command:

```bash
# Test manifest validation
poe test-tool validate_manifest '{"manifest": {"version": "4.6.2", "type": "DeclarativeSource"}, "config": {}}'

# Test secrets listing with local file
poe test-tool list_dotenv_secrets '{"dotenv_path": "/absolute/path/to/.env"}'

# Test populating missing secrets
poe test-tool populate_dotenv_missing_secrets_stubs '{"dotenv_path": "/path/to/.env", "config_paths": "api_key,secret_token"}'
```

The `poe test-tool` command is ideal for:

- Quick testing of individual tools during development
- Testing with real data without setting up full MCP client
- Debugging tool behavior with specific inputs
- Validating privatebin URL functionality

## Using PrivateBin for Connector Config Secrets

PrivateBin can be used when it's not feasible to have a local `.env` file. When using PrivateBin:

1. When creating the privatebin Secret, simply use the same format as you would for a `.env` file.
2. Always set a constant text password as an additional encryption layer. (Use the same password across all files you will use in a given session.)
3. Pass the password as an env var. (Don't give it to the agent.)
4. Private an expiration window such as 1 day or 1 week, depending on your requirements.

```bash
# Test secrets listing with privatebin URL (requires PRIVATEBIN_PASSWORD env var)
export PRIVATEBIN_PASSWORD="your_password"
poe test-tool list_dotenv_secrets '{"dotenv_path": "https://privatebin.net/?abc123"}'

# Test with privatebin URL
poe test-tool populate_dotenv_missing_secrets_stubs '{"dotenv_path": "https://privatebin.net/?abc123#passphrase", "config_paths": "api_key,secret_token"}'
```

## Testing with the VS Code MCP Extension

The repository includes a pre-configured MCP setup in `.vscode/mcp.json`. Install the MCP extension and use the command palette to access connector builder tools directly in your editor.

## MCP Tools Dev Guide

This section has tools on how to develop MCP tools.

### Tool Function Pattern

Here is an example tool definition.

```python
from typing import Annotated
from pydantic import Field
from fastmcp import FastMCP

# @app.tool  # deferred
def my_new_tool(
    param: Annotated[
        str,
        Field(description="Description of the parameter"),
    ],
) -> MyResultModel:
    """Tool description for MCP clients.
    
    Args:
        param: Parameter description
        
    Returns:
        Result description
    """
    # Implementation here
    pass

def register_tools(app: FastMCP) -> None:
    """Register all tools with the FastMCP app."""
    app.tool()(my_new_tool)
```

### Understanding MCP Capabilities: Tools, Prompts, and Resources

The Model Context Protocol (MCP) provides three distinct capability types, each serving different purposes in the AI agent workflow. Understanding when to use each type is crucial for building effective MCP servers.

#### Capability Types

**Tools** are imperative, model-controlled operations that:
- Perform actions with side effects (create, update, delete operations)
- Execute I/O operations or heavier computations
- Are invoked automatically by the LLM when it determines they're needed
- Return structured results that the model can reason about
- Examples: `validate_manifest`, `execute_stream_test_read`, `run_connector_readiness_test_report`

**Prompts** are user-controlled, pre-authored instruction templates that:
- Provide structured guidance and workflows to the model
- Require explicit user invocation (not automatically called by the LLM)
- Are side-effect free and don't perform operations
- Can reference available tools and resources in their content
- Support optional parameters for customization
- Examples: `build_connector_from_scratch`, `add_stream_to_connector`

**Resources** are application-driven, read-only data sources that:
- Expose passive data that can be read by the model or application
- Have unique URIs for identification (e.g., `connector-builder-mcp://version`)
- Support MIME types for content negotiation
- Are cacheable and idempotent (same URI always returns same data)
- Can be direct resources or parameterized templates
- Examples: version information, configuration data, documentation content

#### When to Use Each Capability Type

**Use Tools when:**
- The operation has side effects or performs I/O
- The LLM should decide when to invoke the capability
- You need to execute computations or transformations
- The operation requires authentication or credentials
- You're building, testing, or validating something

**Use Prompts when:**
- You want to provide structured workflows or playbooks
- The user should explicitly choose when to use it
- You're offering guidance, templates, or best practices
- You want to combine multiple tool calls into a cohesive workflow
- You're providing context-specific instructions

**Use Resources when:**
- You're exposing read-only data or metadata
- The data has a stable identifier (URI)
- The content is cacheable and doesn't change frequently
- You want to provide reference information
- The data should be accessible without model invocation

#### MCP Client Support for Auto-Discovery

Based on research of the MCP ecosystem and specification:

**Prompts Support:**
- ✅ **Claude Desktop**: Full support for prompt discovery and invocation
- ✅ **MCP Specification**: Prompts are a core capability with `prompts/list` and `prompts/get` methods
- ⚠️ **Other Clients**: Support varies by implementation; check client documentation

**Resources Support:**
- ✅ **Claude Desktop**: Full support for resource discovery and reading
- ✅ **MCP Specification**: Resources are a core capability with `resources/list`, `resources/read`, and `resources/templates/list` methods
- ⚠️ **Other Clients**: Support varies by implementation; check client documentation

**Note**: The MCP specification defines standard methods for discovering both prompts and resources. However, individual client implementations may vary in their support. When building MCP servers, prioritize tools for core functionality and use prompts/resources as supplementary capabilities.

## Adding New Documentation Topics

The connector builder MCP provides documentation through the `get_connector_builder_docs()` tool, which serves content from the Airbyte documentation repository. To add new topics:

### 1. Identify the Documentation Source

Topics are mapped in `connector_builder_mcp/_guidance.py` in the `TOPIC_MAPPING` dictionary. Each topic has:
- A key (the topic name that users request)
- A tuple containing:
  - The path to the documentation file (relative to the Airbyte repo root, or a full URL)
  - A brief description of the topic

### 2. Add the Topic to TOPIC_MAPPING

Edit `connector_builder_mcp/_guidance.py` and add your new topic to the `TOPIC_MAPPING` dictionary:

```python
TOPIC_MAPPING: dict[str, tuple[str, str]] = {
    # ... existing topics ...
    "your-new-topic": (
        "docs/platform/connector-development/path/to/your-doc.md",
        "Brief description of what this topic covers",
    ),
}
```

For documentation that exists in a branch or external URL, you can use a full URL:

```python
    "your-new-topic": (
        "https://raw.githubusercontent.com/airbytehq/airbyte/refs/heads/branch-name/docs/path/to/doc.md",
        "Brief description of what this topic covers",
    ),
```

### 3. Test Your New Topic

Use the `test-tool` command to verify your topic works correctly:

```bash
# Test that the topic appears in the overview
poe test-tool get_connector_builder_docs '{}'

# Test that the topic content loads correctly
poe test-tool get_connector_builder_docs '{"topic": "your-new-topic"}'
```

### 4. Update Documentation

If you're adding a significant new topic area, consider updating:
- This CONTRIBUTING.md file if it affects contributor workflows
- The README.md if it's a major feature users should know about
- Any relevant inline documentation or docstrings

### Topic Organization Guidelines

When adding topics, follow these conventions:

- **Naming**: Use lowercase with hyphens (e.g., `error-handling`, not `ErrorHandling`)
- **Descriptions**: Keep descriptions concise (under 60 characters when possible)
- **Paths**: Prefer stable paths in the main branch over branch-specific URLs when the documentation is merged
- **Grouping**: Related topics should have consistent prefixes (e.g., `yaml-*` for YAML-specific topics)

### Example: Adding a New Topic

Here's a complete example of adding a new topic for "schema detection":

```python
# In connector_builder_mcp/_guidance.py
TOPIC_MAPPING: dict[str, tuple[str, str]] = {
    # ... existing topics ...
    "schema-detection": (
        "docs/platform/connector-development/config-based/understanding-the-yaml-file/schema-detection.md",
        "Automatic schema detection and inference",
    ),
}
```

Then test it:

```bash
poe test-tool get_connector_builder_docs '{"topic": "schema-detection"}'
```

## Debugging

One or more of these may be helpful in debugging:

```terminal
export HTTPX_LOG_LEVEL=debug
export DEBUG='openai:*'
export OPENAI_AGENTS_LOG=debug
export OPENAI_LOG=debug
export FASTMCP_DEBUG=1
```
