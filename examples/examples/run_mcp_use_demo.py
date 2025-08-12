# /// script
# dependencies = [
#   "mcp-use>=1.0.0",
#   "langchain-openai>=0.1.0",
#   "python-dotenv>=1.0.0",
# ]
# ///
"""Demo script showing how to use mcp-use as a wrapper for connector-builder-mcp.

This script demonstrates:
1. Connecting to connector-builder-mcp via STDIO transport
2. Discovering available MCP tools
3. Running connector validation workflows
4. Using different LLM providers with mcp-use

Usage:
    uv run examples/mcp_use_demo.py

Requirements:
    - connector-builder-mcp server available in PATH
    - Optional: OpenAI API key for LLM integration demo
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient


load_dotenv()

MCP_CONFIG = {
    "mcpServers": {
        "connector-builder": {"command": "uv", "args": ["run", "connector-builder-mcp"], "env": {}}
    }
}

SAMPLE_MANIFEST = """
version: 4.6.2
type: DeclarativeSource
check:
  type: CheckStream
  stream_names:
    - users
definitions:
  streams:
    users:
      type: DeclarativeStream
      name: users
      primary_key:
        - id
      retriever:
        type: SimpleRetriever
        requester:
          type: HttpRequester
          url_base: https://jsonplaceholder.typicode.com
          path: /users
        record_selector:
          type: RecordSelector
          extractor:
            type: DpathExtractor
            field_path: []
spec:
  type: Spec
  connection_specification:
    type: object
    properties: {}
"""


async def demo_direct_tool_calls():
    """Demonstrate direct tool calls without LLM integration."""
    print("🔧 Demo 1: Direct Tool Calls")
    print("=" * 50)

    client = MCPClient.from_dict(MCP_CONFIG)

    session = await client.create_session("connector-builder")

    print("📋 Available MCP Tools:")
    tools = await session.list_tools()
    for tool in tools:
        print(f"  • {tool.name}: {tool.description}")

    print(f"\n✅ Found {len(tools)} tools available")

    print("\n🔍 Validating sample manifest...")
    result = await session.call_tool("validate_manifest", {"manifest": SAMPLE_MANIFEST})

    print("📄 Validation Result:")
    for content in result.content:
        if hasattr(content, "text"):
            print(f"  {content.text}")

    print("\n📚 Getting connector builder documentation...")
    docs_result = await session.call_tool("get_connector_builder_docs", {})

    print("📖 Documentation Overview:")
    for content in docs_result.content:
        if hasattr(content, "text"):
            text = content.text[:200] + "..." if len(content.text) > 200 else content.text
            print(f"  {text}")


async def demo_llm_integration():
    """Demonstrate LLM integration with mcp-use (requires OpenAI API key)."""
    print("\n🤖 Demo 2: LLM Integration")
    print("=" * 50)

    client = MCPClient.from_dict(MCP_CONFIG)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = MCPAgent(client=client, llm=llm)

    query = (
        """
    Please validate this connector manifest and provide feedback on its structure:

    """
        + SAMPLE_MANIFEST
    )

    print("💭 Asking LLM to validate and analyze the manifest...")
    result = await agent.run(query)

    print("🤖 LLM Analysis:")
    print(f"  {result}")


async def demo_multi_tool_workflow():
    """Demonstrate a multi-step connector development workflow."""
    print("\n⚙️  Demo 3: Multi-Tool Workflow")
    print("=" * 50)

    client = MCPClient.from_dict(MCP_CONFIG)

    session = await client.create_session("connector-builder")

    print("1️⃣  Validating manifest...")
    await session.call_tool("validate_manifest", {"manifest": SAMPLE_MANIFEST})
    print("   ✅ Manifest validation complete")

    print("\n2️⃣  Getting development checklist...")
    await session.call_tool("get_connector_builder_checklist", {})
    print("   📋 Development checklist retrieved")

    print("\n3️⃣  Getting manifest JSON schema...")
    await session.call_tool("get_manifest_yaml_json_schema", {})
    print("   📄 JSON schema retrieved")

    print("\n🎉 Multi-tool workflow completed successfully!")
    print("   This demonstrates how mcp-use can orchestrate multiple")
    print("   connector-builder-mcp tools in a single workflow.")


async def main():
    """Run all demo scenarios."""
    print("🚀 mcp-use + connector-builder-mcp Integration Demo")
    print("=" * 60)
    print()
    print("This demo shows how mcp-use can wrap connector-builder-mcp")
    print("to provide vendor-neutral access to Airbyte connector development tools.")
    print()

    await demo_direct_tool_calls()
    await demo_llm_integration()
    await demo_multi_tool_workflow()

    print("\n" + "=" * 60)
    print("✨ Demo completed!")
    print()
    print("Key takeaways:")
    print("• mcp-use provides vendor-neutral access to MCP servers")
    print("• Works with any LangChain-supported LLM")
    print("• Supports both direct tool calls and AI agent workflows")
    print("• Perfect for building custom connector development tools")


if __name__ == "__main__":
    asyncio.run(main())
