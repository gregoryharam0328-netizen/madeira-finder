"""User listing workflow (Part 3 spec) — status values and flag sync."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import UserListingState

WORKFLOW_STATUSES = (
    "new",
    "seen",
    "favourite",
    "need_to_call",
    "viewing_arranged",
    "offer_made",
    "not_available",
    "not_interested",
)


def effective_workflow(state: UserListingState | None) -> str:
    if not state:
        return "new"
    ws = state.workflow_status
    if ws:
        return ws
    if state.is_hidden:
        return "not_interested"
    if state.is_saved:
        return "favourite"
    if state.is_seen:
        return "seen"
    return "new"


def sync_flags_for_workflow(state: UserListingState, workflow: str) -> None:
    """Update legacy boolean flags when the workflow status is set from the UI."""
    now = datetime.utcnow()
    state.workflow_status = workflow

    if workflow == "favourite":
        state.is_saved = True
        state.saved_at = now
        state.is_hidden = False
        state.hidden_at = None
    elif workflow == "not_interested":
        state.is_saved = False
        state.saved_at = None
        # Keep is_hidden in sync for dismissed rows (filters + Supabase/backfill expect it).
        state.is_hidden = True
        state.hidden_at = now
    else:
        state.is_hidden = False
        state.hidden_at = None
        # Match unsave semantics: leaving "Favourite" for Seen / Unreviewed clears the star so
        # GET /dashboard/summary "saved" and the sidebar Favourites count track the heart.
        if workflow in ("new", "seen"):
            state.is_saved = False
            state.saved_at = None

    if workflow == "seen":
        state.is_seen = True
        state.seen_at = now
    elif workflow == "new":
        state.is_seen = False
        state.seen_at = None
