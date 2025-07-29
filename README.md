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

## Installation

```bash
poetry install
```

## Usage

Start the MCP server:

```bash
poetry run builder-mcp
```

Or use with MCP clients by configuring the server in your MCP client configuration.

## Development

This project uses Poetry for dependency management and follows standard Python development practices.

```bash
# Install dependencies
poetry install

# Run linting
poetry run ruff check .

# Run formatting  
poetry run ruff format .
```
Helping robots build Airbyte connectors.
