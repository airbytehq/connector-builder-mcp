# MCP Testing Guide

This guide provides comprehensive instructions for testing the Builder MCP server using FastMCP 2.0 tools and best practices.

## Overview

The Builder MCP server provides tools for Airbyte connector building operations. This guide covers:

- Running the test suite
- Manual testing with FastMCP CLI tools
- Integration testing patterns
- Performance testing
- Debugging MCP issues

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for package management
- FastMCP 2.0 (installed automatically with dependencies)

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed development setup instructions.

## Quick Start

### Install Dependencies

```bash
poe sync
# Equivalent to: uv sync --all-extras
```

### Run All Tests

```bash
poe test
# Equivalent to: uv run pytest tests/ -v
```

### Run Specific Test Categories

```bash
# Run only integration tests
uv run pytest tests/test_integration.py -v

# Run tests requiring credentials (skipped by default)
uv run pytest tests/ -v -m requires_creds

# Run fast tests only (skip slow integration tests)
uv run pytest tests/ -v -m "not requires_creds"
```

## FastMCP CLI Tools

FastMCP 2.0 provides powerful CLI tools for testing and debugging MCP servers. For convenience, we've added poe shortcuts for common FastMCP commands.

### Server Inspection

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

#### Testing Specific Tools

After running `poe inspect`, you can examine the generated `server-info.json` file to see detailed information about each tool:

```bash
# View the complete inspection report
cat server-info.json

# Extract just the tools information using jq
cat server-info.json | jq '.tools'

# Get details for a specific tool
cat server-info.json | jq '.tools[] | select(.name == "validate_manifest")'
```

### Running the Server

Start the MCP server for manual testing:

```bash
# Run with default STDIO transport
poe mcp-serve-local
# Equivalent to: uv run connector-builder-mcp

# Run with HTTP transport for web testing
poe mcp-serve-http
# Equivalent to: uv run python -c "from connector_builder_mcp.server import app; app.run(transport='http', host='127.0.0.1', port=8000)"

# Run with SSE transport
poe mcp-serve-sse
# Equivalent to: uv run python -c "from connector_builder_mcp.server import app; app.run(transport='sse', host='127.0.0.1', port=8000)"
```

### Interactive Testing

Use FastMCP client to test tools interactively:

```bash
# First, inspect available tools
poe inspect --tools

# Create a test script
cat > test_client.py << 'EOF'
import asyncio
from fastmcp import Client

async def test_tools():
    # Connect to the server
    async with Client("connector_builder_mcp/server.py:app") as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        # Test manifest validation
        manifest = {
            "version": "4.6.2",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream", "stream_names": ["test"]},
            "streams": [],
            "spec": {"type": "Spec", "connection_specification": {"type": "object"}}
        }
        
        result = await client.call_tool("validate_manifest", {
            "manifest": manifest,
            "config": {}
        })
        print(f"Validation result: {result.text}")

if __name__ == "__main__":
    asyncio.run(test_tools())
EOF

# Run the test
uv run python test_client.py
```

### VS Code MCP Testing

For VS Code users with the MCP extension, the repository includes a pre-configured setup in `.vscode/mcp.json`. Install the MCP extension and use the command palette to access connector builder tools directly in your editor.

## Testing Patterns

### Unit Testing

Test individual MCP tools in isolation:

```python
def test_validate_manifest():
    manifest = load_test_manifest()
    result = validate_manifest(manifest, {})
    assert result.is_valid
    assert len(result.errors) == 0
```

### Integration Testing

Test complete workflows using multiple tools:

```python
def test_complete_workflow():
    # 1. Validate manifest
    validation = validate_manifest(manifest, config)
    assert validation.is_valid
    
    # 2. Resolve manifest
    resolved = execute_dynamic_manifest_resolution_test(manifest, config)
    assert isinstance(resolved, dict)
    
    # 3. Test stream reading
    stream_result = execute_stream_test_read(manifest, config, "stream_name")
    assert stream_result.success
```

### Error Testing

Test error handling and edge cases:

```python
def test_invalid_manifest():
    invalid_manifest = {"invalid": "structure"}
    result = validate_manifest(invalid_manifest, {})
    assert not result.is_valid
    assert "missing required fields" in result.errors[0]
```

### Performance Testing

Test performance with multiple operations:

```python
def test_performance():
    import time
    start = time.time()
    
    for _ in range(10):
        validate_manifest(manifest, config)
    
    duration = time.time() - start
    assert duration < 5.0  # Should complete within 5 seconds
```

## Advanced Testing

### Testing with Real Connectors

Use real connector manifests for comprehensive testing:

```bash
# Download a real connector manifest
curl -o tests/resources/real_connector.yaml \
  https://raw.githubusercontent.com/airbytehq/airbyte/master/airbyte-integrations/connectors/source-github/manifest.yaml

# Test with the real manifest
uv run pytest tests/test_integration.py::test_real_connector_validation -v
```

### Load Testing

Test server performance under load:

```python
import asyncio
import concurrent.futures
from fastmcp import Client

async def load_test():
    async with Client("connector_builder_mcp/server.py:app") as client:
        # Run 50 concurrent tool calls
        tasks = []
        for i in range(50):
            task = client.call_tool("validate_manifest", {
                "manifest": test_manifest,
                "config": {}
            })
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        assert len(results) == 50
        assert all(result.text for result in results)
```

### Memory Testing

Monitor memory usage during testing:

```bash
# Install memory profiler
uv add memory-profiler

# Run tests with memory monitoring
uv run python -m memory_profiler test_memory.py
```

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run tests with debug output
uv run pytest tests/ -v -s --log-cli-level=DEBUG
```

### MCP Protocol Debugging

Use FastMCP's built-in debugging tools:

```bash
# Run server with protocol debugging
FASTMCP_DEBUG=1 uv run connector-builder-mcp

# Inspect protocol messages (use full command for debugging flags)
uv run fastmcp inspect connector_builder_mcp/server.py:app --protocol-debug
```

### Common Issues

1. **Tool Not Found**: Ensure tools are properly registered in `register_connector_builder_tools()`
2. **Validation Errors**: Check manifest structure against Airbyte CDK requirements
3. **Network Timeouts**: Use `@pytest.mark.requires_creds` for tests that need external APIs
4. **Memory Issues**: Monitor memory usage in long-running tests

## Continuous Integration

### GitHub Actions Integration

The repository includes CI workflows that run tests automatically:

```yaml
# .github/workflows/test.yml
- name: Run MCP Tests
  run: |
    uv run pytest tests/ -v --cov=connector_builder_mcp
    uv run fastmcp inspect connector_builder_mcp/server.py:app --health
```

### Pre-commit Hooks

Install pre-commit hooks for automatic testing:

```bash
uv run pre-commit install

# Run hooks manually
uv run pre-commit run --all-files
```

## Best Practices

1. **Use Fixtures**: Create reusable test fixtures for common manifests and configurations
2. **Mark Slow Tests**: Use `@pytest.mark.requires_creds` for tests that need external resources
3. **Test Error Cases**: Always test both success and failure scenarios
4. **Performance Awareness**: Monitor test execution time and optimize slow tests
5. **Real Data**: Use real connector manifests when possible for comprehensive testing
6. **Isolation**: Ensure tests don't depend on external state or each other
7. **Documentation**: Document complex test scenarios and their purpose

## Resources

- [FastMCP Documentation](https://gofastmcp.com)
- [Airbyte CDK Documentation](https://docs.airbyte.com/connector-development/cdk-python/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Builder MCP Repository](https://github.com/airbytehq/connector-builder-mcp)
