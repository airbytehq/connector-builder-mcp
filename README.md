# builder-mcp

## Overview

The `builder-mcp` repository provides a Model Context Protocol (MCP) server implementation for Airbyte connector building operations. This repository will eventually codify relevant parts of the `builder-ai` functionality, with a focus on **AI ownership** rather than AI assist.

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

## Usage

Start the MCP server:

```bash
uv run builder-mcp
```

Or use with MCP clients by configuring the server in your MCP client configuration.

### MCP Client Configuration

To use the Builder MCP server with MCP clients like Claude Desktop, add the following configuration:

#### Stable Version (Latest PyPI Release)

```json
{
  "mcpServers": {
    "builder-mcp": {
      "command": "uvx",
      "args": ["builder-mcp"]
    }
  }
}
```

#### Development Version (Main Branch)

```json
{
  "mcpServers": {
    "builder-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/airbytehq/builder-mcp.git", "builder-mcp"]
    }
  }
}
```

#### With Custom Configuration

```json
{
  "mcpServers": {
    "builder-mcp": {
      "command": "uvx",
      "args": ["builder-mcp"],
      "env": {
        "AIRBYTE_CDK_LOG_LEVEL": "INFO"
      }
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
poe install     # Install dependencies
poe server      # Start MCP server
poe test        # Run tests
poe check       # Run all checks (lint + typecheck + test)
```

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
