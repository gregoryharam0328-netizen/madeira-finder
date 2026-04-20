"""Windows-only: ensure asyncio can spawn subprocesses (Playwright driver)."""

from __future__ import annotations

import asyncio
import sys


def apply_windows_proactor_policy() -> None:
    """Use Proactor on Windows so asyncio subprocess transport works (Playwright sync API)."""
    if sys.platform != "win32":
        return
    if not hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        return
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except RuntimeError:
        # Policy may already be set by the host (e.g. uvicorn); ignore.
        pass
