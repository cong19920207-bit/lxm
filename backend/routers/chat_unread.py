"""Per-message inbox routes shared by the two account authentication methods."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ERR_CHAT_MESSAGE_NOT_FOUND
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services import chat_unread

MessageId = Annotated[int, Field(gt=0, le=2147483647)]


def inbox_router(authenticate) -> APIRouter:
    router = APIRouter()

    @router.get("/unread")
    async def chat_unread_summary(response: Response, user_id: int = Depends(authenticate),
                                  db: AsyncSession = Depends(get_db)):
        response.headers["Cache-Control"] = "no-store"
        return ApiResponse.ok(data=await chat_unread.unread_summary(db, user_id))

    @router.get("/unread/status")
    async def chat_unread_status(response: Response, assistant_id: list[MessageId] | None = Query(None),
                                 agent_id: list[MessageId] | None = Query(None),
                                 user_id: int = Depends(authenticate), db: AsyncSession = Depends(get_db)):
        replies, agents = assistant_id or [], agent_id or []
        if not 1 <= len(replies) + len(agents) <= 100:
            raise HTTPException(422, "Provide between 1 and 100 chat message IDs")
        response.headers["Cache-Control"] = "no-store"
        return ApiResponse.ok(data={"unread": await chat_unread.unread_among(db, user_id, replies, agents)})

    @router.post("/messages/{source}/{message_id}/read")
    async def chat_message_read(source: chat_unread.MessageSource, message_id: int,
                                user_id: int = Depends(authenticate), db: AsyncSession = Depends(get_db)):
        if await chat_unread.mark_message_read(db, user_id, source, message_id) == "missing":
            return ApiResponse.fail(ERR_CHAT_MESSAGE_NOT_FOUND)
        await db.commit()
        return ApiResponse.ok(data={"source": source, "id": message_id, "is_read": True})

    return router
