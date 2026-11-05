"""Generic configuration workflow only; the business editors arrive in STEP-030/031."""
from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.ext.asyncio import async_sessionmaker
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.constants.pet import PET_CONFIG_CONFLICT,PET_CONFIG_INVALID
from backend.utils.admin_auth import get_current_admin
from backend.services.pet_admin_security import actor_from_admin,allowed,PetAdminDenied
from backend.services import pet_config_service as service

router=APIRouter()

class StrictBody(BaseModel):model_config=ConfigDict(extra='forbid')
class Draft(StrictBody):
    content:dict
    expected_revision:int=Field(ge=0)
    base_version:int=Field(ge=0)
class Validation(StrictBody):revision:int=Field(ge=1)
class Publication(StrictBody):
    operation_id:str=Field(min_length=1,max_length=64)
    reason:str=Field(min_length=1,max_length=2000)
    revision:int=Field(ge=1)
    base_version:int=Field(ge=0)
class Rollback(StrictBody):
    operation_id:str=Field(min_length=1,max_length=64)
    reason:str=Field(min_length=1,max_length=2000)
    target_version:int=Field(ge=1)
    base_version:int=Field(ge=1)
class Disable(StrictBody):
    operation_id:str=Field(min_length=1,max_length=64)
    reason:str=Field(min_length=1,max_length=2000)
    flag:str
class DraftMutation(StrictBody):
    operation_id:str=Field(min_length=1,max_length=64)
    reason:str=Field(min_length=1,max_length=2000)
    expected_revision:int=Field(ge=0)
    base_version:int=Field(ge=0)
class RestoreDraft(DraftMutation):
    source_type:str
    source_revision:int|None=Field(default=None,ge=1)
    source_version:int|None=Field(default=None,ge=1)
    workflow:str|None=None

def failure(error):
    return ApiResponse.fail(PET_CONFIG_CONFLICT if isinstance(error,service.ConfigConflict) else PET_CONFIG_INVALID,data={'reason':str(error)})

@router.get('/config/{domain}')
async def read(domain:str,admin=Depends(get_current_admin),db=Depends(get_db)):
    try:value=await service.read_config(db,domain)
    except service.ConfigInvalid as error:return failure(error)
    if not allowed(admin.role,'config.publish',domain):
        for key in ('draft','validated','draft_diff','validation_error','ai_tests'):value.pop(key,None)
        value.update(draft_state='none',changed_paths=[])
        if domain=='ai':value['content']={'configured':bool(value['content'])}
    return ApiResponse.ok(value)

@router.put('/config/{domain}/draft')
async def draft(domain:str,body:Draft,admin=Depends(get_current_admin),db=Depends(get_db)):
    try:return ApiResponse.ok(await service.save_draft(db,actor_from_admin(admin),domain,**body.model_dump()))
    except (service.ConfigInvalid,service.ConfigConflict) as error:return failure(error)

@router.get('/config/{domain}/drafts')
async def drafts(domain:str,page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=50),admin=Depends(get_current_admin),db=Depends(get_db)):
    from backend.services.pet_config_history import history
    try:return ApiResponse.ok(await history(db,actor_from_admin(admin),domain,page=page,page_size=page_size))
    except (service.ConfigInvalid,service.ConfigConflict) as error:return failure(error)

@router.post('/config/{domain}/restore')
async def restore(domain:str,body:RestoreDraft,admin=Depends(get_current_admin),db=Depends(get_db)):
    from backend.services.pet_config_history import restore as restore_saved
    sessions,actor=await context(db,admin)
    try:return ApiResponse.ok(await restore_saved(sessions,actor,domain,**body.model_dump()))
    except (service.ConfigInvalid,service.ConfigConflict,ValueError) as error:return failure(error)

@router.delete('/config/{domain}/drafts/{revision}')
async def delete(domain:str,revision:int,body:DraftMutation,admin=Depends(get_current_admin),db=Depends(get_db)):
    from backend.services.pet_config_history import delete_draft
    sessions,actor=await context(db,admin)
    try:return ApiResponse.ok(await delete_draft(sessions,actor,domain,revision,**body.model_dump()))
    except (service.ConfigInvalid,service.ConfigConflict,ValueError) as error:return failure(error)

@router.post('/config/{domain}/validate')
async def validate(domain:str,body:Validation,admin=Depends(get_current_admin),db=Depends(get_db)):
    try:return ApiResponse.ok(await service.validate_draft(db,actor_from_admin(admin),domain,revision=body.revision))
    except (service.ConfigInvalid,service.ConfigConflict) as error:return failure(error)

async def context(db,admin):
    actor=actor_from_admin(admin);sessions=async_sessionmaker(db.bind,expire_on_commit=False,autoflush=False)
    await db.rollback()
    return sessions,actor

@router.post('/config/{domain}/publish')
async def publish(domain:str,body:Publication,admin=Depends(get_current_admin),db=Depends(get_db)):
    sessions,actor=await context(db,admin)
    try:return ApiResponse.ok(await service.publish(sessions,actor,domain,**body.model_dump()))
    except (service.ConfigInvalid,service.ConfigConflict,ValueError) as error:return failure(error)

@router.post('/config/{domain}/rollback')
async def rollback(domain:str,body:Rollback,admin=Depends(get_current_admin),db=Depends(get_db)):
    sessions,actor=await context(db,admin)
    try:return ApiResponse.ok(await service.rollback(sessions,actor,domain,**body.model_dump()))
    except (service.ConfigInvalid,service.ConfigConflict,ValueError) as error:return failure(error)

@router.post('/runtime/disable')
async def disable(body:Disable,admin=Depends(get_current_admin),db=Depends(get_db)):
    sessions,actor=await context(db,admin)
    try:return ApiResponse.ok(await service.disable(sessions,actor,**body.model_dump()))
    except (service.ConfigInvalid,ValueError) as error:return failure(error)


@router.get('/model-status')
async def model_status(admin=Depends(get_current_admin),db=Depends(get_db)):
    from backend.services.pet_llm import status
    from backend.services.pet_admin_security import check_permission
    await check_permission(db,actor_from_admin(admin),'overview.read','runtime')
    config=await service.read_config(db,'ai');value=status(config['content'])
    if admin.role in {'ops_admin','observer'}:value={'available':value['available'],'problems':value['problems'],'credential':'not_returned','source':'server_env'}
    return ApiResponse.ok(value)

@router.get('/config/{domain}/impact')
async def impact(domain:str,revision:int,admin=Depends(get_current_admin),db=Depends(get_db)):
 from backend.services.pet_admin_versions import impact as read_impact
 try:return ApiResponse.ok(await read_impact(db,actor_from_admin(admin),domain,revision=revision))
 except (service.ConfigInvalid,ValueError) as error:return failure(error)

@router.get('/config/{domain}/rollback-preview')
async def rollback_preview(domain:str,target_version:int,admin=Depends(get_current_admin),db=Depends(get_db)):
 from backend.services.pet_admin_versions import impact as read_impact
 try:return ApiResponse.ok(await read_impact(db,actor_from_admin(admin),domain,target_version=target_version))
 except (service.ConfigInvalid,ValueError) as error:return failure(error)
