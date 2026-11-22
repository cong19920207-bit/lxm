"""Read the published music catalog shared by H5 and Open API clients."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.constants.bgm import ADMIN_ERR_BGM_UNAVAILABLE
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services import bgm_catalog_service as catalog

router = APIRouter(prefix="/api/bgm", tags=["bgm"])


@router.get("/catalog")
async def public_catalog(response: Response, db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await read_catalog(response, db)


async def read_catalog(response: Response, db: AsyncSession) -> ApiResponse:
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)
    try:
        return ApiResponse.ok(await catalog.cache.get(sessions))
    except catalog.CatalogUnavailable:
        response.status_code = 503
        response.headers["Retry-After"] = "2"
        return ApiResponse.fail(ADMIN_ERR_BGM_UNAVAILABLE)
