from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin
from backend.schemas.common import ApiResponse
from backend.services.pet_admin_security import actor_from_admin
from backend.services import pet_admin_repair as service
from backend.routers.admin.pet_config import failure,context
router=APIRouter()
@router.get('/repair/{pet_id}/preview')
async def preview(pet_id:str,birth_date:str|None=None,admin=Depends(get_current_admin),db=Depends(get_db)):
 try:return ApiResponse.ok(await service.preview(db,actor_from_admin(admin),pet_id,birth_date=birth_date))
 except ValueError as e:return failure(e)
class Repair(BaseModel):
 model_config=ConfigDict(extra='forbid')
 operation_id:str=Field(min_length=1,max_length=64)
 reason:str=Field(min_length=1,max_length=2000)
 basis_digest:str=Field(min_length=64,max_length=64)
 birth_date:str|None=None
@router.post('/repair/{pet_id}')
async def repair(pet_id:str,body:Repair,admin=Depends(get_current_admin),db=Depends(get_db)):
 sessions,actor=await context(db,admin)
 try:return ApiResponse.ok(await service.repair(sessions,actor,pet_id=pet_id,**body.model_dump()))
 except ValueError as e:return failure(e)
