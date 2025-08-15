#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#     "upsonic>=0.1.0",
#     "fastmcp>=0.1.0",
#     "pydantic>=2.0.0",
#     "httpx>=0.25.0"
# ]
# ///

"""
Upsonic MCP Connector Builder Example

This script demonstrates how to use the Upsonic AI agent framework to wrap
the connector-builder-mcp and pyairbyte-mcp servers for automated connector building.

Usage:
    uv run examples/upsonic_example.py

Requirements:
    - connector-builder-mcp server running
    - pyairbyte-mcp server running
    - API credentials for the target source
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional

try:
    from upsonic import Agent, MCPServer
    from upsonic.tools import ToolRegistry
except ImportError:
    print("Upsonic not available. This is a demonstration script.")
    print("Install with: pip install upsonic")
    exit(1)


class ConnectorBuilderAgent:
    """
    Upsonic-based agent for automated connector building using MCP servers.
    """
    
    def __init__(self):
        self.agent = Agent(
            name="connector-builder",
            description="AI agent for building Airbyte connectors using MCP tools"
        )
        self.setup_mcp_servers()
    
    def setup_mcp_servers(self):
        """Configure MCP servers for connector building tools."""
        self.agent.add_mcp_server(
            name="connector-builder",
            server_path="connector-builder-mcp",
            description="Tools for validating and testing connector manifests"
        )
        
        self.agent.add_mcp_server(
            name="pyairbyte",
            server_path="pyairbyte-mcp", 
            description="Tools for connector discovery and local operations"
        )
    
    async def build_connector(
        self, 
        api_name: str, 
        credentials: Dict[str, Any],
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a connector using the Upsonic agent with MCP tools.
        
        Args:
            api_name: Name of the API to build connector for (e.g., "stripe")
            credentials: API credentials dictionary
            base_url: Optional base URL for the API
            
        Returns:
            Dictionary containing the built connector manifest and test results
        """
        
        similar_connectors = await self.agent.call_mcp_tool(
            server="pyairbyte",
            tool="list_connectors",
            args={"keyword": api_name, "connector_type": "source"}
        )
        
        checklist = await self.agent.call_mcp_tool(
            server="connector-builder",
            tool="get_connector_builder_checklist",
            args={}
        )
        
        manifest_prompt = f"""
        Create a declarative connector manifest for {api_name} API.
        
        Reference similar connectors: {similar_connectors}
        Follow this checklist: {checklist}
        
        Use these credentials: {credentials}
        Base URL: {base_url or f"https://api.{api_name.lower()}.com"}
        
        Generate a complete YAML manifest following Airbyte connector standards.
        """
        
        initial_manifest = await self.agent.generate_response(manifest_prompt)
        
        validation_result = await self.agent.call_mcp_tool(
            server="connector-builder",
            tool="validate_manifest",
            args={"manifest_content": initial_manifest}
        )
        
        if validation_result.get("valid", False):
            test_result = await self.agent.call_mcp_tool(
                server="connector-builder",
                tool="execute_stream_test_read",
                args={
                    "manifest_content": initial_manifest,
                    "config": credentials
                }
            )
        else:
            test_result = {"error": "Manifest validation failed"}
        
        return {
            "api_name": api_name,
            "manifest": initial_manifest,
            "validation": validation_result,
            "test_results": test_result,
            "similar_connectors": similar_connectors
        }
    
    async def iterative_improvement(
        self, 
        manifest: str, 
        test_results: Dict[str, Any]
    ) -> str:
        """
        Iteratively improve the connector manifest based on test results.
        """
        if test_results.get("error"):
            improvement_prompt = f"""
            The connector manifest has errors: {test_results['error']}
            
            Current manifest: {manifest}
            
            Fix the issues and return an improved manifest.
            """
            
            improved_manifest = await self.agent.generate_response(improvement_prompt)
            return improved_manifest
        
        return manifest


async def main():
    """
    Example usage of the Upsonic connector builder agent.
    """
    print("🚀 Starting Upsonic Connector Builder Agent Example")
    
    agent = ConnectorBuilderAgent()
    
    example_credentials = {
        "api_key": os.getenv("STRIPE_API_KEY", "sk_test_example"),
        "start_date": "2024-01-01T00:00:00Z"
    }
    
    try:
        print("🔨 Building connector for Stripe API...")
        result = await agent.build_connector(
            api_name="stripe",
            credentials=example_credentials,
            base_url="https://api.stripe.com"
        )
        
        print("✅ Connector building completed!")
        print(f"📋 Validation: {'✅ Passed' if result['validation'].get('valid') else '❌ Failed'}")
        print(f"🧪 Tests: {'✅ Passed' if not result['test_results'].get('error') else '❌ Failed'}")
        
        output_file = f"connector_{result['api_name']}_result.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"💾 Results saved to {output_file}")
        
    except Exception as e:
        print(f"❌ Error building connector: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
