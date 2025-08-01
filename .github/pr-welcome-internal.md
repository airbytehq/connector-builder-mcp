## 👋 Greetings, Airbyte Team Member!

Here are some helpful tips and reminders for your convenience.

### Testing This Branch via MCP

To test the changes in this specific branch with an MCP client like Claude Desktop, use the following configuration:

```json
{
  "mcpServers": {
    "connector-builder-mcp-dev": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/airbytehq/connector-builder-mcp.git@{{ .branch_name }}", "connector-builder-mcp"]
    }
  }
}
```

### Testing This Branch via CLI

You can test this version of the MCP Server using the following CLI snippet:

```bash
# Run the CLI from this branch:
uvx 'git+https://github.com/airbytehq/connector-builder-mcp.git@{{ .branch_name }}#egg=airbyte-connector-builder-mcp' --help
```

### PR Slash Commands

Airbyte Maintainers can execute the following slash commands on your PR:

- `/autofix` - Fixes most formatting and linting issues
- `/poe <command>` - Runs any poe command in the uv virtual environment

[📝 _Edit this welcome message._](https://github.com/airbytehq/connector-builder-mcp/blob/main/.github/pr-welcome-internal.md)
