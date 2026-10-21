"""Single BGM management domain; all reads enforce the same live role matrix."""
from typing import Literal
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select

from backend.constants.bgm import ADMIN_ERR_BGM_NOT_FOUND, BGM_READ_ROLES, BGM_WRITE_ROLES
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services import bgm_service
from backend.services.bgm_audit_service import BgmAuditRoute
from backend.services.bgm_errors import BgmError
from backend.utils.admin_auth import require_role
from backend.models.bgm import BgmOperation
from backend.schemas.bgm import BgmPrepare, BgmCoverPrepare, BgmCoverRemoval, BgmTrackMutation, BgmOrderMutation, BgmCleanupRequest
from backend.services import bgm_upload_service, bgm_directory_service, bgm_cover_service, bgm_cleanup_service

router = APIRouter(route_class=BgmAuditRoute)


@router.get('/tracks')
async def tracks(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 search: str = Query('', max_length=60),
                 state: Literal['receiving', 'processing', 'ready', 'failed', 'deleting', 'delete_failed'] | None = None,
                 filter: Literal['all', 'enabled', 'hidden', 'failed'] = 'all',
                 sort: Literal['created', 'playlist'] = 'created',
                 admin=require_role(*BGM_READ_ROLES), db: AsyncSession = Depends(get_db)):
    return ApiResponse.ok(await bgm_service.list_tracks(db, page=page, page_size=page_size,
                                                     search=search, state=state, filter=filter, sort=sort))


@router.get('/tracks/{track_id}')
async def track(track_id: str, admin=require_role(*BGM_READ_ROLES), db: AsyncSession = Depends(get_db)):
    result = await bgm_service.track_detail(db, track_id)
    return ApiResponse.ok(result) if result else ApiResponse.fail(ADMIN_ERR_BGM_NOT_FOUND)


@router.get('/operations/{operation_id}')
async def operation(operation_id: str, admin=require_role(*BGM_READ_ROLES), db: AsyncSession = Depends(get_db)):
    result = await bgm_service.operation_detail(db, operation_id)
    return ApiResponse.ok(result) if result else ApiResponse.fail(ADMIN_ERR_BGM_NOT_FOUND)


async def write_context(db, admin):
    actor = dict(id=admin.id, token_version=admin.token_version)
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)
    await db.rollback()  # Don't hold the authentication transaction during upload.
    return sessions, actor


@router.post('/operations')
async def prepare_audio(body: BgmPrepare, admin=require_role(*BGM_WRITE_ROLES), db: AsyncSession = Depends(get_db)):
    sessions, actor = await write_context(db, admin)
    service = bgm_cover_service if isinstance(body,BgmCoverPrepare) else bgm_upload_service
    return ApiResponse.ok(await service.prepare(sessions, actor, body))


@router.put('/operations/{operation_id}/content')
async def audio_content(operation_id: str, request: Request, admin=require_role(*BGM_WRITE_ROLES), db: AsyncSession = Depends(get_db)):
    sessions, actor = await write_context(db, admin)
    async with sessions() as lookup:
        action = await lookup.scalar(select(BgmOperation.action).where(BgmOperation.id==operation_id))
    if action not in {'upload_audio','retry_audio','upload_cover'}:
        raise BgmError(20200,404) if action is None else BgmError(20201)
    service = bgm_cover_service if action=='upload_cover' else bgm_upload_service
    return ApiResponse.ok(await service.receive(sessions, actor, operation_id, request))


@router.get('/order')
async def directory_order(admin=require_role(*BGM_READ_ROLES), db: AsyncSession = Depends(get_db)):
    return ApiResponse.ok(await bgm_directory_service.read_order(db))


@router.patch('/tracks/{track_id}')
async def change_track(track_id: str, body: BgmTrackMutation, admin=require_role(*BGM_WRITE_ROLES), db: AsyncSession = Depends(get_db)):
    sessions, actor = await write_context(db, admin)
    return ApiResponse.ok(await bgm_directory_service.mutate(sessions, actor, body, track_id=track_id))


@router.put('/order')
async def change_order(body: BgmOrderMutation, admin=require_role(*BGM_WRITE_ROLES), db: AsyncSession = Depends(get_db)):
    sessions, actor = await write_context(db, admin)
    return ApiResponse.ok(await bgm_directory_service.mutate(sessions, actor, body))


@router.delete('/tracks/{track_id}/cover')
async def remove_cover(track_id: str, body: BgmCoverRemoval, admin=require_role(*BGM_WRITE_ROLES), db: AsyncSession = Depends(get_db)):
    sessions, actor = await write_context(db, admin)
    return ApiResponse.ok(await bgm_cover_service.remove(sessions, actor, track_id, body))


@router.get('/tracks/{track_id}/assets')
async def track_assets(track_id: str, page: int = Query(1,ge=1), page_size: int = Query(20,ge=1,le=100),
                       admin=require_role(*BGM_READ_ROLES), db: AsyncSession = Depends(get_db)):
    result=await bgm_cleanup_service.status(db,track_id,page,page_size)
    return ApiResponse.ok(result) if result else ApiResponse.fail(ADMIN_ERR_BGM_NOT_FOUND)


@router.delete('/tracks/{track_id}')
async def delete_track(track_id: str, body: BgmCleanupRequest, admin=require_role(*BGM_WRITE_ROLES), db: AsyncSession = Depends(get_db)):
    sessions,actor=await write_context(db,admin)
    return ApiResponse.ok(await bgm_cleanup_service.execute(sessions,actor,track_id,body,'delete_track'))


@router.post('/tracks/{track_id}/cleanup-retry')
async def cleanup_track(track_id: str, body: BgmCleanupRequest, admin=require_role(*BGM_WRITE_ROLES), db: AsyncSession = Depends(get_db)):
    sessions,actor=await write_context(db,admin)
    return ApiResponse.ok(await bgm_cleanup_service.execute(sessions,actor,track_id,body,'cleanup_retry'))
