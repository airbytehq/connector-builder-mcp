# connector-builder-mcp

*Helping robots build Airbyte connectors.*

## Overview

A Model Context Protocol (MCP) server for Airbyte connector building operations, enabling **AI ownership** of the complete connector development lifecycle - from manifest validation to automated testing and PR creation.

### Key Features

- **Manifest Operations**: Validate and resolve connector manifests
- **Stream Testing**: Test connector stream reading capabilities  
- **Configuration Management**: Validate connector configurations
- **Test Execution**: Run connector tests with proper limits and constraints

## Quick Start

**Prerequisites:**

- [uv](https://docs.astral.sh/uv/) for package management (`brew install uv`)
- Python 3.10+ (`uv python install 3.10`)

If you are developing or testing locally, you will also want to install:

- [PoeThePoet](https://poethepoet.natn.io) as a task manager (`uv tool install poethepoet`)

*See the [Contributing Guide](CONTRIBUTING.md) or [Testing Guide](TESTING.md) for more information about working with the repo locally.*

**Install:**

The Poe `sync` and `install` commands are identical, giving a quick way to update your virtual environment or create one from scratch, if needed.

```bash
# These are identical:
uv sync --all-extras
poe install
poe sync
```

**Run:**

```bash
# You can use any of these to start the server manually:
uv run connector-builder-mcp
poe mcp-serve-local
poe mcp-serve-http
poe mcp-serve-sse
```

## MCP Client Configuration

To use with MCP clients like Claude Desktop, add the following configuration:

### Stable Version (Latest PyPI Release)

```json
{
  "mcpServers": {
    "connector-builder-mcp": {
      "command": "uvx",
      "args": ["connector-builder-mcp"]
    }
  }
}
```

### Development Version (Main Branch)

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

### Local Development

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

### VS Code MCP Extension

For VS Code users with the MCP extension, use the included configuration in `.vscode/mcp.json`.

## Contributing and Testing Guides

- **[Contributing Guide](./CONTRIBUTING.md)** - Development setup, workflows, and contribution guidelines
- **[Testing Guide](./TESTING.md)** - Comprehensive testing instructions and best practices

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
