"""Immutable registration of reviewed, local pet assets."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel,ConfigDict,Field
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin
from backend.schemas.common import ApiResponse
from backend.services.pet_admin_security import actor_from_admin,check_permission
from backend.services import pet_scene_resources as service
from backend.routers.admin.pet_config import context,failure
from backend.services.pet_config_service import ConfigInvalid
router=APIRouter()
class Registration(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operation_id:str=Field(min_length=1,max_length=64)
    reason:str=Field(min_length=1,max_length=2000)
    resource:dict
@router.get('/resources')
async def resources(admin=Depends(get_current_admin),db=Depends(get_db)):
    return ApiResponse.ok(await service.list_resources(db,actor_from_admin(admin)))
@router.post('/resources')
async def register(body:Registration,admin=Depends(get_current_admin),db=Depends(get_db)):
    sessions,actor=await context(db,admin)
    try:return ApiResponse.ok(await service.register_resource(sessions,actor,**body.model_dump()))
    except (ConfigInvalid,ValueError) as error:return failure(error)
@router.get('/resources/{resource_id}/references')
async def references(resource_id:str,admin=Depends(get_current_admin),db=Depends(get_db)):
    from backend.services.pet_appearance import resource_references
    await check_permission(db,actor_from_admin(admin),'audit.read','appearance')
    return ApiResponse.ok({'resource_id':resource_id,'references':await resource_references(db,resource_id)})
