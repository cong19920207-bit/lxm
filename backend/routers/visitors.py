"""Write-only H5 analytics. The receipt never exposes a device or its history."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.schemas.visitor import OpenReference, VisitorInput
from backend.services import visitor_events as events
from backend.services.visitor_network import network_snapshot, source_for_request
from backend.utils.auth_middleware import get_current_user_optional

router = APIRouter(prefix="/api/h5/visitors", tags=["h5-visitors"])


def check_entry(request: Request, body: OpenReference, user: int | None, kind: str | None = None):
    # The edge marker can only narrow the allowed write. IP trust is checked separately.
    if request.headers.get("x-lxm-visitor-edge") == "public" and body.entry != "public/feed":
        raise HTTPException(400, "公开入口只接受本页匿名访问")
    if body.entry == "public/feed" and (user is not None or kind == "identity"):
        raise HTTPException(400, "公开入口只接受匿名访问")


@router.post("/open-context")
async def open_context(body: OpenReference, request: Request, user: int | None = Depends(get_current_user_optional)):
    # A separately acknowledged, event-bound observation may survive failure of
    # the event transaction. A later request cannot mint proof for an old opening.
    check_entry(request, body, user)
    witness = events.issue_witness(body, str(user) if user is not None else "guest", events.utc_now())
    return ApiResponse.ok({"witness": witness})


@router.post("/events")
async def receive(body: VisitorInput, request: Request, db: AsyncSession = Depends(get_db),
                  user: int | None = Depends(get_current_user_optional)):
    check_entry(request, body, user, body.kind)
    now = events.utc_now()
    _, address = await source_for_request(request)
    snapshot = await run_in_threadpool(network_snapshot, address)
    await db.run_sync(events.record, body, str(user) if user is not None else "guest", snapshot, now)
    await db.commit()
    return ApiResponse.ok({"received": True})
