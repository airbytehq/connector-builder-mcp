# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Data models for phase-specific handoffs between manager and developer agents."""


from pydantic import BaseModel


class Phase1Data(BaseModel):
    """Data for Phase 1: First successful stream read."""

    api_name: str
    additional_instructions: str = ""
    phase_description: str = "Phase 1: First Successful Stream Read"
    objectives: list[str] = [
        "Research the target API and understand its structure",
        "Create initial manifest using the scaffold tool",
        "Set up proper authentication (request secrets from user if needed)",
        "Configure one stream without pagination initially",
        "Validate that you can read records from this stream",
    ]


class Phase2Data(BaseModel):
    """Data for Phase 2: Working pagination."""

    api_name: str
    phase_description: str = "Phase 2: Working Pagination"
    objectives: list[str] = [
        "Add pagination configuration to the manifest",
        "Test reading multiple pages of data",
        "Confirm you can reach the end of the stream",
        "Verify record counts are not suspicious multiples",
        "Update checklist.md with progress",
    ]


class Phase3Data(BaseModel):
    """Data for Phase 3: Add remaining streams."""

    api_name: str
    phase_description: str = "Phase 3: Add Remaining Streams"
    objectives: list[str] = [
        "Identify all available streams from API documentation",
        "Add each stream to the manifest one by one",
        "Test each stream individually",
        "Run full connector readiness test",
        "Update checklist.md with final results",
    ]
