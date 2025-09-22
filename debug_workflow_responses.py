#!/usr/bin/env python3
"""Debug script to test model extraction and cost calculation with different response structures."""

import logging
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from connector_builder_agents.src.cost_tracking import CostTracker


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_openai_response_structure():
    """Test with OpenAI-style response structure."""

    class MockUsage:
        def __init__(self):
            self.completion_tokens = 10
            self.prompt_tokens = 50
            self.total_tokens = 60

    class MockResponse:
        def __init__(self):
            self.model = "gpt-4o-mini-2024-07-18"
            self.usage = MockUsage()

    class MockRunResult:
        def __init__(self):
            self.raw_responses = [MockResponse()]

    cost_tracker = CostTracker(trace_id="test-openai")
    run_result = MockRunResult()

    print("=== Testing OpenAI Response Structure ===")
    try:
        cost = cost_tracker.add_run_result(run_result)
        print(f"✅ OpenAI response test passed. Cost: ${cost:.6f}")
        summary = cost_tracker.get_summary()
        print(f"Models used: {summary['models_used']}")
        print(f"Total cost: ${summary['total_estimated_cost']:.6f}")
    except Exception as e:
        print(f"❌ OpenAI response test failed: {e}")
        import traceback

        traceback.print_exc()


def test_expected_response_structure():
    """Test with expected response structure."""

    class MockUsage:
        def __init__(self):
            self.input_tokens = 50
            self.output_tokens = 10
            self.total_tokens = 60
            self.requests = 1

    class MockResponse:
        def __init__(self):
            self.model = "gpt-4o-mini"
            self.usage = MockUsage()

    class MockRunResult:
        def __init__(self):
            self.raw_responses = [MockResponse()]

    cost_tracker = CostTracker(trace_id="test-expected")
    run_result = MockRunResult()

    print("\n=== Testing Expected Response Structure ===")
    try:
        cost = cost_tracker.add_run_result(run_result)
        print(f"✅ Expected response test passed. Cost: ${cost:.6f}")
        summary = cost_tracker.get_summary()
        print(f"Models used: {summary['models_used']}")
        print(f"Total cost: ${summary['total_estimated_cost']:.6f}")
    except Exception as e:
        print(f"❌ Expected response test failed: {e}")
        import traceback

        traceback.print_exc()


def test_missing_attributes():
    """Test with response missing some attributes."""

    class MockUsage:
        def __init__(self):
            self.completion_tokens = 10

    class MockResponse:
        def __init__(self):
            self.model = "gpt-4o-mini"
            self.usage = MockUsage()

    class MockRunResult:
        def __init__(self):
            self.raw_responses = [MockResponse()]

    cost_tracker = CostTracker(trace_id="test-missing")
    run_result = MockRunResult()

    print("\n=== Testing Missing Attributes ===")
    try:
        cost = cost_tracker.add_run_result(run_result)
        print(f"✅ Missing attributes test passed. Cost: ${cost:.6f}")
        summary = cost_tracker.get_summary()
        print(f"Models used: {summary['models_used']}")
        print(f"Total cost: ${summary['total_estimated_cost']:.6f}")
    except Exception as e:
        print(f"❌ Missing attributes test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_openai_response_structure()
    test_expected_response_structure()
    test_missing_attributes()
