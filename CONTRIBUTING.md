# Contributing to Builder MCP

Thank you for your interest in contributing to the Builder MCP project! This guide will help you get started with development and testing.

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python package management. Make sure you have uv installed:

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/airbytehq/builder-mcp.git
   cd builder-mcp
   ```

2. **Install dependencies**:
   ```bash
   uv sync --all-extras
   ```

3. **Verify the installation**:
   ```bash
   uv run builder-mcp --help
   ```

## Development Workflow

We use [Poe the Poet](https://poethepoet.natn.io/) for task automation. Install it with:

```bash
uv tool install poethepoet
```

### Available Tasks

```bash
# Install/sync dependencies
poe install        # or: uv sync --all-extras
poe sync          # alias for install

# Code quality
poe format        # Format code with ruff
poe lint          # Lint code with ruff  
poe lint-fix      # Lint and auto-fix issues
poe typecheck     # Type check with mypy

# Testing
poe test          # Run tests with verbose output
poe test-fast     # Run tests, stop on first failure

# MCP server operations
poe server        # Start the MCP server
poe inspect       # Inspect available MCP tools

# Combined workflows
poe check         # Run lint + typecheck + test
```

### Manual Commands (without Poe)

If you prefer to run commands directly with uv:

```bash
# Development
uv sync --all-extras                              # Install dependencies
uv run ruff format .                              # Format code
uv run ruff check .                               # Lint code
uv run mypy builder_mcp                           # Type checking
uv run pytest tests/ -v                          # Run tests

# MCP server
uv run builder-mcp                                # Start server
uv run fastmcp inspect builder_mcp/server.py:app # Inspect tools
```

## Testing

The project includes comprehensive tests covering:

- **Server functionality**: MCP server initialization and tool registration
- **Connector builder tools**: Manifest validation, stream testing, and resolution
- **Utility functions**: Configuration filtering and validation

Run the full test suite:

```bash
poe test
# or
uv run pytest tests/ -v
```

### Testing with Real Connectors

To test with actual Airbyte connector manifests:

1. Prepare a connector manifest (JSON format)
2. Use the MCP tools through the server or test them directly
3. Verify that validation, stream testing, and resolution work as expected

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

- **Line length**: 100 characters
- **Target Python version**: 3.10+
- **Import sorting**: Automatic with ruff
- **Type hints**: Required for all public functions

Before submitting changes:

```bash
poe check  # Runs formatting, linting, type checking, and tests
```

## MCP Tool Development

When adding new MCP tools:

1. **Add the tool function** in the appropriate module (e.g., `builder_mcp/_connector_builder.py`)
2. **Use proper type annotations** with Pydantic models for complex inputs/outputs
3. **Register the tool** in the module's registration function
4. **Add comprehensive tests** covering success and failure cases
5. **Update documentation** if the tool adds new capabilities

### Tool Function Pattern

```python
from typing import Annotated
from pydantic import Field
from fastmcp import FastMCP

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

## AI Ownership Focus

This project emphasizes **AI ownership** rather than AI assistance. When contributing:

- **Design for autonomy**: Tools should enable end-to-end AI control of connector building
- **Comprehensive error handling**: AI agents need clear error messages and recovery paths  
- **Structured outputs**: Use Pydantic models for consistent, parseable responses
- **Testing workflows**: Include tools that support automated testing and validation

## Submitting Changes

1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
2. **Make your changes** following the code style guidelines
3. **Run the full test suite**: `poe check`
4. **Commit with clear messages**: Use conventional commit format
5. **Push and create a pull request**

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new MCP tool for stream discovery
fix: resolve manifest validation edge case
docs: update contributing guidelines
test: add integration tests for connector builder
```

## Getting Help

- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Code Review**: All changes require review before merging

## Project Structure

```
builder-mcp/
├── builder_mcp/           # Main package
│   ├── server.py         # FastMCP server entry point
│   ├── _connector_builder.py  # Connector building tools
│   └── _util.py          # Shared utilities
├── tests/                # Test suite
├── poe_tasks.toml        # Task automation config
├── pyproject.toml        # Project configuration
└── CONTRIBUTING.md       # This file
```

Thank you for contributing to Builder MCP! 🚀
