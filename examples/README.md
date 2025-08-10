# Connector Builder MCP Examples

This directory contains example scripts demonstrating how to use and integrate with the connector-builder-mcp server.

## mcp-use Integration Demo

The `mcp_use_demo.py` script demonstrates how to use [mcp-use](https://docs.mcp-use.com) as a wrapper for connector-builder-mcp, providing vendor-neutral access to connector development tools.

### Features Demonstrated

- **Direct Tool Calls**: Programmatic access to MCP tools without LLM overhead
- **LLM Integration**: AI-powered connector development workflows using any LangChain-supported model
- **Multi-Tool Workflows**: Orchestrating multiple connector building tools in sequence

### Usage

```bash
# Run the demo (uv will automatically install dependencies)
uv run examples/mcp_use_demo.py

# For LLM integration demo, set OpenAI API key
export OPENAI_API_KEY="your-api-key"
uv run examples/mcp_use_demo.py
```

### Dependencies

The script uses uv's inline dependency management with the following packages:
- `mcp-use>=0.1.0` - MCP client library
- `langchain-openai>=0.1.0` - OpenAI integration for LLM demos
- `python-dotenv>=1.0.0` - Environment variable management

### What This Enables

Using mcp-use as a wrapper for connector-builder-mcp provides:

1. **Vendor Neutrality**: Use any LLM provider instead of being locked to Claude Desktop
2. **Programmatic Access**: Build custom tools and automation around connector development
3. **Multi-Server Workflows**: Combine connector-builder-mcp with other MCP servers
4. **Custom Integrations**: Embed connector development capabilities in your own applications

### Example Use Cases

- **CI/CD Integration**: Automated connector validation in build pipelines
- **Custom Development Tools**: Build specialized UIs for connector development
- **Multi-LLM Workflows**: Compare connector analysis across different AI models
- **Batch Processing**: Validate and test multiple connectors programmatically

## Integration Benefits

This integration demonstrates the strategic value of mcp-use:

- **Breaks vendor lock-in** from Claude Desktop/VS Code limitations
- **Enables any LLM** to access connector development tools
- **Supports automation** through direct tool calls
- **Facilitates custom workflows** combining multiple MCP servers
- **Maintains compatibility** with existing connector-builder-mcp functionality

The demo shows three usage patterns:
1. **Direct tool calls** for automation and scripting
2. **LLM integration** for AI-powered development assistance  
3. **Multi-tool workflows** for complex connector development tasks

All while maintaining the same powerful connector building capabilities provided by connector-builder-mcp.
