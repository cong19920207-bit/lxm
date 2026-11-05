from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin
from backend.schemas.common import ApiResponse
from backend.services.pet_admin_security import actor_from_admin
from backend.services import pet_admin_text as service
from backend.routers.admin.pet_config import failure,context
router=APIRouter()
class Change(BaseModel):
 model_config=ConfigDict(extra='forbid')
 operation_id:str=Field(min_length=1,max_length=64)
 reason:str=Field(min_length=1,max_length=2000)
 basis_digest:str=Field(min_length=64,max_length=64)
 action:str
 domain:str='copy'
 output:dict|None=None
@router.get('/texts/{text_id}')
async def read(text_id:str,domain:str='copy',admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.view(db,actor_from_admin(admin),text_id,domain))
@router.post('/texts/{text_id}')
async def change(text_id:str,body:Change,admin=Depends(get_current_admin),db=Depends(get_db)):
 sessions,actor=await context(db,admin)
 try:return ApiResponse.ok(await service.change(sessions,actor,text_id=text_id,**body.model_dump()))
 except ValueError as e:return failure(e)
