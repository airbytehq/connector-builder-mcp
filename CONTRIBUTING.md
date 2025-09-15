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

## Debugging

One or more of these may be helpful in debugging:

```terminal
export HTTPX_LOG_LEVEL=debug
export DEBUG='openai:*'
export OPENAI_AGENTS_LOG=debug
export OPENAI_LOG=debug
export FASTMCP_DEBUG=1
```
