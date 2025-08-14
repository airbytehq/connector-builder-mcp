# FastMCP Cloud Deployment Guide

This guide walks you through deploying the connector-builder-mcp server to [FastMCP Cloud](https://fastmcp.cloud), a managed platform for hosting MCP servers.

## Overview

FastMCP Cloud provides the fastest way to deploy your MCP server with zero configuration. It automatically detects your Python dependencies, builds your server, and makes it instantly available to LLM clients like Claude Desktop and Cursor.

### Benefits of FastMCP Cloud

- **Zero Configuration**: Automatic dependency detection and deployment
- **Instant Deployment**: Deploy directly from your GitHub repository
- **Free During Beta**: No cost while the platform is in beta
- **Built-in Authentication**: Secure access with organization-based auth
- **Branch Previews**: Test changes with preview deployments
- **Automatic Scaling**: Handles traffic spikes automatically

## Prerequisites

Before deploying to FastMCP Cloud, ensure you have:

1. **GitHub Account**: Required for repository connection
2. **Python 3.10+**: Your project must use a supported Python version
3. **Dependencies File**: Either `requirements.txt` or `pyproject.toml` (already included)
4. **FastMCP Server**: Production-ready ASGI app (already configured in `connector_builder_mcp/app.py`)

## Step-by-Step Deployment

### Step 1: Prepare Your Repository

1. **Ensure your code is pushed to GitHub**:
   ```bash
   git add .
   git commit -m "Prepare for FastMCP Cloud deployment"
   git push origin main
   ```

2. **Verify the ASGI entrypoint exists**:
   - File: `connector_builder_mcp/app.py`
   - Export: `asgi_app` (already configured)

### Step 2: Connect to FastMCP Cloud

1. **Visit [fastmcp.cloud](https://fastmcp.cloud)**
2. **Sign in with your GitHub account**
3. **Create a new project**:
   - Select your `connector-builder-mcp` repository
   - Or use the FastMCP Cloud quickstart if starting fresh

### Step 3: Configure Your Deployment

In the FastMCP Cloud configuration screen, set:

#### **Project Configuration**
- **Name**: `connector-builder-mcp` (or your preferred name)
- **Entrypoint**: `connector_builder_mcp/app.py:asgi_app`
- **Branch**: `main` (or your preferred deployment branch)

#### **Authentication Settings**
- **Enable Authentication**: ✅ **Recommended**
  - Only members of your FastMCP Cloud organization can connect
  - Provides secure access to your MCP server
- **Disable Authentication**: ⚠️ **Not recommended for production**
  - Server will be publicly accessible
  - Use only for testing or internal networks

### Step 4: Deploy

1. **Click "Create Project"**
2. **Wait for deployment** (usually takes 1-2 minutes)
3. **Verify deployment success** in the dashboard

Your server will be available at:
```
https://your-project-name.fastmcp.app/mcp
```

## Environment Variables

FastMCP Cloud automatically configures most environment variables, but you can customize them:

### Required Variables
- `MCP_AUTH_TOKEN`: Automatically generated if authentication is enabled
- `PORT`: Automatically set by the platform (default: 8000)
- `HOST`: Automatically set to `0.0.0.0` for external access

### Optional Variables
You can add custom environment variables in the FastMCP Cloud dashboard:
- `LOG_LEVEL`: Set logging verbosity (INFO, DEBUG, WARNING, ERROR)
- Custom configuration for your specific use case

## Testing Your Deployment

### Health Check Endpoints

Your deployed server includes several endpoints for monitoring:

- **Health Check**: `https://your-project-name.fastmcp.app/health`
- **Readiness Check**: `https://your-project-name.fastmcp.app/ready`
- **Info Endpoint**: `https://your-project-name.fastmcp.app/info`

### MCP Endpoint

The main MCP endpoint is available at:
```
https://your-project-name.fastmcp.app/mcp
```

## Connecting LLM Clients

### Claude Desktop

Add this configuration to your Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "connector-builder-mcp": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-fetch",
        "https://your-project-name.fastmcp.app/mcp"
      ],
      "env": {
        "AUTHORIZATION": "Bearer your-auth-token"
      }
    }
  }
}
```

### Cursor

In Cursor, add the MCP server configuration:

```json
{
  "mcp": {
    "servers": {
      "connector-builder-mcp": {
        "url": "https://your-project-name.fastmcp.app/mcp",
        "auth": {
          "type": "bearer",
          "token": "your-auth-token"
        }
      }
    }
  }
}
```

### Getting Your Auth Token

If authentication is enabled:
1. Go to your FastMCP Cloud project dashboard
2. Navigate to the "Settings" or "Authentication" section
3. Copy your organization's auth token
4. Use this token in your client configuration

## Branch-Based Deployments

FastMCP Cloud automatically creates preview deployments for pull requests:

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/new-functionality
   git push origin feature/new-functionality
   ```

2. **Open a pull request** on GitHub

3. **FastMCP Cloud creates a preview deployment**:
   ```
   https://your-project-name-pr-123.fastmcp.app/mcp
   ```

4. **Test your changes** before merging to main

## Monitoring and Logs

### Viewing Logs
1. Access your FastMCP Cloud dashboard
2. Navigate to your project
3. View real-time logs and deployment status

### Health Monitoring
Monitor your server health using the built-in endpoints:
- Check `/health` for detailed status information
- Use `/ready` for simple up/down status
- Query `/info` for debugging information

## Troubleshooting

### Common Issues

#### **Deployment Fails**
- Verify your `pyproject.toml` includes all required dependencies
- Check that Python version is 3.10 or higher
- Ensure the entrypoint `connector_builder_mcp/app.py:asgi_app` exists

#### **Authentication Issues**
- Verify your auth token is correct
- Check that authentication is enabled in FastMCP Cloud
- Ensure your client configuration includes the Bearer token

#### **Connection Timeouts**
- Verify the server URL is correct
- Check that your server is responding to health checks
- Ensure no firewall or network issues

### Getting Help

- **FastMCP Discord**: [Join the community](https://discord.com/invite/aGsSC3yDF4)
- **FastMCP Documentation**: [gofastmcp.com](https://gofastmcp.com)
- **GitHub Issues**: Report issues in the connector-builder-mcp repository

## Local Testing

Before deploying to FastMCP Cloud, test your configuration locally:

```bash
# Test the ASGI app directly
python -m connector_builder_mcp.app

# Or use uvicorn for production-like testing
uvicorn connector_builder_mcp.app:asgi_app --host 0.0.0.0 --port 8000

# Test health endpoints
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/info
```

## Security Best Practices

1. **Always enable authentication** for production deployments
2. **Use strong auth tokens** (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
3. **Regularly rotate auth tokens** in production environments
4. **Monitor access logs** for suspicious activity
5. **Use HTTPS only** (automatically enforced by FastMCP Cloud)

## Next Steps

After successful deployment:

1. **Configure your LLM clients** to connect to your deployed server
2. **Set up monitoring** and alerting for production use
3. **Create branch-based workflows** for testing changes
4. **Document your deployment** for team members
5. **Consider setting up CI/CD** for automated deployments

---

**Need help?** Join the [FastMCP Discord community](https://discord.com/invite/aGsSC3yDF4) or check the [FastMCP documentation](https://gofastmcp.com) for more detailed information.
