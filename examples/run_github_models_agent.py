#!/usr/bin/env python3
"""Wrapper script to run the MCP agent with GitHub Models configuration."""

import os
import asyncio
from openai import AsyncOpenAI
from agents import set_default_openai_client

async def main():
    """Configure GitHub Models client and run the agent."""
    client = AsyncOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", os.environ.get("GITHUB_TOKEN")),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://models.github.ai/v1")
    )
    
    set_default_openai_client(client, use_for_tracing=True)
    
    from run_mcp_agent import main as run_agent_main
    await run_agent_main()

if __name__ == "__main__":
    asyncio.run(main())
