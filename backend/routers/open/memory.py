"""Read the Key owner's memory nebula using the same entries as H5."""
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_MEMORY_UNAVAILABLE, MEMORY_TYPE_USER
from backend.database import get_db
from backend.routers.pet import private_response
from backend.schemas.common import ApiResponse
from backend.services.memory_effective_config import EffectiveConfigError
from backend.services.user_vector_memory_service import user_vector_memory_service
from backend.utils.open_api_auth import get_current_user_by_api_key

router = APIRouter(
    prefix="/api/open/v1/memory",
    tags=["open-memory"],
    dependencies=[Depends(private_response)],
)


class MemoryEntry(BaseModel):
    doc_id: str
    key: str
    value: str
    content: str


class MemoryPage(BaseModel):
    total: int
    page: int
    page_size: int
    list: list[MemoryEntry]


class MemoryListResponse(ApiResponse):
    data: MemoryPage | None = None


@router.get("/list", response_model=MemoryListResponse, responses={503: {"model": ApiResponse}})
async def list_memories(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """按页读取本账号记忆星云中的星体及其正文。"""
    # The reader verifies sources in separate sessions and may wait for a remote read.
    await db.close()
    try:
        result = await user_vector_memory_service.list_entries(
            memory_type=MEMORY_TYPE_USER, user_id=user_id, page=page, page_size=page_size
        )
    except (EffectiveConfigError, SQLAlchemyError, TimeoutError):
        response.status_code = 503
        return ApiResponse.fail(ADMIN_ERR_MEMORY_UNAVAILABLE)

    if "error_code" in result:
        response.status_code = 503
        return ApiResponse.fail(ADMIN_ERR_MEMORY_UNAVAILABLE)
    return MemoryListResponse(data=MemoryPage.model_validate(result))
