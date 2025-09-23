# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Evaluators for connector builder agents."""

import pandas as pd
from dotenv import load_dotenv
from phoenix.evals import OpenAIModel, llm_classify


load_dotenv()

EVAL_MODEL = OpenAIModel(model="gpt-4o")


def readiness_eval(input: dict, output: dict) -> int:
    """Create Phoenix LLM classifier for readiness evaluation."""
    EVAL_TEMPLATE = """You are evaluating whether a connector readiness test passed or failed.

A passing report should have:
- All streams tested successfully (marked with ✅)
- No critical errors or failures
- Records extracted from streams (even if with warnings)
- Successful completion indicated

A failing report would have:
- Streams marked as failed (❌)
- Critical errors preventing extraction
- Zero records extracted from streams
- Error messages indicating failure

Based on the connector readiness report below, classify whether the test PASSED or FAILED. Your answer should be a single word, either "PASSED" or "FAILED".

{readiness_report}
"""

    rails = ["PASSED", "FAILED"]

    eval_df = llm_classify(
        model=EVAL_MODEL,
        data=pd.DataFrame([{"readiness_report": output["readiness_report_content"]}]),
        template=EVAL_TEMPLATE,
        rails=rails,
        provide_explanation=True,
    )

    label = eval_df["label"][0]
    score = 1 if label == "PASSED" else 0

    return score
