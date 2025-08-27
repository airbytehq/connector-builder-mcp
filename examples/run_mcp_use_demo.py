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

from agents import Agent as OpenAIAgent
from agents import Runner
from agents.mcp import MCPServerStdio, MCPServerStdioParams
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient, set_debug


FRAMEWORK_MCP_USE = "mcp-use"
FRAMEWORK_OPENAI_AGENTS = "openai-agents"
FRAMEWORK_OPENAI = "openai"  # shorthand


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

    if framework == FRAMEWORK_MCP_USE:
        set_debug(1)  # 2=DEBUG level, 1=INFO level

        client = MCPClient.from_dict(MCP_CONFIG)
        llm = ChatOpenAI(model=model, temperature=temperature)
        agent = MCPAgent(
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
        mcp_servers = [
            MCPServerStdio(
                params=MCPServerStdioParams(
                    command="uv", args=["run", "connector-builder-mcp"], env={}
                )
            ),
            MCPServerStdio(
                params=MCPServerStdioParams(
                    command="npx",
                    args=["@playwright/mcp@latest"],
                    env={
                        "PLAYWRIGHT_HEADLESS": "true",
                        "BLOCK_PRIVATE_IPS": "true",
                        "DISABLE_JAVASCRIPT": "false",
                        "TIMEOUT": "30000",
                    },
                )
            ),
            MCPServerStdio(
                params=MCPServerStdioParams(
                    command="npx", args=["mcp-server-filesystem", "ai-generated-files"], env={}
                )
            ),
        ]

        agent = OpenAIAgent(
            name="MCP Connector Builder",
            instructions="You are a helpful assistant with access to MCP tools for building Airbyte connectors.",
            mcp_servers=mcp_servers,
            model=model,
        )

        print("\n===== Interactive MCP Chat (openai-agents) =====")
        print("Type 'exit' or 'quit' to end the conversation")
        print("==================================\n")

        try:
            for server in mcp_servers:
                await server.connect()

            response = await Runner.run(agent, input=prompt)
            print(response.final_output)

            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in {"exit", "quit"}:
                    print("Ending conversation...")
                    break

                print("\nAssistant: ", end="", flush=True)
                try:
                    response = await Runner.run(agent, input=user_input)
                    print(response.final_output)
                except Exception as e:
                    print(f"\nError: {e}")

        except KeyboardInterrupt:
            print("Conversation terminated (ctrl+c input received).")
        finally:
            for server in mcp_servers:
                try:
                    await server.cleanup()
                except Exception as e:
                    print(f"Warning: Error cleaning up server {server.name}: {e}")


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

    await run_connector_build(instructions=cli_args.prompt, framework=cli_args.framework)

    print("\n" + "=" * 60)
    print("✨ Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())
