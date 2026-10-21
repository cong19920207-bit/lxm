"""Public music metadata has no user identity or preference dependency."""
from fastapi import APIRouter,Depends,Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services import bgm_catalog_service as catalog

router=APIRouter(prefix='/api/bgm',tags=['bgm'])


@router.get('/catalog')
async def public_catalog(response:Response,db:AsyncSession=Depends(get_db)):
    response.headers['Cache-Control']='no-store'
    sessions=async_sessionmaker(db.bind,expire_on_commit=False)
    try:return ApiResponse.ok(await catalog.cache.get(sessions))
    except catalog.CatalogUnavailable:
        return JSONResponse(status_code=503,headers={'Cache-Control':'no-store','Retry-After':'2'},content=ApiResponse.fail(20207).model_dump())
