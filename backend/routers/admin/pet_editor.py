from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin
from backend.schemas.common import ApiResponse
from backend.services.pet_admin_security import actor_from_admin
from backend.services.pet_config_service import ConfigInvalid
from backend.routers.admin.pet_config import failure
from backend.services import pet_admin_editor as service
router=APIRouter()
class Preview(BaseModel):
 model_config=ConfigDict(extra='forbid')
 content:dict
 inputs:dict=Field(default_factory=dict)
@router.get('/editor/{domain}')
async def editor(domain:str,admin=Depends(get_current_admin),db=Depends(get_db)):
 try:return ApiResponse.ok(await service.editor(db,actor_from_admin(admin),domain))
 except ConfigInvalid as e:return failure(e)
@router.get('/preview/{domain}')
async def preview_saved(domain:str,admin=Depends(get_current_admin),db=Depends(get_db)):
 try:return ApiResponse.ok(await service.preview(db,actor_from_admin(admin),domain,readonly=True))
 except (ConfigInvalid,ValueError,KeyError) as e:return failure(e)
@router.post('/preview/{domain}')
async def preview(domain:str,body:Preview,admin=Depends(get_current_admin),db=Depends(get_db)):
 try:return ApiResponse.ok(await service.preview(db,actor_from_admin(admin),domain,content=body.content,inputs=body.inputs))
 except (ConfigInvalid,ValueError,KeyError) as e:return failure(e)
