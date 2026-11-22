"""Account-specific feed access with the account's existing Open API Key."""

from typing import Annotated
from urllib.parse import urljoin, urlsplit

from fastapi import APIRouter, Depends, Header, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants.life_feed_config import DEFAULT_FEED_PAGE_HEADER_AVATAR_URL
from backend.database import get_db
from backend.routers.feed import CommentBody, feed_event_stream, get_feed_write_db
from backend.routers.pet import private_response
from backend.schemas.common import ApiResponse
from backend.services.feed_service import FeedError, feed_service
from backend.utils.open_api_auth import get_current_user_by_api_key

router = APIRouter(
    prefix="/api/open/v1/feed", tags=["open-feed"],
    dependencies=[Depends(private_response)],
)
Account = Annotated[int, Depends(get_current_user_by_api_key)]
Database = Annotated[AsyncSession, Depends(get_db)]
WriteDatabase = Annotated[AsyncSession, Depends(get_feed_write_db)]
FeedId = Annotated[int, Path(ge=1, le=2_147_483_647)]


async def _respond(work, project=None, *, commit: AsyncSession | None = None) -> ApiResponse:
    try:
        data = await work
        if commit is not None:
            await commit.commit()
    except FeedError as exc:
        return ApiResponse.fail(code=exc.code)
    return ApiResponse.ok(project(data) if project else data)


def _image_url(base: str, value: str | None) -> str | None:
    """Use the public request origin for H5 assets; keep signed CDN URLs intact."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        url = urljoin(base, value.strip())
        parts = urlsplit(url)
        if parts.scheme in ("https", "http") and parts.hostname:
            return url
    except ValueError:
        pass
    return None


def _post_images(base: str, post: dict) -> dict:
    return {**post, "image_urls": [
        url for value in post["image_urls"] if (url := _image_url(base, value))
    ]}


@router.get("/config/header", response_model=ApiResponse)
async def get_header(request: Request, user_id: Account):
    data = await feed_service.get_header_config()
    base = str(request.base_url)
    # Existing installations may have the old seeded .jpg path. The shipped asset is .png.
    bg = data["header_bg_url"]
    fallback_bg = "/static/images/feed/bg_default.png"
    if bg == "/static/images/feed/bg_default.jpg":
        bg = fallback_bg
    return ApiResponse.ok({
        **data,
        "header_bg_url": _image_url(base, bg) or _image_url(base, fallback_bg),
        "header_avatar_url": (_image_url(base, data["header_avatar_url"])
                              or _image_url(base, DEFAULT_FEED_PAGE_HEADER_AVATAR_URL)),
    })


@router.get("/list", response_model=ApiResponse)
async def list_feed(
    request: Request, user_id: Account, db: Database,
    cursor: str | None = Query(None, description="上一页返回的 next_cursor"),
    size: int = Query(20, ge=1, le=50),
):
    base = str(request.base_url)
    return await _respond(
        feed_service.list_feed(db, user_id, cursor, size, stable_cursor=True),
        lambda page: {**page, "posts": [_post_images(base, post) for post in page["posts"]]},
    )


@router.get("/posts/{post_id}", response_model=ApiResponse)
async def get_post(request: Request, post_id: FeedId, user_id: Account, db: Database):
    return await _respond(feed_service.get_post(db, user_id, post_id),
                          lambda post: _post_images(str(request.base_url), post))


@router.post("/enter", response_model=ApiResponse)
async def enter(user_id: Account, db: Database):
    return await _respond(feed_service.enter_feed(db, user_id), commit=db)


@router.get("/badge", response_model=ApiResponse)
async def get_badge(user_id: Account, db: Database):
    return await _respond(feed_service.get_badge(db, user_id))


@router.get("/events", response_class=StreamingResponse,
            responses={200: {"content": {"text/event-stream": {}}}})
async def feed_events(request: Request, user_id: Account, db: Database):
    # FastAPI shares get_db with the API Key dependency. A throttled last_used_at
    # update can leave its SELECT transaction open until the SSE stream ends.
    await db.close()
    response = feed_event_stream(request, user_id)
    private_response(response)
    return response


@router.post("/{post_id}/like", response_model=ApiResponse)
async def like(post_id: FeedId, user_id: Account, db: WriteDatabase):
    return await _respond(feed_service.like_post(db, user_id, post_id))


@router.delete("/{post_id}/like", response_model=ApiResponse)
async def unlike(post_id: FeedId, user_id: Account, db: WriteDatabase):
    return await _respond(feed_service.unlike_post(db, user_id, post_id), commit=db)


@router.post("/{post_id}/comments", response_model=ApiResponse)
async def comment(
    post_id: FeedId, body: CommentBody, user_id: Account, db: WriteDatabase,
    idempotency_key: str | None = Header(
        None, alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[!-~]+$"),
):
    return await _respond(feed_service.create_comment(
        db, user_id, post_id, body.content,
        reply_to_lxm=body.reply_to_lxm, idempotency_key=idempotency_key,
    ), commit=db)


@router.post("/{post_id}/read", response_model=ApiResponse)
async def read_post(post_id: FeedId, user_id: Account, db: Database):
    return await _respond(feed_service.mark_feed_post_read(db, user_id, post_id))


@router.post("/comments/{comment_id}/read", response_model=ApiResponse)
async def read_reply(comment_id: FeedId, user_id: Account, db: Database):
    return await _respond(feed_service.mark_comment_reply_read(db, user_id, comment_id))
