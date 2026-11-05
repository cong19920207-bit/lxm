"""Authenticated pet endpoints; the public introduction has no personal state."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.database import get_db
from sqlalchemy.ext.asyncio import async_sessionmaker
from backend.schemas.common import ApiResponse
from backend.utils.auth_middleware import get_current_user
from backend.services import pet_user_service as service

def private_response(response:Response):
    response.headers['Cache-Control']='private, no-store'
    response.headers['Vary']='Authorization'

router=APIRouter(dependencies=[Depends(private_response)])
class StrictBody(BaseModel):model_config=ConfigDict(extra='forbid')
class NameBody(StrictBody):
    name:str=Field(min_length=1,max_length=128)
    request_key:str=Field(min_length=1,max_length=96)
class AdoptBody(NameBody):acknowledged:bool
class InteractionStart(StrictBody):
    kind:str=Field(max_length=32)
    request_key:str=Field(min_length=1,max_length=96)
class FeedBody(StrictBody):request_key:str=Field(min_length=1,max_length=96)
class JointStart(FeedBody):
    direct:bool=False
    initiator:str=Field(default='user',pattern='^(user|invitation)$')
class JointAccept(StrictBody):resources_ready:bool
class PhotoStart(FeedBody):resources_ready:bool
class SceneSnapshot(StrictBody):
    data_url:str=Field(max_length=3_000_000)
    stage:str=Field(max_length=24)
    record_version:int=Field(ge=1)
    resource_version:str=Field(max_length=64)
class PhotoCapture(JointAccept):snapshot:SceneSnapshot
class InteractionEvidence(StrictBody):
    duration_ms:float=Field(default=0,ge=0,le=120000,allow_inf_nan=False)
    moved:bool=False
    auxiliary:bool=False
    region:str=Field(default='',max_length=16)
class InteractionFinish(StrictBody):
    evidence:InteractionEvidence=Field(default_factory=InteractionEvidence)
    cancel:bool=False

async def respond(db,work):
    try:
        async with db.begin_nested():result=await work
        return ApiResponse.ok(result)
    except PermissionError:raise HTTPException(401,'账号不可用')
    except LookupError:return ApiResponse.fail(20302,data={'reason':'pet_not_found'})
    except service.PetInputError as error:
        code=20305 if isinstance(error,service.PetDisabled) else 20302 if isinstance(error,service.PetUnavailable) else 20303 if isinstance(error,service.PetConflict) else 20301
        return ApiResponse.fail(code,data={'reason':str(error)})

@router.get('/intro')
async def intro(db=Depends(get_db)):
    return ApiResponse.ok(await service.introduction(db))

@router.get('/me')
async def me(user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,service.read_pet(db,user_id))

@router.post('/adopt')
async def adopt(body:AdoptBody,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,service.adopt(db,user_id,**body.model_dump()))

@router.get('/adoption-result')
async def adoption_result(user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,service.read_pet(db,user_id,settle=False))

@router.post('/rename')
async def rename(body:NameBody,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,service.rename(db,user_id,**body.model_dump()))

from backend.services import pet_interactions as interactions

@router.post('/interactions')
async def interaction_start(body:InteractionStart,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,interactions.start(db,user_id,**body.model_dump()))

@router.get('/interaction-requests/{request_key}')
async def interaction_request(request_key:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,interactions.query_request(db,user_id,request_key))

@router.get('/interactions/{attempt_id}')
async def interaction_query(attempt_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,interactions.query(db,user_id,attempt_id))

@router.post('/interactions/{attempt_id}/finish')
async def interaction_finish(attempt_id:str,body:InteractionFinish,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,interactions.finish(db,user_id,attempt_id,**body.model_dump()))

@router.post('/feed')
async def feed(body:FeedBody,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,interactions.feed(db,user_id,request_key=body.request_key))

from backend.services import pet_joint_service as joint

@router.post('/joint/invitations')
async def joint_invite(body:JointStart,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,joint.invite(db,user_id,**body.model_dump()))

@router.post('/joint/{attempt_id}/accept')
async def joint_accept(attempt_id:str,body:JointAccept,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,joint.accept(db,user_id,attempt_id,resources_ready=body.resources_ready))

@router.post('/joint/{attempt_id}/pass')
async def joint_pass(attempt_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,joint.player_pass(db,user_id,attempt_id))

@router.post('/joint/{attempt_id}/resolve')
async def joint_resolve(attempt_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,joint.resolve(db,user_id,attempt_id))

@router.post('/joint/{attempt_id}/cancel')
async def joint_cancel(attempt_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,joint.cancel(db,user_id,attempt_id))

from backend.services import pet_photos as photos
@router.post('/photos/growth-prompt')
async def photo_growth_prompt(user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,photos.claim_growth_prompt(db,user_id))
@router.post('/photos')
async def photo_start(body:PhotoStart,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,photos.start(db,user_id,**body.model_dump()))
@router.post('/photos/{attempt_id}/prepare')
async def photo_prepare(attempt_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,photos.prepare(db,user_id,attempt_id))
@router.post('/photos/{attempt_id}/capture')
async def photo_capture(attempt_id:str,body:PhotoCapture,user_id=Depends(get_current_user),db=Depends(get_db)):
    # The service commits an intent, releases SQL locks for OSS, then fences the result.
    sessions=async_sessionmaker(db.bind,expire_on_commit=False,autoflush=False);await db.rollback()
    return await photo_work(photos.capture(sessions,user_id,attempt_id,**body.model_dump()))

async def photo_work(work):
    try:return ApiResponse.ok(await work)
    except PermissionError:raise HTTPException(401,'账号不可用')
    except LookupError:return ApiResponse.fail(20302,data={'reason':'pet_not_found'})
    except photos.PhotoStorageError:return ApiResponse.fail(20302,data={'reason':'storage_unavailable'})
    except service.PetInputError as error:
        code=20305 if isinstance(error,service.PetDisabled) else 20302 if isinstance(error,service.PetUnavailable) else 20303 if isinstance(error,service.PetConflict) else 20301
        return ApiResponse.fail(code,data={'reason':str(error)})

@router.get('/photos/{attempt_id}')
async def photo_status(attempt_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    sessions=async_sessionmaker(db.bind,expire_on_commit=False,autoflush=False);await db.rollback()
    return await photo_work(photos.photo_status(sessions,user_id,attempt_id))
@router.post('/photos/{attempt_id}/archive')
async def photo_archive(attempt_id:str,body:JointAccept,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,photos.archive(db,user_id,attempt_id,resources_ready=body.resources_ready))
@router.post('/photos/{attempt_id}/cancel')
async def photo_cancel(attempt_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,photos.cancel(db,user_id,attempt_id))

@router.get('/preferences/{key}')
async def preference(key:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    from backend.services.pet_preferences import preference_evidence
    return await respond(db,preference_evidence(db,user_id,key))

from datetime import date
from backend.services import pet_records as records
@router.get('/records')
async def records_daily(day:date|None=None,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,records.daily(db,user_id,day=day))
@router.get('/events/{event_id}')
async def event_detail(event_id:str,origin:str='daily',origin_date:str|None=None,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,records.detail(db,user_id,event_id,origin=origin,origin_date=origin_date))

@router.get('/album')
async def album(cursor:str|None=Query(default=None,max_length=512),limit:int=Query(default=20,ge=1,le=50),user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,records.album(db,user_id,cursor=cursor,limit=limit))

@router.get('/birthday')
async def birthday(user_id=Depends(get_current_user),db=Depends(get_db)):
    from backend.services.pet_birthday import current_birthday
    return await respond(db,current_birthday(db,user_id))


from backend.services import pet_activity as activity
class ViewHeartbeat(StrictBody):
    sequence:int=Field(ge=1)
    foreground:bool
    surface:str=Field(max_length=32)

@router.post('/view-sessions')
async def view_start(user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,activity.begin_view(db,user_id))

@router.post('/view-sessions/{session_id}/heartbeat')
async def view_heartbeat(session_id:str,body:ViewHeartbeat,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,activity.heartbeat(db,user_id,session_id,**body.model_dump()))


@router.get('/expressions/{event_id}')
async def expression(event_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    from backend.services.pet_expression import expression_for_event
    return await respond(db,expression_for_event(db,user_id,event_id))


@router.post('/returns/entry')
async def return_entry(user_id=Depends(get_current_user),db=Depends(get_db)):
    from backend.services.pet_return import enter
    return await respond(db,enter(db,user_id))

@router.get('/returns/{return_id}')
async def return_read(return_id:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    from backend.services.pet_return import read_return
    return await respond(db,read_return(db,user_id,return_id))

@router.get('/rename-requests/{request_key}')
async def rename_request(request_key:str,user_id=Depends(get_current_user),db=Depends(get_db)):
    return await respond(db,service.rename_result(db,user_id,request_key))
