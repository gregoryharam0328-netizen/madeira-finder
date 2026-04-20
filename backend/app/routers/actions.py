from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ListingGroup, User, UserListingState
from app.schemas import ListingStatePatch
from app.services.user_workflow import WORKFLOW_STATUSES, sync_flags_for_workflow

router = APIRouter()


def get_or_create_state(db: Session, user_id: UUID, listing_group_id: UUID) -> UserListingState:
    state = db.query(UserListingState).filter_by(user_id=user_id, listing_group_id=listing_group_id).first()
    if state:
        return state
    exists = db.query(ListingGroup).filter_by(id=listing_group_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Listing group not found")
    state = UserListingState(user_id=user_id, listing_group_id=listing_group_id, workflow_status="new")
    db.add(state)
    db.flush()
    return state


@router.post("/{listing_group_id}/save")
def save_listing(listing_group_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state = get_or_create_state(db, current_user.id, listing_group_id)
    state.is_saved = True
    state.saved_at = datetime.utcnow()
    state.workflow_status = "favourite"
    state.is_hidden = False
    state.hidden_at = None
    db.commit()
    return {"ok": True}


@router.post("/{listing_group_id}/unsave")
def unsave_listing(listing_group_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state = get_or_create_state(db, current_user.id, listing_group_id)
    state.is_saved = False
    state.saved_at = None
    if state.workflow_status == "favourite":
        state.workflow_status = "seen"
        state.is_seen = True
        state.seen_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/{listing_group_id}/seen")
def mark_seen(listing_group_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state = get_or_create_state(db, current_user.id, listing_group_id)
    state.is_seen = True
    state.seen_at = datetime.utcnow()
    if state.workflow_status in (None, "new"):
        state.workflow_status = "seen"
    db.commit()
    return {"ok": True}


@router.post("/{listing_group_id}/unseen")
def mark_unseen(listing_group_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state = get_or_create_state(db, current_user.id, listing_group_id)
    state.is_seen = False
    state.seen_at = None
    if state.workflow_status == "seen":
        state.workflow_status = "new"
    db.commit()
    return {"ok": True}


@router.post("/{listing_group_id}/hide")
def hide_listing(listing_group_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state = get_or_create_state(db, current_user.id, listing_group_id)
    sync_flags_for_workflow(state, "not_interested")
    db.commit()
    return {"ok": True}


@router.post("/{listing_group_id}/unhide")
def unhide_listing(listing_group_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state = get_or_create_state(db, current_user.id, listing_group_id)
    state.is_hidden = False
    state.hidden_at = None
    state.workflow_status = "new"
    db.commit()
    return {"ok": True}


@router.patch("/{listing_group_id}/state")
def patch_listing_state(
    listing_group_id: UUID,
    body: ListingStatePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    state = get_or_create_state(db, current_user.id, listing_group_id)
    if body.workflow_status is not None:
        if body.workflow_status not in WORKFLOW_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid workflow_status")
        sync_flags_for_workflow(state, body.workflow_status)
    if body.note is not None:
        state.note = body.note
    db.flush()
    db.commit()
    return {"ok": True}
