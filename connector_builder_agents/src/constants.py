# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Constants for the Airbyte connector builder agents."""

import os
import subprocess
from pathlib import Path

from agents import (
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI


# Initialize env vars:
load_dotenv()

GH_MODELS_OPENAI_BASE_URL: str = "https://models.github.ai/inference"
OPENAI_BASE_URL_ENV_VAR: str = "OPENAI_BASE_URL"
OPENAI_API_KEY_ENV_VAR: str = "OPENAI_API_KEY"
OPENAI_BASE_URL: str = "https://api.openai.com/v1"

PROMPT_FILE_PATH = Path(__file__).parent.parent / "prompts" / "root-prompt.md"
PROMPT_FILE_STR = PROMPT_FILE_PATH.read_text(encoding="utf-8")
MAX_CONNECTOR_BUILD_STEPS = 100
DEFAULT_CONNECTOR_BUILD_API_NAME: str = "JSONPlaceholder API"
DEFAULT_DEVELOPER_MODEL: str = (
    "gpt-5"  # "gpt-4.1"  # "o4-mini", "gpt-4.1-turbo", "openai/gpt-4o-mini", "gpt-4o-mini"
)
DEFAULT_MANAGER_MODEL: str = (
    "gpt-5"  # "gpt-4.1"  # "o4-mini", "gpt-4.1-turbo", "openai/gpt-4o-mini", "gpt-4o-mini"
)
AUTO_OPEN_TRACE_URL: bool = os.environ.get("AUTO_OPEN_TRACE_URL", "1").lower() in {"1", "true"}

HEADLESS_BROWSER = True


def initialize_models() -> None:
    """Initialize LLM models based on environment variables."""
    global OPENAI_BASE_URL

    if OPENAI_BASE_URL_ENV_VAR in os.environ:
        print("⚙️ Detected custom OpenAI API root in environment.")
        OPENAI_BASE_URL = os.environ[OPENAI_BASE_URL_ENV_VAR]
        if "github.ai" in OPENAI_BASE_URL and OPENAI_BASE_URL != GH_MODELS_OPENAI_BASE_URL:
            print(
                f"⚠️ Warning: Detected GitHub Models endpoint but non-standard API root: {OPENAI_BASE_URL}. "
                f"Recommended root URL is: {GH_MODELS_OPENAI_BASE_URL}"
            )

        if OPENAI_BASE_URL.lower() in {"gh", "github", "github models"}:
            print(
                f"Found GitHub Models endpoint alias: {OPENAI_BASE_URL}. "
                f"Applying recommended Github Models URL root: {GH_MODELS_OPENAI_BASE_URL}"
            )
            OPENAI_BASE_URL = GH_MODELS_OPENAI_BASE_URL

        if "github.ai" in OPENAI_BASE_URL and "OPENAI_API_KEY" not in os.environ:
            print(
                "GitHub Models endpoint detected but not API Root is set. "
                "Attempting to extract token using `gh auth token` CLI command."
            )

            _ = subprocess.check_output(["gh", "auth", "status"])
            openai_api_key: str = (
                subprocess.check_output(["gh", "auth", "token"]).decode("utf-8").strip()
            )
            print(
                "✅ Successfully extracted GitHub token from `gh` CLI: "
                f"({openai_api_key[:4]}...{openai_api_key[-4:]})"
            )
            if not openai_api_key.startswith("sk-"):
                raise ValueError(
                    "Extracted GitHub token does not appear to be valid. "
                    "Please ensure you have the GitHub CLI installed and authenticated."
                )
            os.environ["OPENAI_API_KEY"] = openai_api_key

        print(f"ℹ️ Using Custom OpenAI-Compatible LLM Endpoint: {OPENAI_BASE_URL}")
        github_models_client = AsyncOpenAI(
            base_url=OPENAI_BASE_URL,
            api_key=os.environ.get("OPENAI_API_KEY", None),
        )
        set_default_openai_client(
            github_models_client,
            use_for_tracing=False,
        )
        set_default_openai_api(
            "chat_completions"
        )  # GH Models doesn't support 'responses' endpoint.
        set_tracing_disabled(True)  # Tracing not supported with GitHub Models endpoint.


initialize_models()
