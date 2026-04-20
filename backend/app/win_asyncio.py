"""Windows-only: ensure asyncio can spawn subprocesses (Playwright driver)."""

from __future__ import annotations

import asyncio
import sys
from typing import Any


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


def _is_win_connection_forcibly_closed(exc: BaseException) -> bool:
    """WinError 10054 during transport teardown — noisy but harmless with Proactor."""
    if not isinstance(exc, OSError):
        return False
    if getattr(exc, "winerror", None) == 10054:
        return True
    return "10054" in str(exc) and "forcibly closed" in str(exc).lower()


def install_windows_proactor_reset_noise_handler(loop: asyncio.AbstractEventLoop) -> None:
    """
    Suppress asyncio's default logging for Proactor ``ConnectionResetError`` (10054) on
    ``_call_connection_lost`` — the remote already closed the socket; ``shutdown()`` races.
    """
    if sys.platform != "win32":
        return
    prev = loop.get_exception_handler()

    def _handler(l: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        exc = context.get("exception")
        if exc is not None and _is_win_connection_forcibly_closed(exc):
            return
        if prev is not None:
            prev(l, context)
        else:
            l.default_exception_handler(context)

    loop.set_exception_handler(_handler)
