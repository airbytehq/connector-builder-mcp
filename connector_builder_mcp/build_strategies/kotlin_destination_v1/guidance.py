"""GUIDANCE domain tools - Documentation for Kotlin destination connectors.

This module contains tools for getting guidance and documentation about
building Kotlin-based destination connectors.
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
def get_kotlin_destination_connector_docs(
    topic: Annotated[
        str | None,
        Field(
            description="Specific topic to get detailed documentation for. If not provided, returns high-level overview."
        ),
    ] = None,
) -> str:
    """Get Kotlin destination connector builder documentation and guidance.

    Args:
        topic: Optional specific topic for detailed documentation

    Returns:
        High-level overview or detailed topic-specific documentation
    """
    logger.info(f"Getting Kotlin destination connector docs for topic: {topic}")

    if not topic:
        return """# Kotlin Destination Connector Builder Documentation

**Important**: Before starting development, call the `get_connector_builder_checklist()` tool.
The checklist provides step-by-step guidance for building Kotlin-based destination connectors.


This build strategy helps you create Airbyte destination connectors using Kotlin. Kotlin
destination connectors are built using the Airbyte CDK for Java/Kotlin and provide full
programmatic control over how data is written to destination systems.


- Implement the `Destination` interface from Airbyte CDK
- Define spec() and check() operations
- Implement write() operation for data ingestion

- Implement `AirbyteMessageConsumer` for processing records
- Handle batching and buffering for efficient writes
- Manage transactions and error handling

- **Append**: Add new records without modifying existing data
- **Overwrite**: Replace all existing data with new data
- **Upsert**: Update existing records or insert new ones

- Map Airbyte types to destination system types
- Handle nested objects and arrays
- Support type conversions and transformations


For detailed guidance on specific aspects, request documentation for:
- **kotlin_destination_overview**: Detailed overview of Kotlin destination development
- **consumer_implementation**: Guide to implementing consumer classes
- **write_modes**: Understanding and implementing write modes
- **batching**: Batching strategies for efficient writes
- **schema_mapping**: Type mapping and transformations
- **error_handling**: Error handling and retry logic
"""

    topic_docs = {
        "kotlin_destination_overview": """# Kotlin Destination Connector Development Overview

Kotlin destination connectors provide full programmatic control over how data is
written to databases, data warehouses, and other storage systems.


1. **Setup Environment**: Configure JDK, Gradle, and dependencies
2. **Create Scaffold**: Generate project structure with build files
3. **Implement Spec**: Define configuration parameters
4. **Implement Check**: Validate connection and credentials
5. **Implement Consumer**: Create consumer class for processing records
6. **Implement Write Modes**: Support append, overwrite, and/or upsert
7. **Test**: Unit, integration, and acceptance testing
8. **Package**: Build Docker image


```
destination-example/
├── build.gradle.kts
├── src/
│   ├── main/
│   │   ├── kotlin/
│   │   │   └── io/airbyte/integrations/destination/example/
│   │   │       ├── ExampleDestination.kt
│   │   │       ├── ExampleConsumer.kt
│   │   │       └── writers/
│   │   │           ├── ExampleWriter.kt
│   │   │           └── BatchWriter.kt
│   │   └── resources/
│   │       └── spec.yaml
│   └── test/
│       └── kotlin/
└── Dockerfile
```
""",
        "consumer_implementation": """# Consumer Implementation Guide


```kotlin
class ExampleConsumer(
    private val config: JsonNode,
    private val catalog: ConfiguredAirbyteCatalog
) : AirbyteMessageConsumer {
    
    private val writers = mutableMapOf<String, StreamWriter>()
    
    override fun start() {
        // Initialize connections and writers
        catalog.streams.forEach { stream ->
            writers[stream.stream.name] = createWriter(stream)
        }
    }
    
    override fun accept(message: AirbyteMessage) {
        when (message.type) {
            Type.RECORD -> {
                val streamName = message.record.stream
                writers[streamName]?.write(message.record.data)
            }
            Type.STATE -> {
                // Flush buffers and commit
                writers.values.forEach { it.flush() }
            }
        }
    }
    
    override fun close() {
        writers.values.forEach { it.close() }
    }
}
```


```kotlin
class BufferedConsumer(
    private val config: JsonNode,
    private val catalog: ConfiguredAirbyteCatalog,
    private val bufferSize: Int = 1000
) : AirbyteMessageConsumer {
    
    private val buffers = mutableMapOf<String, MutableList<JsonNode>>()
    
    override fun accept(message: AirbyteMessage) {
        when (message.type) {
            Type.RECORD -> {
                val streamName = message.record.stream
                val buffer = buffers.getOrPut(streamName) { mutableListOf() }
                buffer.add(message.record.data)
                
                if (buffer.size >= bufferSize) {
                    flushBuffer(streamName)
                }
            }
            Type.STATE -> {
                flushAllBuffers()
            }
        }
    }
    
    private fun flushBuffer(streamName: String) {
        val buffer = buffers[streamName] ?: return
        writers[streamName]?.writeBatch(buffer)
        buffer.clear()
    }
}
```
""",
        "write_modes": """# Write Modes Implementation


```kotlin
class AppendWriter(
    private val tableName: String,
    private val connection: Connection
) : StreamWriter {
    
    override fun write(record: JsonNode) {
        val sql = "INSERT INTO $tableName (${getColumns()}) VALUES (${getPlaceholders()})"
        connection.prepareStatement(sql).use { stmt ->
            setParameters(stmt, record)
            stmt.executeUpdate()
        }
    }
}
```


