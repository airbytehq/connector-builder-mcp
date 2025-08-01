# connector-builder-mcp

## Overview

The `connector-builder-mcp` repository provides a Model Context Protocol (MCP) server implementation for Airbyte connector building operations. This repository will eventually codify relevant parts of the `builder-ai` functionality, with a focus on **AI ownership** rather than AI assist.

### AI Ownership vs AI Assist

This project emphasizes **end-to-end AI ownership**, including:

- Autonomous connector building and testing
- Automated PR creation and management
- Complete workflow automation without human intervention

This differs from AI assist tools that merely help human developers - instead, this enables AI agents to fully own the connector development process from start to finish.

## MCP Implementation

The MCP server follows the established PyAirbyte pattern with:

- Main server module that initializes FastMCP
- Separate tool modules for different functional areas
- Comprehensive connector building capabilities exposed as MCP tools

### Available Tools

- **Manifest Operations**: Validate and resolve connector manifests
- **Stream Testing**: Test connector stream reading capabilities  
- **Configuration Management**: Validate connector configurations
- **Test Execution**: Run connector tests with proper limits and constraints

## Getting Started

To use the Builder MCP server, you'll need Python 3.10+ and [uv](https://docs.astral.sh/uv/) for package management.

For detailed development setup and contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Installation

```bash
uv sync --all-extras
```

## Manual Start

Start the MCP server:

```bash
# You can use any of these to start the server manually:
uv run connector-builder-mcp
poe mcp-serve-local
poe mcp-serve-http
poe mcp-serve-sse
```

Or use with MCP clients by configuring the server in your MCP client configuration.

### MCP Client Configuration

To use the Builder MCP server with MCP clients like Claude Desktop, add the following configuration:

#### Stable Version (Latest PyPI Release)

```json
{
  "mcpServers": {
    "connector-builder-mcp": {
      "command": "uvx",
      "args": [
        "connector-builder-mcp"
      ]
    }
  }
}
```

#### Development Version (Main Branch)

```json
{
  "mcpServers": {
    "connector-builder-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/airbytehq/connector-builder-mcp.git@main",
        "connector-builder-mcp"
      ]
    }
  }
}
```

#### Repo Cloned Out Locally

You can run from a locally cloned version of the repo using the below syntax.

Remember to update the path to your actual repo location.

```json
{
  "mcpServers": {
    "connector-builder-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/repos/connector-builder-mcp",
        "connector-builder-mcp"
      ]
    }
  }
}
```

### Using Poe Tasks

For convenience, you can use [Poe the Poet](https://poethepoet.natn.io/) task runner:

```bash
# Install Poe
uv tool install poethepoet

# Then use ergonomic commands
poe install         # Install dependencies
poe check           # Run all checks (lint + typecheck + test)
poe test            # Run tests
poe mcp-serve-local # Serve locally
poe mcp-serve-http  # Serve over HTTP
poe mcp-serve-sse   # Serve over SSE
```

You can also run `poe --help` to see a full list of available Poe commands.

If you ever want to see what a Poe task is doing (such as to run it directly or customize how it runs), check out the `poe_tasks.toml` file at the root of the repo.

## Development

This project uses [uv](https://docs.astral.sh/uv/) for package management and follows modern Python development practices.

```bash
# Install dependencies
uv sync --all-extras

# Run linting
uv run ruff check .

# Run formatting  
uv run ruff format .

# Run tests
uv run pytest tests/ -v

# Type checking
uv run mypy builder_mcp
```

Helping robots build Airbyte connectors.

## Testing

For comprehensive testing instructions, including FastMCP CLI tools and integration testing patterns, see the [Testing Guide](./TESTING.md).

## Contributing

See the [Contributing Guide](./CONTRIBUTING.md) for information on how to contribute.
