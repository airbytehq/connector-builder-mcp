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

_(Note: Unlike Poetry, uv will generally auto-run a sync whenever you use `uv run`. So, `uv sync`
may not be strictly necessary.)_

### Using Poe Tasks

For convenience, install [Poe the Poet](https://poethepoet.natn.io/) task runner:

```bash
# Install Poe
uv tool install poethepoet

# View all available commands
poe --help
```

## Poe Shortcuts

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

### Tool Function Pattern

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

## Testing with GitHub Models

```bash
brew install gh
gh auth login
gh extension install https://github.com/github/gh-models
gh models --help
```

## Debugging

One or more of these may be helpful in debugging:

```terminal
export HTTPX_LOG_LEVEL=debug
export DEBUG='openai:*'
export OPENAI_AGENTS_LOG=debug
export OPENAI_LOG=debug
```
