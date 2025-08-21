#!/usr/bin/env python3
"""
One-liner CLI tool for testing MCP tools directly with JSON arguments.

Usage:
    poe test-tool execute_stream_test_read '{"manifest": "...", "config": {}, "stream_name": "users", "max_records": 3}'
    poe test-tool run_connector_readiness_test_report '{"manifest": "...", "config": {}, "max_records": 10}'
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

from connector_builder_mcp._validation_testing import (
    execute_stream_test_read,
    run_connector_readiness_test_report,
)


def load_sample_manifest(name: str) -> str:
    """Load a sample manifest from tests/resources."""
    manifest_path = Path(__file__).parent.parent / "tests" / "resources" / f"{name}.yaml"
    if manifest_path.exists():
        return manifest_path.read_text()
    raise FileNotFoundError(f"Sample manifest not found: {manifest_path}")


def main() -> None:
    """Main entry point for the MCP tool tester."""
    if len(sys.argv) < 3:
        print("Usage: python test_mcp_tool.py <tool_name> '<json_args>'", file=sys.stderr)
        print("", file=sys.stderr)
        print("Available tools:", file=sys.stderr)
        print("  - execute_stream_test_read", file=sys.stderr)
        print("  - run_connector_readiness_test_report", file=sys.stderr)
        print("", file=sys.stderr)
        print("Sample manifests (use @sample_name in manifest field):", file=sys.stderr)
        print("  - @rick_and_morty_manifest", file=sys.stderr)
        print("  - @simple_api_manifest", file=sys.stderr)
        print("", file=sys.stderr)
        print("Example:", file=sys.stderr)
        print('  poe test-tool execute_stream_test_read \'{"manifest": "@simple_api_manifest", "config": {}, "stream_name": "users", "max_records": 3}\'', file=sys.stderr)
        sys.exit(1)

    tool_name = sys.argv[1]
    json_args = sys.argv[2]

    try:
        args: Dict[str, Any] = json.loads(json_args)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON arguments: {e}", file=sys.stderr)
        sys.exit(1)

    if "manifest" in args and isinstance(args["manifest"], str) and args["manifest"].startswith("@"):
        sample_name = args["manifest"][1:]
        try:
            manifest_path = Path(__file__).parent.parent / "tests" / "resources" / f"{sample_name}.yaml"
            if manifest_path.exists():
                args["manifest"] = str(manifest_path)
            else:
                raise FileNotFoundError(f"Sample manifest not found: {manifest_path}")
        except FileNotFoundError as e:
            print(f"Error loading sample manifest: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        if tool_name == "execute_stream_test_read":
            result = execute_stream_test_read(**args)
            print(f"Success: {result.success}")
            print(f"Message: {result.message}")
            print(f"Records read: {result.records_read}")
            if result.record_stats:
                print(f"Record stats: {json.dumps(result.record_stats, indent=2)}")
            if result.errors:
                print(f"Errors: {result.errors}")

        elif tool_name == "run_connector_readiness_test_report":
            result = run_connector_readiness_test_report(**args)
            print("Readiness Test Report:")
            print("=" * 60)
            print(result)
            print("=" * 60)

        else:
            print(f"Unknown tool: {tool_name}", file=sys.stderr)
            print("Available tools: execute_stream_test_read, run_connector_readiness_test_report", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error executing tool '{tool_name}': {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
