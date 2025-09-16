# connector-builder-mcp

*Helping robots build Airbyte connectors.*

## Overview

A Model Context Protocol (MCP) server for Airbyte connector building operations, enabling **AI ownership** of the complete connector development lifecycle - from manifest validation to automated testing and PR creation.

### Key Features

- **Manifest Operations**: Validate and resolve connector manifests
- **Stream Testing**: Test connector stream reading capabilities  
- **Configuration Management**: Validate connector configurations
- **Test Execution**: Run connector tests with proper limits and constraints

## MCP Client Configuration

To use with MCP clients like Claude Desktop, add the following configuration:

### Stable Version (Latest PyPI Release)

```json
{
  "mcpServers": {
    "connector-builder-mcp--stable": {
      "command": "uvx",
      "args": [
        "airbyte-connector-builder-mcp",
      ]
    }
  }
}
```

### Development Version (Main Branch)

```json
{
  "mcpServers": {
    "connector-builder-mcp--dev-main": {
      "command": "uvx",
      "args": [
        "--from=git+https://github.com/airbytehq/connector-builder-mcp.git@main",
        "airbyte-connector-builder-mcp"
      ]
    }
  }
}
```

### Local Development

```json
{
  "mcpServers": {
    "connector-builder-mcp--local-dev": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/repos/connector-builder-mcp",
        "airbyte-connector-builder-mcp"
      ]
    }
  }
}
```

### Complementary MCP Servers

If your agents doesn't already have files and/or internet access, you may want to add one or more of these:

```json
{
  "mcpServers": {
    // ... other servers defined here ...
    "files-server": {
      "command": "npx",
      "args": [
        "mcp-server-filesystem",
        "/Users/ajsteers/.mcp/file-artifacts/"
      ]
    },
    "playwright-web-browser": {
      "command": "npx",
      "args": [
          "@playwright/mcp@latest",
          "--headless"
      ],
      env={}
    }
  }
}
```

If you'd like to time your agent, you can add this timer tool:

```json
{
  "mcpServers": {
    // ... other servers defined here ...
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time", "--local-timezone", "America/Los_Angeles"]
    },
  }
}
```

### VS Code MCP Extension

For VS Code users with the MCP extension, use the included configuration in `.vscode/mcp.json`.

## Contributing and Testing Guides

- **[Contributing Guide](./CONTRIBUTING.md)** - Development setup, workflows, and contribution guidelines
- **[Testing Guide](./TESTING.md)** - Comprehensive testing instructions and best practices
