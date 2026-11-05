from datetime import datetime
from fastapi import APIRouter,Depends,Query
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin
from backend.schemas.common import ApiResponse
from backend.services.pet_admin_security import actor_from_admin
from backend.services import pet_admin_versions as service
router=APIRouter()
@router.get('/versions')
async def versions(domain:str|None=None,version:int|None=None,admin_id:int|None=None,action:str|None=None,start:datetime|None=None,end:datetime|None=None,at:datetime|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.versions(db,actor_from_admin(admin),**{k:v for k,v in locals().items() if k not in {'db','admin'}}))
@router.get('/versions/{version_id}')
async def detail(version_id:str,admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.version_detail(db,actor_from_admin(admin),version_id))
@router.get('/logs')
async def audit(domain:str|None=None,action:str|None=None,admin_id:int|None=None,operation_id:str|None=None,object_id:str|None=None,start:datetime|None=None,end:datetime|None=None,at:datetime|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.audit(db,actor_from_admin(admin),**{k:v for k,v in locals().items() if k not in {'db','admin'}}))
