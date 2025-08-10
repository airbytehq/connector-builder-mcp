# Connector Builder MCP Agent Examples

This directory contains example scripts demonstrating how to wrap the connector-builder-mcp and pyairbyte-mcp servers using different approaches for automated connector building.

## Available Examples

### 1. Upsonic Framework Example (`upsonic_example.py`)

Demonstrates using the Upsonic AI agent framework to build connectors with MCP integration.

**Features:**
- Native MCP server support
- Reliability layers for production use
- Simple agent orchestration
- Automated connector building workflow

**Usage:**
```bash
uv run examples/upsonic_example.py
```

**Dependencies:** Automatically managed via uv inline dependencies
- `upsonic>=0.1.0`
- `fastmcp>=0.1.0`
- `pydantic>=2.0.0`
- `httpx>=0.25.0`

**Note:** This example demonstrates the intended workflow but requires the Upsonic framework to be available for full execution.

### 2. AutoGen Multi-Agent Example (`autogen_example.py`)

Demonstrates using Microsoft AutoGen's multi-agent framework for sophisticated connector building workflows.

**Features:**
- Multi-agent collaboration (Planner, Builder, Validator, MCP Coordinator)
- Sophisticated reasoning and iteration
- Group chat orchestration
- Comprehensive error handling

**Usage:**
```bash
export OPENAI_API_KEY="your-openai-api-key"
uv run examples/autogen_example.py
```

**Dependencies:** Automatically managed via uv inline dependencies
- `pyautogen>=0.2.0`
- `fastmcp>=0.1.0`
- `pydantic>=2.0.0`
- `httpx>=0.25.0`
- `openai>=1.0.0`

**Note:** This example demonstrates the intended workflow but requires the AutoGen framework to be available for full execution.

### 3. Basic MCP Integration Example (`basic_mcp_example.py`)

Demonstrates the core MCP integration workflow without external AI frameworks.

**Features:**
- Direct MCP workflow demonstration
- Mock responses for testing
- Simple dependency management
- Educational workflow example

**Usage:**
```bash
uv run examples/basic_mcp_example.py
```

**Dependencies:** Automatically managed via uv inline dependencies
- `httpx>=0.25.0`
- `pydantic>=2.0.0`

### 4. Working MCP Example (`working_mcp_example.py`)

Demonstrates MCP integration with simulated tool responses for testing purposes.

**Features:**
- Simulated MCP tool responses
- Complete workflow demonstration
- Error handling examples
- Result persistence

**Usage:**
```bash
uv run examples/working_mcp_example.py
```

**Dependencies:** Automatically managed via uv inline dependencies
- `httpx>=0.25.0`
- `pydantic>=2.0.0`

### 5. Real MCP Integration Example (`real_mcp_integration_example.py`)

Demonstrates actual MCP server integration using subprocess calls to real MCP tools.

**Features:**
- Real MCP tool calls via subprocess
- Actual server integration testing
- Live validation and testing
- Comprehensive error handling

**Usage:**
```bash
uv run examples/real_mcp_integration_example.py
```

**Dependencies:** Automatically managed via uv inline dependencies
- `httpx>=0.25.0`
- `pydantic>=2.0.0`

**Note:** This example requires both MCP servers to be running and accessible via `mcp-cli`.

## Prerequisites

### MCP Servers
Both examples require the following MCP servers to be running:

1. **connector-builder-mcp**: Provides tools for manifest validation, stream testing, and configuration management
2. **pyairbyte-mcp**: Provides tools for connector discovery, registry access, and local operations

### Environment Setup

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Set up MCP servers** (from the repository root):
   ```bash
   # Install connector-builder-mcp dependencies
   uv sync --all-extras
   
   # Start the MCP servers (in separate terminals)
   uv run connector-builder-mcp
   uv run pyairbyte-mcp
   ```

3. **Configure API credentials** (for testing):
   ```bash
   export STRIPE_API_KEY="sk_test_your_stripe_key"
   export OPENAI_API_KEY="your_openai_key"  # For AutoGen example
   ```

## How It Works

Both examples demonstrate the same core workflow:

1. **Discovery**: Find similar existing connectors for reference patterns
2. **Planning**: Use the connector builder checklist to create a build strategy
3. **Generation**: Create initial connector manifest using AI reasoning
4. **Validation**: Validate manifest syntax and completeness
5. **Testing**: Execute stream tests and smoke tests
6. **Iteration**: Improve based on validation and test feedback

### MCP Tool Integration

The examples leverage these key MCP tools:

**From connector-builder-mcp:**
- `get_connector_builder_checklist`: Get step-by-step building guidance
- `validate_manifest`: Validate connector manifest syntax
- `execute_stream_test_read`: Test stream reading functionality
- `execute_record_counts_smoke_test`: Run smoke tests

**From pyairbyte-mcp:**
- `list_connectors`: Find existing connectors for reference
- `get_connector_info`: Get detailed connector metadata
- `get_connector_manifest`: Retrieve existing connector manifests

## Customization

### Adding New Frameworks

To add support for additional agent frameworks:

1. Create a new example script following the naming pattern: `{framework}_example.py`
2. Use the uv inline dependency syntax:
   ```python
   #!/usr/bin/env -S uv run
   # /// script
   # dependencies = [
   #     "your-framework>=1.0.0",
   #     "fastmcp>=0.1.0"
   # ]
   # ///
   ```
3. Implement the core workflow using your framework's patterns
4. Update this README with usage instructions

### Modifying Workflows

The examples can be customized for different use cases:

- **Different APIs**: Change the `api_name` and `credentials` parameters
- **Custom validation**: Add additional validation steps or custom rules
- **Extended testing**: Include integration tests or performance benchmarks
- **Different output formats**: Modify result formatting and storage

## Troubleshooting

### Common Issues

1. **MCP servers not running**: Ensure both MCP servers are started before running examples
2. **Missing API keys**: Set required environment variables for the target APIs
3. **Dependency conflicts**: Use `uv run` to ensure isolated dependency management
4. **Network issues**: Check connectivity to target APIs and MCP servers

### Debug Mode

Add debug logging to any example by setting:
```bash
export LOG_LEVEL=DEBUG
uv run examples/{example_name}.py
```

## Contributing

When adding new examples or improving existing ones:

1. Follow the established patterns for MCP integration
2. Use uv inline dependencies for dependency management
3. Include comprehensive error handling and logging
4. Update this README with new examples and usage instructions
5. Test with multiple API types to ensure robustness

## Related Documentation

- [Connector Builder MCP Documentation](../README.md)
- [PyAirbyte MCP Documentation](https://github.com/airbytehq/PyAirbyte)
- [Upsonic Framework](https://github.com/Upsonic/Upsonic)
- [Microsoft AutoGen](https://github.com/microsoft/autogen)
- [UV Package Manager](https://docs.astral.sh/uv/)
