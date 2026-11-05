from datetime import datetime,date
from fastapi import APIRouter,Depends,Query,Response
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import get_current_admin
from backend.services.pet_admin_security import actor_from_admin
from backend.services import pet_admin_read as service
router=APIRouter()
@router.get('/pets')
async def pets(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),pet_id:str|None=None,user_id:int|None=None,name:str|None=None,stage:str|None=None,band:str|None=None,account:str|None=None,at:datetime|None=None,start:datetime|None=None,end:datetime|None=None,admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.list_pets(db,actor_from_admin(admin),page=page,page_size=page_size,pet_id=pet_id,user_id=user_id,name=name,stage=stage,band=band,account=account,at=at,start=start,end=end))
@router.get('/pets/{pet_id}')
async def detail(pet_id:str,at:datetime|None=None,admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.detail(db,actor_from_admin(admin),pet_id,at=at))
@router.get('/pets/{pet_id}/{panel}')
async def panel(pet_id:str,panel:str,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),at:datetime|None=None,start:datetime|None=None,end:datetime|None=None,source_id:str|None=None,admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.panel(db,actor_from_admin(admin),pet_id,panel,at=at,start=start,end=end,source_id=source_id,page=page,page_size=page_size))

@router.get('/overview/{section}')
async def overview(section:str,at:datetime|None=None,start:datetime|None=None,admin=Depends(get_current_admin),db=Depends(get_db)):
 from backend.services.pet_admin_overview import section as read_section
 return ApiResponse.ok(await read_section(db,actor_from_admin(admin),section,at=at,start=start))

@router.get('/daily/{pet_id}')
async def daily_record(pet_id:str,day:date,at:datetime|None=None,admin=Depends(get_current_admin),db=Depends(get_db)):
 return ApiResponse.ok(await service.daily_record(db,actor_from_admin(admin),pet_id,day=day,at=at))

@router.get('/photo-assets/{snapshot_id}')
async def photo_image(snapshot_id:str,response:Response,admin=Depends(get_current_admin),db=Depends(get_db)):
 response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
 return ApiResponse.ok(await service.photo_image(db,actor_from_admin(admin),snapshot_id))
