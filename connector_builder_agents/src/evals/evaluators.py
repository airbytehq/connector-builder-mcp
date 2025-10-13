# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Unified LLM-based evaluator for connector builder agents."""

import json
import logging

import pandas as pd
from dotenv import load_dotenv
from opentelemetry.trace import get_current_span
from phoenix.evals import OpenAIModel, llm_classify


load_dotenv()

logger = logging.getLogger(__name__)

UNIFIED_EVAL_MODEL = "gpt-4o"

UNIFIED_EVAL_TEMPLATE = """You are evaluating the quality of a generated Airbyte connector.

You will evaluate based on two criteria and return scores for each.

**Artifacts Provided:**
1. **Readiness Report**: Markdown report showing test results for the connector
2. **Manifest**: YAML defining the connector's streams and configuration
3. **Expected Streams**: List of stream names that should be present in the manifest

**Evaluation Criteria:**

Evaluate whether the connector readiness test passed or failed.

A passing report should have all of the following:
- All streams tested successfully (marked with ✅)
- No critical errors or failures
- Records extracted from streams (even if with warnings)
- Successful completion indicated

A failing report could have any of the following:
- Streams marked as failed (❌)
- Critical errors preventing extraction
- Zero records extracted from streams
- Error messages indicating failure

**Score: 1.0 if PASSED, 0.0 if FAILED**

Evaluate what percentage of expected streams are present in the manifest.

Instructions:
- Extract all stream names from the manifest YAML (look for `streams:` section, each with a `name:` field)
- Compare against the expected streams list
- Count only exact name matches (case-sensitive)
- Calculate: (number of expected streams found) / (total expected streams)

Example:
- Expected: ["posts", "users", "comments"]
- Found in manifest: ["posts", "comments", "albums"]
- Matched: ["posts", "comments"]
- Score: 2/3 = 0.67

**Score: float between 0.0 and 1.0**

---

**Input Data:**

Readiness Report:
```
{readiness_report}
```

Manifest:
```
{manifest}
```

Expected Streams: {expected_streams}

---

**Instructions:**
Carefully analyze the artifacts above and classify the readiness as either "PASSED" or "FAILED", and calculate the streams percentage.

Your response must be in this exact format (one word for readiness, one number for streams):
READINESS: <PASSED or FAILED>
STREAMS: <percentage as decimal, e.g., 0.67>
"""


def unified_eval(expected: dict, output: dict) -> dict:
    """Unified LLM-based evaluator for all connector quality criteria.

    Evaluates both readiness (pass/fail) and streams (percentage match) using a single LLM call.

    Args:
        expected: Dict containing expected criteria (e.g., expected_streams list)
        output: Dict containing task output with artifacts (readiness_report, manifest)

    Returns:
        Dict with 'readiness' (0.0 or 1.0) and 'streams' (0.0-1.0) scores
    """
    if output is None:
        logger.warning("Output is None, cannot evaluate")
        return {"readiness": 0.0, "streams": 0.0}

    readiness_report = output.get("artifacts", {}).get("readiness_report", "Not available")
    manifest = output.get("artifacts", {}).get("manifest", "Not available")

    if readiness_report == "Not available":
        logger.warning("No readiness report found")

    if manifest == "Not available":
        logger.warning("No manifest found")

    expected_obj = json.loads(expected.get("expected", "{}"))
    expected_streams = expected_obj.get("expected_streams", [])

    logger.info(f"Expected streams: {expected_streams}")

    # Set attributes on span for visibility
    span = get_current_span()
    span.set_attribute("expected_streams", expected_streams)

    if not expected_streams:
        logger.warning("No expected streams provided")

    prompt = UNIFIED_EVAL_TEMPLATE.format(
        readiness_report=readiness_report,
        manifest=manifest,
        expected_streams=json.dumps(expected_streams),
    )

    try:
        eval_df = llm_classify(
            model=OpenAIModel(model=UNIFIED_EVAL_MODEL),
            data=pd.DataFrame(
                [
                    {
                        "readiness_report": readiness_report,
                        "manifest": manifest,
                        "expected_streams": json.dumps(expected_streams),
                    }
                ]
            ),
            template=prompt,
            rails=None,
            provide_explanation=True,
        )

        logger.info(f"Unified evaluation result: {eval_df}")

        response_text = eval_df["label"][0]

        readiness_score = 0.0
        streams_score = 0.0

        for line in response_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("READINESS:"):
                readiness_value = line.split(":", 1)[1].strip().upper()
                readiness_score = 1.0 if readiness_value == "PASSED" else 0.0
            elif line.startswith("STREAMS:"):
                streams_value = line.split(":", 1)[1].strip()
                try:
                    streams_score = float(streams_value)
                    streams_score = max(0.0, min(1.0, streams_score))
                except ValueError:
                    logger.warning(f"Could not parse streams score from: {streams_value}")
                    streams_score = 0.0

        logger.info(f"Parsed readiness score: {readiness_score}")
        logger.info(f"Parsed streams score: {streams_score}")

        span.set_attribute("readiness_score", readiness_score)
        span.set_attribute("streams_score", streams_score)

        return {"readiness": readiness_score, "streams": streams_score}

    except Exception as e:
        logger.error(f"Error during unified evaluation: {e}", exc_info=True)
        return {"readiness": 0.0, "streams": 0.0}
