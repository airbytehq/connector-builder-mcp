#!/usr/bin/env python3
"""Debug script to test model name extraction from OpenAI API responses."""

import logging
import os

from openai import OpenAI


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_openai_response_structure():
    """Make a simple OpenAI API call and examine the response structure."""

    api_key = os.getenv("OPENAI_APLKEY")
    if not api_key:
        print("ERROR: OPENAI_APLKEY environment variable not set")
        return

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello! Just say 'Hi' back."}],
            max_tokens=10,
        )

        print("=== RESPONSE OBJECT STRUCTURE ===")
        print(f"Response type: {type(response)}")
        print(f"Response attributes: {dir(response)}")
        print()

        print("=== RESPONSE CONTENT ===")
        print(f"Model: {getattr(response, 'model', 'NOT FOUND')}")
        print(f"Usage: {getattr(response, 'usage', 'NOT FOUND')}")
        print()

        if hasattr(response, "usage"):
            usage = response.usage
            print("=== USAGE OBJECT ===")
            print(f"Usage type: {type(usage)}")
            print(f"Usage attributes: {dir(usage)}")
            print(f"Input tokens: {getattr(usage, 'prompt_tokens', 'NOT FOUND')}")
            print(f"Output tokens: {getattr(usage, 'completion_tokens', 'NOT FOUND')}")
            print(f"Total tokens: {getattr(usage, 'total_tokens', 'NOT FOUND')}")
            print()

        print("=== TESTING CURRENT EXTRACTION LOGIC ===")

        def test_extract_model_name(response):
            """Test version of _extract_model_name method."""
            for attr in ["model", "model_name", "engine"]:
                if hasattr(response, attr):
                    model_value = getattr(response, attr)
                    if model_value:
                        print(f"Found model via {attr}: {model_value}")
                        return str(model_value)

            # Try nested raw_response
            if hasattr(response, "raw_response"):
                raw = response.raw_response
                print(f"Raw response type: {type(raw)}")
                print(f"Raw response attributes: {dir(raw)}")
                if hasattr(raw, "model"):
                    model_value = raw.model
                    if model_value:
                        print(f"Found model via raw_response.model: {model_value}")
                        return str(model_value)

            print("Could not extract model name - would return 'unknown-model'")
            return "unknown-model"

        extracted_model = test_extract_model_name(response)
        print(f"Extracted model name: {extracted_model}")

    except Exception as e:
        print(f"ERROR making API call: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_openai_response_structure()
