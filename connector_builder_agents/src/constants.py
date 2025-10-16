# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Constants for the Airbyte connector builder agents."""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

ROOT_PROMPT_FILE_PATH = Path(__file__).parent.parent / "prompts" / "root-prompt.md"
ROOT_PROMPT_FILE_STR = ROOT_PROMPT_FILE_PATH.read_text(encoding="utf-8")
MAX_CONNECTOR_BUILD_STEPS = 100
DEFAULT_CONNECTOR_BUILD_API_NAME: str = "JSONPlaceholder API"
DEFAULT_DEVELOPER_MODEL: str = "openai:gpt-4o"
DEFAULT_MANAGER_MODEL: str = "openai:gpt-4o"
AUTO_OPEN_TRACE_URL: bool = os.environ.get("AUTO_OPEN_TRACE_URL", "1").lower() in {"1", "true"}

HEADLESS_BROWSER = True
