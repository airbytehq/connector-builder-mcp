"""Utility functions for the connector builder agents."""

from contextlib import suppress
from functools import lru_cache

from .constants import AUTO_OPEN_TRACE_URL


@lru_cache  # Hacky way to run 'just once' 🙂
def open_if_browser_available(url: str) -> None:
    """Open a URL for the user to track progress.

    Fail gracefully in the case that we don't have a browser.
    """
    if AUTO_OPEN_TRACE_URL is False:
        return

    with suppress(Exception):
        import webbrowser  # noqa: PLC0415

        webbrowser.open(url=url)