```kotlin
class OverwriteWriter(
    private val tableName: String,
    private val connection: Connection
) : StreamWriter {
    
    private var isFirstBatch = true
    
    override fun writeBatch(records: List<JsonNode>) {
        if (isFirstBatch) {
            // Truncate or drop/recreate table
            connection.createStatement().use {
                it.execute("TRUNCATE TABLE $tableName")
            }
            isFirstBatch = false
        }
        
        // Insert records
        records.forEach { write(it) }
    }
}
```


```kotlin
class UpsertWriter(
    private val tableName: String,
    private val primaryKeys: List<String>,
    private val connection: Connection
) : StreamWriter {
    
    override fun write(record: JsonNode) {
        val sql = buildUpsertSql()
        connection.prepareStatement(sql).use { stmt ->
            setParameters(stmt, record)
            stmt.executeUpdate()
        }
    }
    
    private fun buildUpsertSql(): String {
        // PostgreSQL example
        return """
            INSERT INTO $tableName (${getColumns()})
            VALUES (${getPlaceholders()})
            ON CONFLICT (${primaryKeys.joinToString()})
            DO UPDATE SET ${getUpdateClause()}
        """.trimIndent()
    }
}
```
""",
        "batching": """# Batching Strategies


```kotlin
class BatchWriter(
    private val batchSize: Int = 1000
) {
    private val buffer = mutableListOf<JsonNode>()
    
    fun addRecord(record: JsonNode) {
        buffer.add(record)
        if (buffer.size >= batchSize) {
            flush()
        }
    }
    
    fun flush() {
        if (buffer.isEmpty()) return
        
        val sql = buildBatchInsertSql(buffer.size)
        connection.prepareStatement(sql).use { stmt ->
            var paramIndex = 1
            buffer.forEach { record ->
                setParameters(stmt, record, paramIndex)
                paramIndex += getColumnCount()
            }
            stmt.executeUpdate()
        }
        buffer.clear()
    }
}
```


```kotlin
class TimeBasedBatchWriter(
    private val flushIntervalMs: Long = 5000
) {
    private val buffer = mutableListOf<JsonNode>()
    private var lastFlushTime = System.currentTimeMillis()
    
    fun addRecord(record: JsonNode) {
        buffer.add(record)
        
        val now = System.currentTimeMillis()
        if (now - lastFlushTime >= flushIntervalMs) {
            flush()
            lastFlushTime = now
        }
    }
}
```
""",
        "schema_mapping": """# Schema Mapping and Type Conversion


```kotlin
object TypeMapper {
    fun airbyteTypeToSqlType(airbyteType: JsonNode): String {
        return when (airbyteType.get("type").asText()) {
            "string" -> "VARCHAR"
            "integer" -> "BIGINT"
            "number" -> "DOUBLE"
            "boolean" -> "BOOLEAN"
            "array" -> "JSON"
            "object" -> "JSON"
            else -> "VARCHAR"
        }
    }
    
    fun convertValue(value: JsonNode, targetType: String): Any? {
        return when (targetType) {
            "BIGINT" -> value.asLong()
            "DOUBLE" -> value.asDouble()
            "BOOLEAN" -> value.asBoolean()
            "JSON" -> value.toString()
            else -> value.asText()
        }
    }
}
```


```kotlin
class SchemaManager(private val connection: Connection) {
    
    fun createTableFromAirbyteSchema(
        tableName: String,
        schema: JsonNode
    ) {
        val columns = schema.get("properties").fields().asSequence()
            .map { (name, type) ->
                "$name ${TypeMapper.airbyteTypeToSqlType(type)}"
            }
            .joinToString(", ")
        
        val sql = "CREATE TABLE IF NOT EXISTS $tableName ($columns)"
        connection.createStatement().use { it.execute(sql) }
    }
}
```
""",
        "error_handling": """# Error Handling and Retry Logic


```kotlin
class RetryableWriter(
    private val delegate: StreamWriter,
    private val maxRetries: Int = 3
) : StreamWriter {
    
    override fun write(record: JsonNode) {
        var attempt = 0
        var lastException: Exception? = null
        
        while (attempt < maxRetries) {
            try {
                delegate.write(record)
                return
            } catch (e: SQLException) {
                lastException = e
                attempt++
                
                if (isRetryable(e)) {
                    Thread.sleep(getBackoffDelay(attempt))
                } else {
                    throw e
                }
            }
        }
        
        throw RuntimeException("Failed after $maxRetries attempts", lastException)
    }
    
    private fun isRetryable(e: SQLException): Boolean {
        // Check for transient errors
        return e.sqlState in listOf("08001", "08006", "40001")
    }
    
    private fun getBackoffDelay(attempt: Int): Long {
        return (1000L * Math.pow(2.0, attempt.toDouble())).toLong()
    }
}
```


```kotlin
class TransactionalWriter(
    private val connection: Connection
) : StreamWriter {
    
    override fun writeBatch(records: List<JsonNode>) {
        connection.autoCommit = false
        try {
            records.forEach { write(it) }
            connection.commit()
        } catch (e: Exception) {
            connection.rollback()
            throw e
        } finally {
            connection.autoCommit = true
        }
    }
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
