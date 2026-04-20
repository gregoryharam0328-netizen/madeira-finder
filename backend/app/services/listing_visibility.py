"""Which listing groups appear on main feeds vs the dismissed (Not interested) tab."""

from __future__ import annotations

from sqlalchemy import and_, or_

from app.models import UserListingState


def filter_visible_on_main_feed(query):
    """
    Rows visible on All listings / New today / default grids.
    Excludes workflow_status == 'not_interested' and legacy rows with is_hidden (pre-workflow).
    """
    return query.filter(
        or_(
            UserListingState.id.is_(None),
            and_(
                or_(
                    UserListingState.workflow_status.is_(None),
                    UserListingState.workflow_status != "not_interested",
                ),
                or_(UserListingState.is_hidden.is_(None), UserListingState.is_hidden.is_(False)),
            ),
        )
    )


def filter_dismissed_not_interested(query):
    """Groups the user marked Not interested (or legacy hidden-only rows)."""
    return query.filter(
        UserListingState.id.isnot(None),
        or_(
            UserListingState.workflow_status == "not_interested",
            UserListingState.is_hidden.is_(True),
        ),
    )
