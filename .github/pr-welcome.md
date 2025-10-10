## 👋 Welcome to the Airbyte Connector Builder MCP!

Thank you for your contribution! We're excited to have you in the Airbyte community.

### Testing This Branch via MCP

To test the changes in this specific branch with an MCP client like Claude Desktop, use the following configuration:

```json
{
  "mcpServers": {
    "connector-builder-mcp-dev": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/{{ .repo_name }}.git@{{ .branch_name }}", "connector-builder-mcp"]
    }
  }
}
```

### Testing This Branch via CLI

You can test this version of the MCP Server using the following CLI snippet:

```bash
# Run the CLI from this branch:
uvx 'git+https://github.com/{{ .repo_name }}.git@{{ .branch_name }}#egg=airbyte-connector-builder-mcp' --help
```

### PR Slash Commands

Airbyte Maintainers can execute the following slash commands on your PR:

- `/autofix` - Fixes most formatting and linting issues
- `/build-connector prompt="<your prompt>"` - Builds a connector on-demand using the AI builder
- `/poe <command>` - Runs any poe command in the uv virtual environment
- `/test` - Runs the test suite

### AI Builder Evaluations

AI builder evaluations run automatically under the following conditions:
- When a PR is marked as "ready for review"
- When a PR is reopened
- When the PR title contains `[llm]`, `[agent]`, or `[eval]`

Evaluations also run on a schedule (Mon/Wed/Fri at midnight UTC) and can be manually triggered via workflow dispatch.

### Helpful Resources

- [Contributing Guidelines](https://github.com/airbytehq/connector-builder-mcp/blob/main/CONTRIBUTING.md)
- [Airbyte Slack](https://airbytehq.slack.com/)

If you have any questions, feel free to ask in the PR comments or join our Slack community.

[📝 _Edit this welcome message._](https://github.com/airbytehq/connector-builder-mcp/blob/main/.github/pr-welcome.md)
