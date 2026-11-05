from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin
from backend.schemas.common import ApiResponse
from backend.services.pet_admin_security import actor_from_admin
from backend.services.pet_admin_ai import template_preview,simulate
from backend.services.pet_config_service import ConfigInvalid,ConfigConflict
from backend.services.pet_llm import ModelConfigurationError
from backend.services.pet_budget import BudgetDenied
from backend.routers.admin.pet_config import failure,context
from backend.routers.admin.pet_editor import Preview
router=APIRouter()
@router.get('/ai/preview')
async def preview_saved(admin=Depends(get_current_admin),db=Depends(get_db)):
 try:return ApiResponse.ok(await template_preview(db,actor_from_admin(admin),readonly=True))
 except ValueError as e:return failure(e)
@router.post('/ai/preview')
async def preview(body:Preview,admin=Depends(get_current_admin),db=Depends(get_db)):
 try:return ApiResponse.ok(await template_preview(db,actor_from_admin(admin),content=body.content,inputs=body.inputs))
 except ValueError as e:return failure(e)
class Simulation(BaseModel):
 model_config=ConfigDict(extra='forbid')
 operation_id:str=Field(min_length=1,max_length=64)
 reason:str=Field(min_length=1,max_length=2000)
 revision:int=Field(ge=1)
 content_digest:str=Field(min_length=64,max_length=64)
 workflow:str
 inputs:dict
@router.post('/ai/test')
async def test(body:Simulation,admin=Depends(get_current_admin),db=Depends(get_db)):
 sessions,actor=await context(db,admin)
 try:return ApiResponse.ok(await simulate(sessions,actor,**body.model_dump()))
 except (ConfigInvalid,ConfigConflict,ModelConfigurationError,BudgetDenied) as e:return failure(e)
