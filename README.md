# connector-builder-mcp

*Helping robots build Airbyte connectors.*

## Overview

A Model Context Protocol (MCP) server for Airbyte connector building operations, enabling **AI ownership** of the complete connector development lifecycle - from manifest validation to automated testing and PR creation.

### Key Features

- **Manifest Operations**: Validate and resolve connector manifests
- **Stream Testing**: Test connector stream reading capabilities  
- **Configuration Management**: Validate connector configurations
- **Test Execution**: Run connector tests with proper limits and constraints
- **Session-Scoped Encryption**: Optionally encrypt secrets client-side for enhanced security (see [docs/encryption.md](./docs/encryption.md))

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

For information on running from source, see the [Contributing Guide](./CONTRIBUTING.md).

### Complementary MCP Servers

The below MCP servers have been tested to work well with the Connector Builder MCP server and will complement its capabilities.

- **Claude Code Users:** You should only need the PyAirbyte MCP server for most tasks. Specifically, this enables publishing to Airbyte Cloud, running local tests, and validating manifests and configurations.
- **Claude Desktop Users:** As of this writing, Claude Desktop does not have built-in file system or timekeeping capabilities. Therefore, you will likely _also_ want to add the Files Server MCP.
- **Other Clients:** Depending on your client, you may want to add the Timer MCP and/or the Playwright MCP for web browsing capabilities.

#### PyAirbyte MCP

The [PyAirbyte MCP Server](https://airbytehq.github.io/PyAirbyte/airbyte/mcp.html) (powered by [PyAirbyte](https://github.com/airbytehq/PyAirbyte)) gives the ability to publish and test connector definitions to your Airbyte Cloud workspace. It also includes tools for more extensive local tests, including syncing data locally to a cache and querying the results with SQL.

```jsonc
{
  "mcpServers": {
    // ... other servers defined here ...
    "airbyte-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--python=3.11",
        "--from=airbyte@latest",
        "airbyte-mcp"
      ],
      "env": {
        "AIRBYTE_MCP_ENV_FILE": "/Users/youruser/.mcp/airbyte_mcp.env"
      }
    }
  }
}
```

Your `airbyte_mcp.env` file should contain your Airbyte Cloud credentials:

```ini
# Airbyte Project Artifacts Directory
AIRBYTE_PROJECT_DIR=/path/to/any/writeable/project-dir

# Airbyte Cloud Credentials (Required for Airbyte Cloud Operations)
AIRBYTE_CLOUD_WORKSPACE_ID=your_workspace_id
AIRBYTE_CLOUD_CLIENT_ID=your_api_key
AIRBYTE_CLOUD_CLIENT_SECRET=your_api_secret

# Optional: Google Creds to Use for GCP GSM (Google Secret Manager):
GCP_GSM_CREDENTIALS_JSON={...inline-json...}
```

For more detailed setup instructions, please see the [PyAirbyte MCP docs](https://airbytehq.github.io/PyAirbyte/airbyte/mcp.html).

#### Files Server MCP

If your agent doesn't already have the ability to read-write files, you can add this:

```json
{
  "mcpServers": {
    // ... other servers defined here ...
    "files-server": {
      "command": "npx",
      "args": [
        "mcp-server-filesystem",
        "/path/to/your/build-artifacts/"
      ]
    }
  }
}
```

#### Playwright MCP (Web Browsing)

Playwright is the most common tool used for web browsing, and it doesn't require an API key and it can accomplish most web tasks.

```jsonc
{
  "mcpServers": {
    // ... other servers defined here ...
    "playwright-web-browser": {
      "command": "npx",
      "args": [
          "@playwright/mcp@latest",
          "--headless"
      ],
      "env": {}
    }
  }
}
```

#### Timer MCP

If you'd like to time your agent and it does not already include timekeeping ability, you can add this timer tool:  

```json
{
  "mcpServers": {
    // ... other servers defined here ...
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time", "--local-timezone", "America/Los_Angeles"]
    }
  }
}
```

### VS Code MCP Extension

For VS Code users with the MCP extension, use the included configuration in `.vscode/mcp.json`.

## Contributing and Testing Guides

- **[Contributing Guide](./CONTRIBUTING.md)** - Development setup, workflows, and contribution guidelines
- **[Testing Guide](./TESTING.md)** - Comprehensive testing instructions and best practices
