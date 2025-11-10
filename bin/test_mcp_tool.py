#!/usr/bin/env python3
"""
One-liner CLI tool for testing MCP tools directly with JSON arguments.

Usage:
    poe test-tool <tool_name> '<json_args>'
    poe test-tool execute_stream_test_read '{"manifest": "@simple_api_manifest", "config": {}, "stream_name": "users", "max_records": 3}'
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from fastmcp import Client

from connector_builder_mcp.server import app


async def call_mcp_tool(tool_name: str, args: dict[str, Any]) -> Any:
    """Call an MCP tool using the FastMCP client."""

    async with Client(app) as client:
        result = await client.call_tool(tool_name, args)
        return result


def main() -> None:
    """Main entry point for the MCP tool tester."""
    if len(sys.argv) < 3:
        print("Usage: python test_mcp_tool.py <tool_name> '<json_args>'", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print(
            '  poe test-tool execute_stream_test_read \'{"manifest": "@simple_api_manifest", "config": {}, "stream_name": "users", "max_records": 3}\'',
            file=sys.stderr,
        )
        print(
            '  poe test-tool run_connector_readiness_test_report \'{"manifest": "@simple_api_manifest", "config": {}, "max_records": 10}\'',
            file=sys.stderr,
        )
        print(
            '  poe test-tool validate_manifest \'{"manifest": "@simple_api_manifest"}\'',
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        print("Sample manifests (use @sample_name in manifest field):", file=sys.stderr)
        print("  - @rick_and_morty_manifest", file=sys.stderr)
        print("  - @simple_api_manifest", file=sys.stderr)
        sys.exit(1)

    tool_name = sys.argv[1]
    json_args = sys.argv[2]

    try:
        args: dict[str, Any] = json.loads(json_args)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON arguments: {e}", file=sys.stderr)
        sys.exit(1)

    if (
        "manifest" in args
        and isinstance(args["manifest"], str)
        and args["manifest"].startswith("@")
    ):
        sample_name = args["manifest"][1:]
        try:
            manifest_path = (
                Path(__file__).parent.parent / "tests" / "resources" / f"{sample_name}.yaml"
            )
            if manifest_path.exists():
                args["manifest"] = str(manifest_path)
            else:
                raise FileNotFoundError(f"Sample manifest not found: {manifest_path}")
        except FileNotFoundError as e:
            print(f"Error loading sample manifest: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        result = asyncio.run(call_mcp_tool(tool_name, args))

        if hasattr(result, "text"):
            print(result.text)
        else:
            print(str(result))

    except Exception as e:
        print(f"Error executing tool '{tool_name}': {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
