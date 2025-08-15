#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#     "pyautogen>=0.2.0",
#     "fastmcp>=0.1.0",
#     "pydantic>=2.0.0",
#     "httpx>=0.25.0",
#     "openai>=1.0.0"
# ]
# ///

"""
AutoGen MCP Connector Builder Example

This script demonstrates how to use the Microsoft AutoGen multi-agent framework
to wrap the connector-builder-mcp and pyairbyte-mcp servers for automated connector building.

Usage:
    uv run examples/autogen_example.py

Requirements:
    - connector-builder-mcp server running
    - pyairbyte-mcp server running
    - OpenAI API key for LLM interactions
    - API credentials for the target source
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional, List

try:
    import autogen
    from autogen import ConversableAgent, GroupChat, GroupChatManager
    from autogen.agentchat.contrib.mcp_agent import MCPAgent
except ImportError:
    print("AutoGen not available. This is a demonstration script.")
    print("Install with: pip install pyautogen")
    exit(1)


class AutoGenConnectorBuilder:
    """
    AutoGen-based multi-agent system for automated connector building using MCP servers.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key required for AutoGen agents")
        
        self.llm_config = {
            "model": "gpt-4",
            "api_key": self.openai_api_key,
            "temperature": 0.1
        }
        
        self.setup_agents()
    
    def setup_agents(self):
        """Initialize the multi-agent system with specialized roles."""
        
        self.planner_agent = ConversableAgent(
            name="planner",
            system_message="""You are a connector planning specialist. Your role is to:
            1. Analyze the target API and requirements
            2. Find similar existing connectors for reference
            3. Create a detailed build strategy
            4. Use MCP tools to gather necessary information
            
            Always start by using the connector registry to find similar connectors.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER"
        )
        
        self.builder_agent = ConversableAgent(
            name="builder", 
            system_message="""You are a connector manifest builder. Your role is to:
            1. Create declarative YAML connector manifests
            2. Follow Airbyte connector building best practices
            3. Use the connector builder checklist as guidance
            4. Iterate on manifests based on validation feedback
            
            Always validate manifests before proceeding to testing.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER"
        )
        
        self.validator_agent = ConversableAgent(
            name="validator",
            system_message="""You are a connector validation specialist. Your role is to:
            1. Validate connector manifests for syntax and completeness
            2. Execute stream tests and smoke tests
            3. Analyze test results and provide improvement feedback
            4. Ensure connectors meet quality standards
            
            Always run comprehensive tests before declaring success.""",
            llm_config=self.llm_config,
            human_input_mode="NEVER"
        )
        
        self.mcp_agent = MCPAgent(
            name="mcp_coordinator",
            system_message="""You coordinate MCP server interactions. Your role is to:
            1. Execute MCP tool calls for connector building operations
            2. Manage communication between agents and MCP servers
            3. Handle error recovery for MCP operations
            4. Provide MCP tool results to other agents""",
            llm_config=self.llm_config,
            mcp_servers=[
                {
                    "name": "connector-builder",
                    "server_path": "connector-builder-mcp"
                },
                {
                    "name": "pyairbyte", 
                    "server_path": "pyairbyte-mcp"
                }
            ]
        )
        
        self.agents = [
            self.planner_agent,
            self.builder_agent, 
            self.validator_agent,
            self.mcp_agent
        ]
        
        self.group_chat = GroupChat(
            agents=self.agents,
            messages=[],
            max_round=20,
            speaker_selection_method="round_robin"
        )
        
        self.manager = GroupChatManager(
            groupchat=self.group_chat,
            llm_config=self.llm_config
        )
    
    async def build_connector(
        self,
        api_name: str,
        credentials: Dict[str, Any],
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a connector using the AutoGen multi-agent system.
        
        Args:
            api_name: Name of the API to build connector for
            credentials: API credentials dictionary
            base_url: Optional base URL for the API
            
        Returns:
            Dictionary containing the built connector and results
        """
        
        task_message = f"""
        Build an Airbyte connector for the {api_name} API.
        
        Requirements:
        - API Name: {api_name}
        - Base URL: {base_url or f"https://api.{api_name.lower()}.com"}
        - Credentials: {json.dumps(credentials, indent=2)}
        
        Process:
        1. Planner: Research similar connectors and create build strategy
        2. Builder: Create initial manifest following the strategy
        3. Validator: Test and validate the manifest
        4. Iterate until successful or max rounds reached
        
        Use MCP tools throughout the process for:
        - Finding similar connectors (pyairbyte server)
        - Getting building guidance (connector-builder server)
        - Validating manifests (connector-builder server)
        - Testing streams (connector-builder server)
        """
        
        chat_result = await self.manager.a_initiate_chat(
            self.planner_agent,
            message=task_message
        )
        
        return self.extract_results(chat_result, api_name)
    
    def extract_results(self, chat_result: Any, api_name: str) -> Dict[str, Any]:
        """Extract and structure results from the multi-agent conversation."""
        
        messages = chat_result.chat_history if hasattr(chat_result, 'chat_history') else []
        
        manifest_content = None
        validation_results = None
        test_results = None
        
        for message in messages:
            content = message.get('content', '')
            
            if 'version:' in content and 'streams:' in content:
                manifest_content = content
            
            if 'validation' in content.lower() and ('passed' in content.lower() or 'failed' in content.lower()):
                validation_results = content
            
            if 'test' in content.lower() and ('success' in content.lower() or 'error' in content.lower()):
                test_results = content
        
        return {
            "api_name": api_name,
            "manifest": manifest_content,
            "validation_results": validation_results,
            "test_results": test_results,
            "conversation_history": messages,
            "success": manifest_content is not None and validation_results is not None
        }


async def main():
    """
    Example usage of the AutoGen connector builder system.
    """
    print("🚀 Starting AutoGen Multi-Agent Connector Builder Example")
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable required")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return 1
    
    try:
        print("🤖 Initializing AutoGen multi-agent system...")
        builder = AutoGenConnectorBuilder()
        
        example_credentials = {
            "api_key": os.getenv("STRIPE_API_KEY", "sk_test_example"),
            "start_date": "2024-01-01T00:00:00Z"
        }
        
        print("🔨 Building connector for Stripe API using multi-agent collaboration...")
        result = await builder.build_connector(
            api_name="stripe",
            credentials=example_credentials,
            base_url="https://api.stripe.com"
        )
        
        print("✅ Multi-agent connector building completed!")
        print(f"📋 Success: {'✅ Yes' if result['success'] else '❌ No'}")
        print(f"📝 Manifest Generated: {'✅ Yes' if result['manifest'] else '❌ No'}")
        print(f"🧪 Validation: {'✅ Completed' if result['validation_results'] else '❌ Missing'}")
        print(f"🔍 Tests: {'✅ Completed' if result['test_results'] else '❌ Missing'}")
        
        output_file = f"autogen_connector_{result['api_name']}_result.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"💾 Results saved to {output_file}")
        
        conversation_file = f"autogen_conversation_{result['api_name']}.json"
        with open(conversation_file, 'w') as f:
            json.dump(result['conversation_history'], f, indent=2, default=str)
        print(f"💬 Conversation history saved to {conversation_file}")
        
    except Exception as e:
        print(f"❌ Error in multi-agent connector building: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
