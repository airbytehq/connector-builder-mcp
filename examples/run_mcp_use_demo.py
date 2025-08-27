# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Demo script showing how to use different agent frameworks with connector-builder-mcp.

This script demonstrates:
1. Connecting to connector-builder-mcp via STDIO transport
2. Discovering available MCP tools
3. Running connector validation workflows
4. Using different agent frameworks (mcp-use, openai-agents) with MCP

Usage:
    uv run --project=examples examples/run_mcp_use_demo.py "Build a connector for Rick and Morty"
    uv run --project=examples examples/run_mcp_use_demo.py --framework openai "Build a connector"
    poe run_mcp_prompt --prompt "Your prompt string here"

Requirements:
    - connector-builder-mcp server available in PATH
    - Optional: OpenAI API key for LLM integration demo
    - For openai-agents: openai-agents-mcp package
"""

import argparse
import asyncio
import importlib
from pathlib import Path

from dotenv import load_dotenv

FRAMEWORK_MCP_USE = "mcp-use"
FRAMEWORK_OPENAI_AGENTS = "openai-agents"
FRAMEWORK_OPENAI = "openai"  # shorthand


def import_framework_dependencies(framework: str):
    if framework in [FRAMEWORK_MCP_USE]:
        from langchain_openai import ChatOpenAI
        from mcp_use import MCPAgent, MCPClient, set_debug

        return ChatOpenAI, MCPAgent, MCPClient, set_debug
    elif framework in [FRAMEWORK_OPENAI_AGENTS, FRAMEWORK_OPENAI]:
        try:
            from openai_agents_mcp import Agent, Runner, RunnerContext

            return None, Agent, Runner, RunnerContext
        except ImportError as e:
            raise ImportError(
                "openai-agents-mcp is required for openai-agents framework. Install with: uv add openai-agents-mcp"
            ) from e
    else:
        raise ValueError(f"Unsupported framework: {framework}")


# Initialize mcp-use for backward compatibility
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


async def demo_manifest_validation():
    """Demonstrate LLM integration with mcp-use."""
    print("\n🤖 Demo 2: LLM Integration")
    print("=" * 50)

    await run_agent_prompt(
        prompt="Please validate this connector manifest and provide feedback on its structure:"
        + SAMPLE_MANIFEST,
        model="gpt-4o-mini",
        temperature=0.0,
    )
async def run_connector_build(
    api_name: str | None = None,
    instructions: str | None = None,
    framework: str = FRAMEWORK_MCP_USE,
):
    """Demonstrate agent integration with specified framework."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")
    if api_name:
        instructions = (
            f"Fully build and test a connector for '{api_name}'. " + (instructions or "")
        ).strip()
    assert instructions, "By now, instructions should be non-null."

    print(f"\n🤖 Building Connector using AI ({framework})")

    prompt = Path("./prompts/root-prompt.md").read_text(encoding="utf-8") + "\n\n"
    if not HUMAN_IN_THE_LOOP:
        prompt += (
            "Instead of checking in with the user, as your tools suggest, please try to work "
            "autonomously to complete the task."
        )
    prompt += instructions

    await run_agent_prompt(
        prompt=prompt,
        framework=framework,
        model="gpt-4o-mini",
        temperature=0.0,
    )


async def run_agent_prompt(
    prompt: str,
    framework: str = FRAMEWORK_MCP_USE,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
):
    """Execute agent with specified framework."""
    if framework == FRAMEWORK_OPENAI:
        framework = FRAMEWORK_OPENAI_AGENTS

    ChatOpenAI, Agent, Client, extra = import_framework_dependencies(framework)

    if framework == FRAMEWORK_MCP_USE:
        set_debug = extra
        set_debug(1)  # 2=DEBUG level, 1=INFO level

        client = Client.from_dict(MCP_CONFIG)
        if ChatOpenAI is None:
            raise RuntimeError("ChatOpenAI should not be None for mcp-use framework")
        llm = ChatOpenAI(model=model, temperature=temperature)
        agent = Agent(
            client=client,
            llm=llm,
            max_steps=MAX_CONNECTOR_BUILD_STEPS,
            memory_enabled=True,
            retry_on_error=True,
            max_retries_per_step=2,
        )

        print("\n===== Interactive MCP Chat (mcp-use) =====")
        print("Type 'exit' or 'quit' to end the conversation")
        print("Type 'clear' to clear conversation history")
        print("==================================\n")

        try:
            response = await agent.run(prompt)
            print(response)

            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in {"exit", "quit"}:
                    print("Ending conversation...")
                    break

                print("\nAssistant: ", end="", flush=True)
                try:
                    response = await agent.run(user_input)
                    print(response)
                except Exception as e:
                    print(f"\nError: {e}")

        except KeyboardInterrupt:
            print("Conversation terminated (ctrl+c input received).")
        finally:
            if client and client.sessions:
                await client.close_all_sessions()

    elif framework == FRAMEWORK_OPENAI_AGENTS:
        Runner, RunnerContext = Client, extra

        agent = Agent(
            mcp_servers=["connector-builder", "playwright", "filesystem-rw"],
            model=model,
            temperature=temperature,
        )

        print("\n===== Interactive MCP Chat (openai-agents) =====")
        print("Type 'exit' or 'quit' to end the conversation")
        print("==================================\n")

        try:
            context = RunnerContext()
            response = await Runner.run(agent, input=prompt, context=context)
            print(response)

            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in {"exit", "quit"}:
                    print("Ending conversation...")
                    break

                print("\nAssistant: ", end="", flush=True)
                try:
                    response = await Runner.run(agent, input=user_input, context=context)
                    print(response)
                except Exception as e:
                    print(f"\nError: {e}")

        except KeyboardInterrupt:
            print("Conversation terminated (ctrl+c input received).")
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
    parser.add_argument(
        "--framework",
        choices=[FRAMEWORK_MCP_USE, FRAMEWORK_OPENAI_AGENTS, FRAMEWORK_OPENAI],
        default=FRAMEWORK_MCP_USE,
        help="Framework to use for MCP integration (default: mcp-use, 'openai' is shorthand for 'openai-agents')",
    )
    return parser.parse_args()


async def main():
    """Run all demo scenarios."""
    print("🚀 Multi-Framework MCP + connector-builder-mcp Integration Demo")
    print("=" * 60)
    print()
    print("This demo shows how different agent frameworks can wrap connector-builder-mcp")
    print("to provide vendor-neutral access to Airbyte connector development tools.")
    print()

    cli_args: argparse.Namespace = _parse_args()
    
    print(f"Using framework: {cli_args.framework}")

    # await demo_direct_tool_calls()
    # await demo_manifest_validation()
    # await demo_multi_tool_workflow()
    await run_connector_build(instructions=cli_args.prompt, framework=cli_args.framework)

    print("\n" + "=" * 60)
    print("✨ Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())
