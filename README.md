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
        "airbyte-connector-builder-mcp"
      ]
    }
  }
}
```

### Suggested MCP Server Config

For streamlined onboarding, the below config contains both a PyAirbyte MCP and Connector Builder MCP implementation.

```json
{
  "mcpServers": {
    "airbyte-connector-builder-mcp": {
      "command": "uvx",
      "args": [
        "airbyte-connector-builder-mcp"
      ]
    },
    "airbyte-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--python=3.11",
        "--from=airbyte@latest",
        "airbyte-mcp"
      ],
      "env": {
        "AIRBYTE_MCP_ENV_FILE": "/Users/{YOUR-USER-ID}/.mcp/airbyte_mcp.env",
        "AIRBYTE_CLOUD_MCP_SAFE_MODE": "1",
        "AIRBYTE_CLOUD_MCP_READ_ONLY": "0"
      }
    }
  }
}
```

Important:
- Remember to update the `AIRBYTE_MCP_ENV_FILE` path to your actual path, and to create a new file there at that path. Note that the file can be empty to start.
- For complete setup instructions and environment variable documentation, see the [PyAirbyte MCP documentation](https://airbytehq.github.io/PyAirbyte/airbyte/mcp.html).

### Running from Source

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
        "AIRBYTE_MCP_ENV_FILE": "/Users/{YOUR-USER-ID}/.mcp/airbyte_mcp.env",
        "AIRBYTE_CLOUD_MCP_SAFE_MODE": "1",
        "AIRBYTE_CLOUD_MCP_READ_ONLY": "0"
      }
    }
  }
}
```

Note:
- Make sure to replace `/Users/{YOUR-USER-ID}/.mcp/airbyte_mcp.env` with the actual path to your `airbyte_mcp.env` file.
  - See below for details on the contents of this file.
- For information about the `AIRBYTE_CLOUD_MCP_SAFE_MODE` and `AIRBYTE_CLOUD_MCP_READ_ONLY` environment variables, see the [PyAirbyte MCP Safety documentation](https://airbytehq.github.io/PyAirbyte/airbyte/mcp.html#airbyte-cloud-mcp-server-safety).

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

## Environment Variables

The Connector Builder MCP server supports several environment variables for configuration:

### Session Manifest Path Configuration

These environment variables allow you to customize where session manifest files are stored. **Security Note:** These overrides are only allowed in STDIO mode and will cause the server to fail at startup if used in remote mode.

Precedence (most specific to least specific):

1. **`CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH`** - Exact path to the manifest file
   - Example: `/path/to/my/manifest.yaml`
   - Most specific override, takes precedence over all others

2. **`CONNECTOR_BUILDER_MCP_SESSION_DIR`** - Session directory path
   - Example: `/path/to/my/session`
   - Manifest will be stored as `manifest.yaml` in this directory

3. **`CONNECTOR_BUILDER_MCP_SESSION_ROOT`** - Root directory for all sessions
   - Example: `/path/to/sessions`
   - Session-specific subdirectories will be created based on session ID hash

4. **`CONNECTOR_BUILDER_MCP_SESSIONS_DIR`** - Legacy session storage directory (deprecated)
   - Use `CONNECTOR_BUILDER_MCP_SESSION_ROOT` instead
   - Lowest precedence, maintained for backward compatibility

5. **Default** - If no overrides are set: `~/.mcp-sessions/{session_id_hash}/manifest.yaml`

All path overrides must be absolute paths. Relative paths will be rejected for security reasons.

### Remote Mode Configuration

- **`CONNECTOR_BUILDER_MCP_REMOTE_MODE`** - Set to `true`, `1`, or `yes` to indicate remote mode
  - Default: `false` (STDIO mode)
  - When set to `true`, path override environment variables are not allowed and will cause startup failure

## Contributing and Testing Guides

- **[Contributing Guide](./CONTRIBUTING.md)** - Development setup, workflows, and contribution guidelines
- **[Testing Guide](./TESTING.md)** - Comprehensive testing instructions and best practices

## Reporting Issues

If you encounter bugs, have feature requests, or need help:

1. **Check Existing Issues**: Search the [GitHub Issues](https://github.com/airbytehq/connector-builder-mcp/issues) to see if your issue has already been reported
2. **Create a New Issue**: If your issue is new, [open an issue](https://github.com/airbytehq/connector-builder-mcp/issues/new) with:
   - A clear, descriptive title
   - Detailed description of the problem or feature request
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Your environment details (OS, Python version, MCP client)
   - Relevant logs or error messages
3. **Community Support**: For questions and discussions, you can also reach out through the [Airbyte Community Slack](https://airbyte.com/community)

When reporting issues related to specific connectors or the Connector Builder UI itself, please file those in the main [Airbyte repository](https://github.com/airbytehq/airbyte/issues) instead.

## Troubleshooting

### Claude Code Troubleshooting

In Claude Code, you can run `/mcp` to investigate your MCP Server configuration. This will also print the paths being used for the MCP JSON config.

If for any reason, `/mcp` does not find your servers, run `/doctor` to ensure the file can be parsed. If a parsing error is occurring, it will be noted in the `/doctor` output but not in the `/mcp` output.
