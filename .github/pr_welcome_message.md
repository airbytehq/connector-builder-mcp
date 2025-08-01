# PR Welcome Message

Thank you for contributing to Builder MCP! 🚀

## Testing This Branch

To test the changes in this specific branch with an MCP client like Claude Desktop, use the following configuration:

### MCP Configuration for This Branch

```json
{
  "mcpServers": {
    "builder-mcp-dev": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/airbytehq/builder-mcp.git@devin/1753831735-basic-mcp-implementation", "builder-mcp"]
    }
  }
}
```

This configuration will install and run the Builder MCP server directly from this development branch, allowing you to test the latest changes before they're merged.

## Available Tools

Once configured, you'll have access to these MCP tools:
- `validate_manifest` - Validate connector manifest structure and configuration
- `execute_stream_read` - Test reading from connector streams
- `get_resolved_manifest` - Get resolved connector manifest

## Development Setup

For local development and testing:

```bash
# Clone and setup
git clone https://github.com/airbytehq/builder-mcp.git
cd builder-mcp
git checkout devin/1753831735-basic-mcp-implementation

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Start MCP server
uv run builder-mcp
```

## Questions or Issues?

If you encounter any issues testing this branch, please leave a comment on the PR!
