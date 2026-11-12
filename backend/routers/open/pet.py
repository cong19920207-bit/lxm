"""External participation in an already adopted pet, using the account's API key."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants.pet import (
    PET_ACTION_DISABLED, PET_CONFIG_INVALID, PET_REQUEST_CONFLICT, PET_UNAVAILABLE,
)
from backend.database import get_db
from backend.routers.pet import private_response
from backend.schemas.common import ApiResponse
from backend.services import pet_interactions, pet_records, pet_user_service
from backend.services.pet_expression import expression_for_event
from backend.utils.open_api_auth import get_current_user_by_api_key

router = APIRouter(prefix='/api/open/v1/pet', tags=['open-pet'],
                   dependencies=[Depends(private_response)])
ADOPTION_PATH = '/pages/pet.html'
ADOPTION_MESSAGE = '请先到平台领养小狗'


class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid')


class FeedBody(StrictBody):
    request_key: str = Field(min_length=1, max_length=96)


class InteractionStart(FeedBody):
    kind: Literal['touch', 'play']


class InteractionFinish(StrictBody):
    cancel: bool = False


async def respond(db, work):
    try:
        async with db.begin_nested():
            result = await work
        return ApiResponse.ok(result)
    except PermissionError:
        raise HTTPException(401, '账号不可用') from None
    except LookupError as error:
        reason = str(error)
        if reason == 'pet_not_found':
            return ApiResponse.fail(PET_UNAVAILABLE, message=ADOPTION_MESSAGE,
                                    data={'reason':reason, 'adoption_path':ADOPTION_PATH})
        return ApiResponse.fail(PET_UNAVAILABLE, data={'reason':reason})
    except pet_user_service.PetInputError as error:
        code = (PET_ACTION_DISABLED if isinstance(error, pet_user_service.PetDisabled)
                else PET_UNAVAILABLE if isinstance(error, pet_user_service.PetUnavailable)
                else PET_REQUEST_CONFLICT if isinstance(error, pet_user_service.PetConflict)
                else PET_CONFIG_INVALID)
        return ApiResponse.fail(code, data={'reason':str(error)})


@router.get('/me')
async def me(user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    result = await respond(db, pet_user_service.read_pet(db, user_id))
    if result.code == 0:
        pet = result.data
        result.data = {'adopted':pet is not None, 'pet':pet, 'adoption_path':None if pet is not None else ADOPTION_PATH}
        if pet is None:
            result.message = ADOPTION_MESSAGE
    return result


@router.post('/feed')
async def feed(body: FeedBody, user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_interactions.feed(db, user_id, request_key=body.request_key))


@router.post('/interactions')
async def start(body: InteractionStart, user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_interactions.start(db, user_id, **body.model_dump(), completion_mode='programmatic'))


@router.get('/interaction-requests/{request_key}')
async def request_result(request_key: str = Path(min_length=1, max_length=96),
                         user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_interactions.query_request(db, user_id, request_key))


@router.get('/interaction-requests')
async def request_result_by_key(request_key: str = Query(min_length=1, max_length=96),
                                user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_interactions.query_request(db, user_id, request_key))


@router.get('/interactions/{attempt_id}')
async def interaction(attempt_id: str = Path(min_length=1, max_length=36),
                      user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_interactions.query(db, user_id, attempt_id))


@router.post('/interactions/{attempt_id}/finish')
async def finish(body: InteractionFinish, attempt_id: str = Path(min_length=1, max_length=36),
                 user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_interactions.finish(db, user_id, attempt_id, cancel=body.cancel, completion_mode='programmatic'))


@router.get('/records')
async def records(day: date | None = None, user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_records.daily(db, user_id, day=day))


@router.get('/events/{event_id}')
async def event(event_id: str = Path(min_length=1, max_length=36), origin: Literal['daily', 'album'] = 'daily',
                origin_date: date | None = None, user_id: int = Depends(get_current_user_by_api_key),
                db: AsyncSession = Depends(get_db)):
    return await respond(db, pet_records.detail(db, user_id, event_id, origin=origin,
                                                origin_date=origin_date.isoformat() if origin_date else None))


@router.get('/expressions/{event_id}')
async def expression(event_id: str = Path(min_length=1, max_length=36),
                     user_id: int = Depends(get_current_user_by_api_key), db: AsyncSession = Depends(get_db)):
    return await respond(db, expression_for_event(db, user_id, event_id))
