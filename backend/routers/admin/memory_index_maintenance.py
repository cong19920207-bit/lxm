"""Global maintenance/backfill reads and bounded explicit task retry."""
import os
from typing import Literal
from fastapi import APIRouter,Query
from pydantic import BaseModel,field_validator
from backend.database import async_session_maker
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import require_role
from backend.services.memory_admin_common import uuid_value,AdminMemoryError,response_error
from backend.services.memory_admin_maintenance import MaintenanceService
from backend.routers.admin.memory_diagnostics import bounded

router=APIRouter()
def get_service():return MaintenanceService(async_session_maker,os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip())

class RetryBody(BaseModel):
    request_id:str
    expected_revision:str
    @field_validator('request_id')
    @classmethod
    def request_uuid(cls,value):return uuid_value(value,(7,))
    @field_validator('expected_revision')
    @classmethod
    def revision(cls,value):
        if not value.isascii() or not value.isdigit() or str(int(value))!=value or not 0<int(value)<2**64:raise ValueError('invalid_revision')
        return value

@router.get('/memory-index-maintenance/tasks')
async def tasks(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user_id:int|None=Query(None,gt=0),
    type:Literal['character_global','character_private','character_knowledge','user']|None=None,
    state:Literal['pending','running','retry_wait','manual_required','completed','superseded','source_unverified']|None=None,
    operation:Literal['create','update','delete','index','retry','baseline','batch']|None=None,
    source:Literal['admin','text','voice','system']|None=None,doc_id:str|None=Query(None,min_length=1,max_length=64),
    start_date:str|None=None,end_date:str|None=None,actor=require_role('super_admin','ai_trainer','observer')):
    return await bounded(lambda:get_service().tasks(actor,page=page,page_size=page_size,user_id=user_id,memory_type=type,
        state=state,operation=operation,source=source,doc_id=doc_id,start_date=start_date,end_date=end_date))

@router.get('/memory-index-maintenance/tasks/{task_id}')
async def task_detail(task_id:str,section:Literal['attempts','backfills']|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
    actor=require_role('super_admin','ai_trainer','observer')):
    uuid_value(task_id,(4,))
    return await bounded(lambda:get_service().task_detail(task_id,actor,section=section,page=page,page_size=page_size))

@router.post('/memory-index-maintenance/tasks/{task_id}/retry')
async def retry(task_id:str,body:RetryBody,actor=require_role('super_admin','ai_trainer')):
    uuid_value(task_id,(4,))
    try:
        result=await get_service().retry(task_id,body.model_dump(),actor)
        return ApiResponse(code=result['code'],data=result,message=result.get('reason','success'))
    except AdminMemoryError as exc:return response_error(exc)
    except Exception:return ApiResponse.fail(20129,message='persistence_unavailable')

@router.delete('/memory-index-maintenance/history/{record_id}')
async def delete_history(record_id:str,actor=require_role('super_admin','ai_trainer')):
    if not record_id.isascii() or not record_id.isdigit() or str(int(record_id))!=record_id or not 0<int(record_id)<2**63:
        from fastapi import HTTPException
        raise HTTPException(422,detail='invalid_record_id')
    try:return ApiResponse.ok(data=await get_service().delete_history(record_id,actor))
    except AdminMemoryError as exc:return response_error(exc)
    except Exception:return ApiResponse.fail(20129,message='persistence_unavailable')

@router.get('/memory-index-maintenance/backfills')
async def backfills(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
    state:Literal['pending','running','interrupted','manual_required','completed']|None=None,
    stage:Literal['scan','index','reconcile','catchup']|None=None,start_date:str|None=None,end_date:str|None=None,
    actor=require_role('super_admin','ai_trainer','observer')):
    return await bounded(lambda:get_service().backfills(page=page,page_size=page_size,state=state,stage=stage,start_date=start_date,end_date=end_date))

@router.get('/memory-index-maintenance/backfills/{run_id}')
async def backfill_detail(run_id:str,actor=require_role('super_admin','ai_trainer','observer')):
    uuid_value(run_id,(4,))
    return await bounded(lambda:get_service().backfill_detail(run_id))

@router.get('/memory-index-maintenance/backfills/{run_id}/items')
async def backfill_items(run_id:str,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
    source_class:Literal['standard_kv','legacy_free_text','empty','identity_or_parse_error']|None=Query(None,alias='class'),
    state:Literal['matched','missing','extra','mismatch','unknown','retry_wait','identity_or_parse_error']|None=None,
    actor=require_role('super_admin','ai_trainer','observer')):
    uuid_value(run_id,(4,))
    return await bounded(lambda:get_service().backfill_items(run_id,page=page,page_size=page_size,source_class=source_class,state=state))
