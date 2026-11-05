"""One pet administration API namespace; scoped operations and read-only audit."""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from backend.database import get_db
from backend.models.pet_admin import PetAdminOperation
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import get_current_admin
from backend.services.pet_admin_security import (actor_from_admin,allowed,DOMAINS,WRITE_ROLES,
    prepare_operation,read_audit,operation_view,check_permission,PetAdminDenied)

router=APIRouter()
from backend.routers.admin.pet_resources import router as resources_router
router.include_router(resources_router)
from backend.routers.admin.pet_config import router as config_router
router.include_router(config_router)
from backend.routers.admin.pet_read import router as read_router
router.include_router(read_router)
from backend.routers.admin.pet_editor import router as editor_router
router.include_router(editor_router)
from backend.routers.admin.pet_ai import router as ai_router
router.include_router(ai_router)
from backend.routers.admin.pet_repair import router as repair_router
router.include_router(repair_router)
from backend.routers.admin.pet_text import router as text_router
router.include_router(text_router)

from backend.routers.admin.pet_tasks import router as tasks_router
router.include_router(tasks_router)

from backend.routers.admin.pet_versions import router as versions_router
router.include_router(versions_router)

class PrepareOperation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operation_id:str=Field(min_length=1,max_length=64)
    action:str=Field(max_length=48)
    domain:str=Field(max_length=24)
    target:str=Field(min_length=1,max_length=128)
    reason:str=Field(min_length=1,max_length=2000)
    payload:dict=Field(default_factory=dict)

@router.get('/permissions')
async def permissions(admin=Depends(get_current_admin)):
    return ApiResponse.ok({'role':admin.role,'actions':[
        {'action':action,'domain':domain} for action,domain in WRITE_ROLES if allowed(admin.role,action,domain)]})

@router.get('/audit')
async def audit(domain:str|None=None,operation_id:str|None=None,limit:int=Query(100,ge=1,le=100),
                admin=Depends(get_current_admin),db=Depends(get_db)):
    return ApiResponse.ok({'list':await read_audit(db,actor_from_admin(admin),domain=domain,operation_id=operation_id,limit=limit)})

@router.post('/operations')
async def prepare(body:PrepareOperation,admin=Depends(get_current_admin),db=Depends(get_db)):
    actor=actor_from_admin(admin);sessions=async_sessionmaker(db.bind,expire_on_commit=False,autoflush=False)
    await db.rollback()
    try:
        op=await prepare_operation(sessions,actor,**body.model_dump())
    except ValueError as error:raise HTTPException(409,detail='operation_conflict_or_invalid') from error
    return ApiResponse.ok({'operation_id':op})

@router.get('/operations/{operation_id}')
async def operation(operation_id:str,admin=Depends(get_current_admin),db=Depends(get_db)):
    op=await db.get(PetAdminOperation,operation_id)
    if op is None:raise HTTPException(404,detail='operation_not_found')
    await check_permission(db,actor_from_admin(admin),'audit.read',op.domain)
    return ApiResponse.ok(operation_view(op))
