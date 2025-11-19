"""GUIDANCE domain tools - Documentation for Kotlin source connectors.

This module contains tools for getting guidance and documentation about
building Kotlin-based source connectors.
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
def get_kotlin_source_connector_docs(
    topic: Annotated[
        str | None,
        Field(
            description="Specific topic to get detailed documentation for. If not provided, returns high-level overview."
        ),
    ] = None,
) -> str:
    """Get Kotlin source connector builder documentation and guidance.

    Args:
        topic: Optional specific topic for detailed documentation

    Returns:
        High-level overview or detailed topic-specific documentation
    """
    logger.info(f"Getting Kotlin source connector docs for topic: {topic}")

    if not topic:
        return """# Kotlin Source Connector Builder Documentation

**Important**: Before starting development, call the `get_connector_builder_checklist()` tool.
The checklist provides step-by-step guidance for building Kotlin-based source connectors.


This build strategy helps you create Airbyte source connectors using Kotlin. Kotlin source
connectors are built using the Airbyte CDK for Java/Kotlin and provide full programmatic
control over connector behavior.


- Implement the `Source` interface from Airbyte CDK
- Define spec(), check(), and discover() operations
- Implement read() operation for data extraction

- Extend `HttpStream` for REST API sources
- Extend `IncrementalStream` for incremental sync support
- Override methods like path(), parseResponse(), nextPageToken()

- Define connector configuration in spec.yaml
- Use ConfiguredAirbyteCatalog for stream selection
- Handle authentication credentials securely

- Unit tests for individual stream classes
- Integration tests with real API calls
- Acceptance tests for connector certification


For detailed guidance on specific aspects, request documentation for:
- **kotlin_source_overview**: Detailed overview of Kotlin source development
- **stream_implementation**: Guide to implementing stream classes
- **authentication**: Authentication patterns in Kotlin
- **pagination**: Pagination strategies
- **incremental_sync**: Implementing incremental syncs
- **error_handling**: Error handling best practices
"""

    topic_docs = {
        "kotlin_source_overview": """# Kotlin Source Connector Development Overview

Kotlin source connectors provide full programmatic control over data extraction
from APIs and databases.


1. **Setup Environment**: Configure JDK, Gradle, and dependencies
2. **Create Scaffold**: Generate project structure with build files
3. **Implement Spec**: Define configuration parameters
4. **Implement Check**: Validate connection and credentials
5. **Implement Discover**: Define available streams and schemas
6. **Implement Streams**: Create stream classes for each data source
7. **Test**: Unit, integration, and acceptance testing
8. **Package**: Build Docker image


```
source-example/
├── build.gradle.kts
├── src/
│   ├── main/
│   │   ├── kotlin/
│   │   │   └── io/airbyte/integrations/source/example/
│   │   │       ├── ExampleSource.kt
│   │   │       └── streams/
│   │   │           ├── ExampleStream.kt
│   │   │           └── UsersStream.kt
│   │   └── resources/
│   │       └── spec.yaml
│   └── test/
│       └── kotlin/
└── Dockerfile
```
""",
        "stream_implementation": """# Stream Implementation Guide


```kotlin
class UsersStream(config: JsonNode) : HttpStream(config) {
    override fun path(): String = "users"

    override fun primaryKey(): List<List<String>> =
        listOf(listOf("id"))

    override fun parseResponse(
        response: HttpResponse,
        streamState: JsonNode?
    ): Iterable<JsonNode> {
        return response.body.get("data").elements().asSequence().asIterable()
    }
}
```


```kotlin
class EventsStream(config: JsonNode) : IncrementalHttpStream(config) {
    override fun cursorField(): String = "created_at"

    override fun getUpdatedState(
        currentStreamState: JsonNode?,
        latestRecord: JsonNode
    ): JsonNode {
        val currentCursor = currentStreamState?.get(cursorField())?.asText()
        val recordCursor = latestRecord.get(cursorField()).asText()
        return if (recordCursor > currentCursor) {
            Jsons.jsonNode(mapOf(cursorField() to recordCursor))
        } else {
            currentStreamState ?: Jsons.emptyObject()
        }
    }
}
```
""",
        "authentication": """# Authentication Patterns


