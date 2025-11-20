#!/usr/bin/env python3

# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
"""Generate docs for all public modules in connector-builder-mcp and save them to docs/generated.

Usage:
    uv run python docs/generate.py

"""

from __future__ import annotations

import pathlib
import shutil

import pdoc


def run() -> None:
    """Generate docs for all public modules in connector-builder-mcp and save them to docs/generated."""
    public_modules = [
        "connector_builder_mcp",
    ]

    # recursively delete the docs/generated folder if it exists
    if pathlib.Path("docs/generated").exists():
        shutil.rmtree("docs/generated")

    pdoc.render.configure(
        template_directory=pathlib.Path("docs/templates"),
        show_source=True,
        search=True,
        logo="https://docs.airbyte.com/img/logo-dark.png",
        favicon="https://docs.airbyte.com/img/favicon.png",
        mermaid=True,
        docformat="google",
    )
    pdoc.pdoc(
        *public_modules,
        output_directory=pathlib.Path("docs/generated"),
    )


if __name__ == "__main__":
    run()
