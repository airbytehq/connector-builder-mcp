"""GUIDANCE domain tools - Documentation and connector discovery for OpenAPI/Sonar.

This module contains tools for getting guidance and documentation about
building OpenAPI-based connectors with Sonar's connector-sdk.
"""

import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def get_openapi_connector_docs(
    topic: Annotated[
        str | None,
        Field(
            description="Specific topic to get detailed documentation for. If not provided, returns high-level overview."
        ),
    ] = None,
) -> str:
    """Get OpenAPI/Sonar connector builder documentation and guidance.

    Args:
        topic: Optional specific topic for detailed documentation

    Returns:
        High-level overview or detailed topic-specific documentation
    """
    logger.info(f"Getting OpenAPI connector docs for topic: {topic}")

    if not topic:
        return """# OpenAPI/Sonar Connector Builder Documentation

**Important**: Before starting development, call the `get_connector_builder_checklist()` tool.
The checklist provides step-by-step guidance for building OpenAPI-based connectors.


This build strategy helps you create Airbyte connectors from OpenAPI specifications using
Sonar's connector-sdk framework. The connector-sdk uses extended OpenAPI 3.0 specifications
with custom x-airbyte-* extensions to define connector behavior.


- Standard OpenAPI 3.0 YAML or JSON format
- Defines API paths, operations, schemas, and authentication
- Extended with x-airbyte-* custom properties

- **x-airbyte-resource**: Marks an operation as an Airbyte resource (stream)
- **x-airbyte-verb**: Specifies the operation type (read, write, etc.)
- **x-airbyte-pagination**: Configures pagination behavior
- **x-airbyte-token-path**: Specifies where to find pagination tokens in responses

- Supports API Key, Bearer Token, OAuth 2.0, and Basic Auth
- Configured via OpenAPI securitySchemes
- Mapped to Airbyte authentication types


For detailed guidance on specific aspects, request documentation for:
- **openapi_overview**: Detailed overview of OpenAPI connector development
- **x_airbyte_extensions**: Guide to custom OpenAPI extensions
- **authentication**: Authentication configuration patterns
- **pagination**: Pagination strategies and configuration
- **schema_mapping**: Mapping OpenAPI schemas to Airbyte schemas
"""

    topic_docs = {
        "openapi_overview": """# OpenAPI Connector Development Overview

OpenAPI-based connectors use extended OpenAPI 3.0 specifications to define
how the connector interacts with APIs. The connector-sdk reads the OpenAPI
spec and generates connector code automatically.


1. **Obtain OpenAPI Specification**: Get or create an OpenAPI 3.0 spec for the API
2. **Add x-airbyte Extensions**: Mark resources and configure behavior
3. **Configure Authentication**: Set up security schemes
4. **Test Resources**: Validate each resource works correctly
5. **Package Connector**: Generate final connector package


- Rapid development from existing API documentation
- Automatic code generation
- Type-safe schema definitions
- Built-in validation
""",
        "x_airbyte_extensions": """# x-airbyte-* Extensions Guide

Custom OpenAPI extensions that define Airbyte-specific behavior:

Marks an operation as an Airbyte resource (stream).
```yaml
paths:
  /users:
    get:
      x-airbyte-resource: users
      x-airbyte-verb: read
```

Configures pagination for a resource.
```yaml
x-airbyte-pagination:
  type: cursor
  cursor_path: $.next_page_token
```

Specifies where to find pagination tokens in responses.
```yaml
x-airbyte-token-path: $.pagination.next
```
""",
        "authentication": """# Authentication Configuration

Configure authentication using OpenAPI securitySchemes:

```yaml
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
```

```yaml
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
```

```yaml
components:
  securitySchemes:
    OAuth2:
      type: oauth2
      flows:
        authorizationCode:
          authorizationUrl: https://api.example.com/oauth/authorize
          tokenUrl: https://api.example.com/oauth/token
```
""",
        "pagination": """# Pagination Strategies

Configure pagination using x-airbyte-pagination extension:

```yaml
x-airbyte-pagination:
  type: cursor
  cursor_path: $.next_page_token
  has_more_path: $.has_more
```

```yaml
x-airbyte-pagination:
  type: offset
  limit_param: limit
  offset_param: offset
```

```yaml
x-airbyte-pagination:
  type: page
  page_param: page
  page_size_param: per_page
```
""",
        "schema_mapping": """# Schema Mapping

OpenAPI schemas are automatically mapped to Airbyte schemas:

- string → string
- integer → integer
- number → number
- boolean → boolean
- array → array
- object → object

Nested objects in OpenAPI schemas are preserved in Airbyte schemas.

Required fields from OpenAPI are marked as required in Airbyte schemas.

Nullable fields are handled using oneOf with null type.
""",
    }

    if topic in topic_docs:
        return topic_docs[topic]

    return f"# {topic} Documentation\n\nTopic '{topic}' not found. Available topics: {', '.join(topic_docs.keys())}"


def register_guidance_tools(
    app: FastMCP,
):
    """Register guidance tools in the MCP server."""
    register_mcp_tools(app, domain=ToolDomain.GUIDANCE)
