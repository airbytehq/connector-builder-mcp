# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Demo script showing how to use mcp-use as a wrapper for connector-builder-mcp.

This script demonstrates:
1. Connecting to connector-builder-mcp via STDIO transport
2. Discovering available MCP tools
3. Running connector validation workflows
4. Using different LLM providers with mcp-use

Usage:
    uv run --project=examples examples/run_mcp_use_demo.py "Build a connector for Rick and Morty"
    poe run_mcp_prompt --prompt "Your prompt string here"

Requirements:
    - connector-builder-mcp server available in PATH
    - Optional: OpenAI API key for LLM integration demo
"""

import argparse
import asyncio
import importlib
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient, set_debug


set_debug(1)  # 2=DEBUG level, 1=INFO level


# Print loaded versions of mcp-use and langchain
def print_library_versions():
    print("Loaded library versions:")
    try:
        mcp_use = importlib.import_module("mcp_use")
        print(f"  mcp-use: {getattr(mcp_use, '__version__', 'unknown')}")
    except Exception as e:
        print(f"  mcp-use: not found ({e})")
    try:
        langchain = importlib.import_module("langchain")
        print(f"  langchain: {getattr(langchain, '__version__', 'unknown')}")
    except Exception as e:
        print(f"  langchain: not found ({e})")


print_library_versions()

# Initialize env vars:
load_dotenv()


DEFAULT_CONNECTOR_BUILD_API_NAME: str = "Rick and Morty API"
HUMAN_IN_THE_LOOP: bool = True  # Set to True to enable human-in-the-loop mode

# Setup MCP Config:
MCP_CONFIG = {
    "mcpServers": {
        "connector-builder": {
            "command": "uv",
            "args": [
                "run",
                "connector-builder-mcp",
            ],
            "env": {},
        },
        "playwright": {
            "command": "npx",
            "args": [
                "@playwright/mcp@latest",
            ],
            "env": {
                # "DISPLAY": ":1",
                "PLAYWRIGHT_HEADLESS": "true",
                "BLOCK_PRIVATE_IPS": "true",
                "DISABLE_JAVASCRIPT": "false",
                "TIMEOUT": "30000",
            },
        },
        "filesystem-rw": {
            "command": "npx",
            "args": [
                "mcp-server-filesystem",
                str(Path() / "ai-generated-files"),
                # TODO: Research if something like this is supported:
                # "--allowed-extensions",
                # ".txt,.md,.json,.py",
            ],
        },
    }
}
MAX_CONNECTOR_BUILD_STEPS = 100
client = MCPClient.from_dict(MCP_CONFIG)

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
    session = await client.create_session("connector-builder")
    print("🔧 Demo 1: Direct Tool Calls")
    print("=" * 50)

    print("📋 Available MCP Tools:")
    tools = await session.list_tools()
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


async def run_connector_build(
    api_name: str | None = None,
    instructions: str | None = None,
):
    """Demonstrate LLM integration with mcp-use."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")
    if api_name:
        instructions = (
            f"Fully build and test a connector for '{api_name}'. " + (instructions or "")
        ).strip()
    assert instructions, "By now, instructions should be non-null."

    print("\n🤖 Building Connector using AI")

    prompt = Path("./prompts/root-prompt.md").read_text(encoding="utf-8") + "\n\n"
    if not HUMAN_IN_THE_LOOP:
        prompt += (
            "Instead of checking in with the user, as your tools suggest, please try to work "
            "autonomously to complete the task."
        )
    prompt += instructions

    await run_mcp_use_prompt(
        prompt=prompt,
        model="gpt-4o-mini",
        temperature=0.0,
    )


async def run_mcp_use_prompt(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
):
    """Execute LLM agent with mcp-use."""
    client = MCPClient.from_dict(MCP_CONFIG)
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
    )
    agent = MCPAgent(
        client=client,
        llm=llm,
        max_steps=MAX_CONNECTOR_BUILD_STEPS,
        memory_enabled=True,
        retry_on_error=True,
        max_retries_per_step=2,
    )
    print("\n===== Interactive MCP Chat =====")
    print("Type 'exit' or 'quit' to end the conversation")
    print("Type 'clear' to clear conversation history")
    print("==================================\n")
    try:
        response = await agent.run(prompt)
        print(response)
        # Main chat loop
        while True:
            # Get user input
            user_input = input("\nYou: ")

            # Check for exit command
            if user_input.lower() in {"exit", "quit"}:
                print("Ending conversation...")
                break

            # Get response from agent
            print("\nAssistant: ", end="", flush=True)

            try:
                # Run the agent with the user input (memory handling is automatic)
                response = await agent.run(user_input)
                print(response)

            except Exception as e:
                print(f"\nError: {e}")
    except KeyboardInterrupt:
        print("Conversation terminated (ctrl+c input received).")

    finally:
        # Clean up
        if client and client.sessions:
            await client.close_all_sessions()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MCP agent with a prompt.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Build a connector for Rick and Morty.",
        help="Prompt string to pass to the agent.",
    )
    return parser.parse_args()


async def main():
    """Run all demo scenarios."""
    print("🚀 mcp-use + connector-builder-mcp Integration Demo")
    print("=" * 60)
    print()
    print("This demo shows how mcp-use can wrap connector-builder-mcp")
    print("to provide vendor-neutral access to Airbyte connector development tools.")
    print()

    cli_args: argparse.Namespace = _parse_args()

    # await demo_direct_tool_calls()
    # await demo_manifest_validation()
    # await demo_multi_tool_workflow()
    await run_connector_build(instructions=cli_args.prompt)

    print("\n" + "=" * 60)
    print("✨ Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())
