from datetime import datetime
from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,ConfigDict,Field
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin
from backend.schemas.common import ApiResponse
from backend.services.pet_admin_security import actor_from_admin
from backend.services import pet_admin_tasks as service
from backend.routers.admin.pet_config import failure,context
router=APIRouter()
@router.get('/tasks')
async def listing(at:datetime|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),kind:str|None=None,pet_id:str|None=None,user_id:int|None=None,state:str|None=None,reason:str|None=None,start:datetime|None=None,end:datetime|None=None,unknown:bool|None=None,validity:str|None=None,time_field:str='created_at',admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.listing(db,actor_from_admin(admin),**{k:v for k,v in locals().items() if k not in {'db','admin'}}))
@router.get('/tasks/{object_id}')
async def detail(object_id:str,type:str='task',at:datetime|None=None,admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.detail(db,actor_from_admin(admin),object_id,type=type,now=at))
class Recovery(BaseModel):
 model_config=ConfigDict(extra='forbid')
 operation_id:str=Field(min_length=1,max_length=64)
 reason:str=Field(min_length=1,max_length=2000)
 action:str
 domain:str='fault'
@router.post('/tasks/{object_id}')
async def recover(object_id:str,body:Recovery,admin=Depends(get_current_admin),db=Depends(get_db)):
 sessions,actor=await context(db,admin)
 try:return ApiResponse.ok(await service.recover(sessions,actor,object_id=object_id,**body.model_dump()))
 except ValueError as e:return failure(e)
