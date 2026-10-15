"""Global diagnostic management, independent of user-directory permissions."""
import asyncio
import os
from typing import Literal
from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,Field,field_validator,model_validator
from backend.database import async_session_maker
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import require_role
from backend.services.memory_admin_common import AdminMemoryError,response_error,uuid_value
from backend.services.memory_diagnostic_service import DiagnosticService

router=APIRouter()
_service=None

def get_service():
    global _service
    if _service is None:_service=DiagnosticService(async_session_maker,os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip())
    return _service

class ExecuteBody(BaseModel):
    request_id:str
    user_id:int=Field(gt=0,strict=True)
    source:Literal['main','openapi','step8']
    input:str=Field(min_length=1,max_length=2000)
    parent_execution_id:str|None=None
    @field_validator('request_id')
    @classmethod
    def request_uuid(cls,value):return uuid_value(value,(7,))
    @field_validator('parent_execution_id')
    @classmethod
    def parent_uuid(cls,value):return uuid_value(value,(4,)) if value else value
    @model_validator(mode='after')
    def valid_input(self):
        if not self.input.strip() or self.source=='step8' and len(self.input)>200:raise ValueError('input_invalid')
        return self

async def bounded(invoke):
    try:
        async with asyncio.timeout(5):return ApiResponse.ok(data=await invoke())
    except AdminMemoryError as exc:return response_error(exc)
    except Exception:return ApiResponse.fail(20129,message='persistence_unavailable')

@router.post('/memory-diagnostics')
async def execute(body:ExecuteBody,actor=require_role('super_admin','ai_trainer')):
    service=get_service()
    try:
        result,created=await service.admit(body.model_dump(),actor)
        if created:service.schedule(result['id'])
        return ApiResponse.ok(data=result)
    except AdminMemoryError as exc:return response_error(exc)
    except Exception:return ApiResponse.fail(20129,message='persistence_unavailable')

@router.get('/memory-diagnostics')
async def history(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),request_id:str|None=None,
    user_id:int|None=Query(None,gt=0),source:Literal['main','openapi','step8']|None=None,
    state:Literal['accepted','running','completed','degraded','failed','budget_blocked','interrupted','manual_required']|None=None,
    start_date:str|None=None,end_date:str|None=None,actor=require_role('super_admin','ai_trainer','observer')):
    if request_id:uuid_value(request_id,(7,))
    return await bounded(lambda:get_service().list(actor,page=page,page_size=page_size,request_id=request_id,
        user_id=user_id,source=source,state=state,start_date=start_date,end_date=end_date))

@router.get('/memory-diagnostics/{execution_id}')
async def detail(execution_id:str,section:Literal['candidates']|None=None,page:int=Query(1,ge=1),
    page_size:int=Query(20,ge=1,le=100),route:Literal['cg','cp','ck','user']|None=None,
    actor=require_role('super_admin','ai_trainer','observer')):
    uuid_value(execution_id,(4,))
    if route and section is None:return ApiResponse.fail(20120,message='section_required')
    return await bounded(lambda:get_service().detail(execution_id,actor,section=section,page=page,page_size=page_size,route=route))

@router.delete('/memory-diagnostics/{execution_id}')
async def delete(execution_id:str,actor=require_role('super_admin','ai_trainer')):
    uuid_value(execution_id,(4,))
    try:return ApiResponse.ok(data=await get_service().delete(execution_id,actor))
    except AdminMemoryError as exc:return response_error(exc)
    except Exception:return ApiResponse.fail(20129,message='persistence_unavailable')