```kotlin
override fun getAuthenticator(): HttpAuthenticator {
    return ApiKeyAuthenticator(
        config.get("api_key").asText(),
        ApiKeyAuthenticator.Location.HEADER,
        "X-API-Key"
    )
}
```


```kotlin
override fun getAuthenticator(): HttpAuthenticator {
    return BearerAuthenticator(config.get("access_token").asText())
}
```


```kotlin
override fun getAuthenticator(): HttpAuthenticator {
    return OAuth2Authenticator(
        tokenRefreshEndpoint = "https://api.example.com/oauth/token",
        clientId = config.get("client_id").asText(),
        clientSecret = config.get("client_secret").asText(),
        refreshToken = config.get("refresh_token").asText()
    )
}
```
""",
        "pagination": """# Pagination Strategies


```kotlin
override fun nextPageToken(response: HttpResponse): String? {
    val nextCursor = response.body.get("pagination")?.get("next_cursor")?.asText()
    return if (nextCursor.isNullOrEmpty()) null else nextCursor
}

override fun request(
    streamSlice: StreamSlice?,
    streamState: JsonNode?,
    nextPageToken: String?
): HttpRequest {
    val params = mutableMapOf<String, String>()
    nextPageToken?.let { params["cursor"] = it }
    return HttpRequest.builder()
        .url(url(streamSlice))
        .params(params)
        .build()
}
```


```kotlin
private var offset = 0
private val limit = 100

override fun nextPageToken(response: HttpResponse): String? {
    val records = parseResponse(response, null).count()
    return if (records < limit) null else (offset + limit).toString()
}
```
""",
        "incremental_sync": """# Implementing Incremental Syncs


Define the field used for incremental syncs:

```kotlin
override fun cursorField(): String = "updated_at"
```


Track and update sync state:

```kotlin
override fun getUpdatedState(
    currentStreamState: JsonNode?,
    latestRecord: JsonNode
): JsonNode {
    val currentCursor = currentStreamState?.get(cursorField())?.asText() ?: "1970-01-01"
    val recordCursor = latestRecord.get(cursorField()).asText()

    return Jsons.jsonNode(
        mapOf(cursorField() to maxOf(currentCursor, recordCursor))
    )
}
```


Add cursor to API requests:

```kotlin
override fun request(
    streamSlice: StreamSlice?,
    streamState: JsonNode?,
    nextPageToken: String?
): HttpRequest {
    val params = mutableMapOf<String, String>()

    streamState?.get(cursorField())?.asText()?.let {
        params["since"] = it
    }

    return HttpRequest.builder()
        .url(url(streamSlice))
        .params(params)
        .build()
}
```
""",
        "error_handling": """# Error Handling Best Practices


```kotlin
override fun shouldRetry(response: HttpResponse): Boolean {
    return response.statusCode in listOf(429, 500, 502, 503, 504)
}

override fun backoffTime(response: HttpResponse): Duration {
    val retryAfter = response.headers["Retry-After"]?.firstOrNull()
    return if (retryAfter != null) {
        Duration.ofSeconds(retryAfter.toLong())
    } else {
        Duration.ofSeconds(30)
    }
}
```


```kotlin
override fun parseResponse(
    response: HttpResponse,
    streamState: JsonNode?
): Iterable<JsonNode> {
    if (!response.isSuccessful) {
        val errorMessage = response.body.get("error")?.get("message")?.asText()
            ?: "Unknown error"
        throw RuntimeException("API error: $errorMessage")
    }
    return response.body.get("data").elements().asSequence().asIterable()
}
```
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
