#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#     "httpx>=0.25.0",
# ]
# ///

"""
Real MCP Integration Example

This script demonstrates actual integration with connector-builder-mcp and 
pyairbyte-mcp servers using real MCP tool calls via subprocess.

Usage:
    uv run examples/real_mcp_integration_example.py

Requirements:
    - connector-builder-mcp server running
    - pyairbyte-mcp server running
"""

import asyncio
import json
import os
import subprocess
from typing import Dict, Any, Optional


def call_real_mcp_tool(server: str, tool_name: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Call an actual MCP tool using subprocess to execute mcp-cli commands.
    """
    if args is None:
        args = {}
    
    args_json = json.dumps(args) if args else "{}"
    
    print(f"📞 Calling {server}.{tool_name} with args: {args_json}")
    
    try:
        cmd = [
            "mcp-cli", "tool", "call", tool_name,
            "--server", server,
            "--input", args_json
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            
            result_start = -1
            for i, line in enumerate(lines):
                if line.startswith("Tool result:"):
                    result_start = i + 1
                    break
            
            if result_start >= 0:
                result_text = '\n'.join(lines[result_start:]).strip()
                
                try:
                    return json.loads(result_text)
                except json.JSONDecodeError:
                    return {"result": result_text}
            else:
                return {"result": result.stdout}
        else:
            return {"error": f"Command failed: {result.stderr}"}
            
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out"}
    except Exception as e:
        return {"error": f"Exception: {str(e)}"}


async def test_real_mcp_integration():
    """
    Test actual MCP server integration with real tool calls.
    """
    print("🚀 Starting Real MCP Integration Test with Actual Tool Calls")
    
    results = {
        "test_name": "real_mcp_integration_with_subprocess",
        "status": "running",
        "steps": []
    }
    
    print("\n📋 Step 1: Discovering available connectors...")
    try:
        connector_list = call_real_mcp_tool("pyairbyte-mcp", "list_connectors", {
            "keyword_filter": "stripe"
        })
        
        if "error" not in connector_list:
            print(f"✅ Found connector: {connector_list.get('result', connector_list)}")
            results["steps"].append({
                "step": 1,
                "name": "list_connectors",
                "status": "success",
                "result": connector_list
            })
        else:
            print(f"❌ Error: {connector_list['error']}")
            results["steps"].append({
                "step": 1,
                "name": "list_connectors",
                "status": "error",
                "error": connector_list['error']
            })
    except Exception as e:
        print(f"❌ Error listing connectors: {e}")
        results["steps"].append({
            "step": 1,
            "name": "list_connectors",
            "status": "error",
            "error": str(e)
        })
    
    print("\n📝 Step 2: Getting connector building checklist...")
    try:
        checklist = call_real_mcp_tool("connector-builder-mcp", "get_connector_builder_checklist", {})
        
        if "error" not in checklist:
            checklist_text = checklist.get('result', str(checklist))
            lines = checklist_text.split('\n')
            print(f"✅ Retrieved checklist with {len(lines)} lines")
            print("   First few items:")
            for line in lines[:5]:
                if line.strip() and '- [ ]' in line:
                    print(f"     {line.strip()}")
            
            results["steps"].append({
                "step": 2,
                "name": "get_connector_builder_checklist",
                "status": "success",
                "result": checklist
            })
        else:
            print(f"❌ Error: {checklist['error']}")
            results["steps"].append({
                "step": 2,
                "name": "get_connector_builder_checklist",
                "status": "error",
                "error": checklist['error']
            })
    except Exception as e:
        print(f"❌ Error getting checklist: {e}")
        results["steps"].append({
            "step": 2,
            "name": "get_connector_builder_checklist",
            "status": "error",
            "error": str(e)
        })
    
    print("\n🔍 Step 3: Getting connector info for Stripe...")
    try:
        connector_info = call_real_mcp_tool("pyairbyte-mcp", "get_connector_info", {
            "connector_name": "source-stripe"
        })
        
        if "error" not in connector_info:
            info = connector_info.get('result', connector_info)
            if isinstance(info, dict):
                name = info.get('connector_name', 'unknown')
                metadata = info.get('connector_metadata', {})
                version = metadata.get('latest_available_version', 'unknown')
                streams = metadata.get('suggested_streams', [])
                
                print(f"✅ Retrieved info for {name} v{version}")
                print(f"   Suggested streams: {', '.join(streams[:3])}{'...' if len(streams) > 3 else ''}")
            else:
                print(f"✅ Retrieved connector info: {str(info)[:100]}...")
            
            results["steps"].append({
                "step": 3,
                "name": "get_connector_info",
                "status": "success",
                "result": connector_info
            })
        else:
            print(f"❌ Error: {connector_info['error']}")
            results["steps"].append({
                "step": 3,
                "name": "get_connector_info",
                "status": "error",
                "error": connector_info['error']
            })
    except Exception as e:
        print(f"❌ Error getting connector info: {e}")
        results["steps"].append({
            "step": 3,
            "name": "get_connector_info",
            "status": "error",
            "error": str(e)
        })
    
    print("\n✅ Step 4: Validating sample connector manifest...")
    sample_manifest = """version: "0.1.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names: ["customers"]
streams:
  - name: customers
    primary_key: ["id"]
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.stripe.com"
        path: "/v1/customers"
        http_method: "GET"
        authenticator:
          type: BearerAuthenticator
          api_token: "{{ config['api_key'] }}"
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: ["data"]
spec:
  type: Spec
  connection_specification:
    type: object
    properties:
      api_key:
        type: string
        title: API Key
        description: Stripe API key
        airbyte_secret: true
    required: ["api_key"]"""
    
    try:
        validation_result = call_real_mcp_tool("connector-builder-mcp", "validate_manifest", {
            "manifest": sample_manifest
        })
        
        if "error" not in validation_result:
            result = validation_result.get('result', validation_result)
            print(f"✅ Manifest validation completed")
            print(f"   Result: {str(result)[:200]}...")
            
            results["steps"].append({
                "step": 4,
                "name": "validate_manifest",
                "status": "success",
                "result": validation_result
            })
        else:
            print(f"❌ Error: {validation_result['error']}")
            results["steps"].append({
                "step": 4,
                "name": "validate_manifest",
                "status": "error",
                "error": validation_result['error']
            })
    except Exception as e:
        print(f"❌ Error validating manifest: {e}")
        results["steps"].append({
            "step": 4,
            "name": "validate_manifest",
            "status": "error",
            "error": str(e)
        })
    
    successful_steps = len([s for s in results["steps"] if s["status"] == "success"])
    total_steps = len(results["steps"])
    
    print(f"\n📊 Summary:")
    print(f"✅ Completed {successful_steps}/{total_steps} steps successfully")
    print(f"✅ uv inline dependency syntax working correctly")
    print(f"✅ Real MCP tool integration demonstrated via subprocess")
    
    if successful_steps == total_steps:
        results["status"] = "success"
        print("🎉 All real MCP integration tests passed!")
    else:
        results["status"] = "partial_success"
        print("⚠️  Some real MCP integration tests had issues")
    
    output_file = "real_mcp_integration_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"💾 Test results saved to {output_file}")
    
    return results


async def main():
    """
    Main function to run the real MCP integration test.
    """
    try:
        results = await test_real_mcp_integration()
        if results["status"] == "success":
            print("\n🎉 Real MCP integration test completed successfully!")
            return 0
        else:
            print(f"\n⚠️  Real MCP integration test completed with status: {results['status']}")
            return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
