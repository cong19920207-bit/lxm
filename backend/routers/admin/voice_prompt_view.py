"""GET-only voice prompt views. No configuration or model operations."""
from fastapi import APIRouter, HTTPException, Response

from backend.schemas.common import ApiResponse
from backend.services.realtime_voice_prompt_view_service import get_prompt_catalog, get_prompt_view
from backend.utils.admin_auth import require_role

router = APIRouter(dependencies=[require_role('super_admin', 'ai_trainer', 'observer')])


@router.get('/prompt-view')
async def prompt_catalog(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return ApiResponse.ok(data=get_prompt_catalog())


@router.get('/prompt-view/{prompt_key}')
async def prompt_detail(prompt_key: str, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        data = get_prompt_view(prompt_key)
    except KeyError:
        raise HTTPException(status_code=404, detail='提示词不存在') from None
    return ApiResponse.ok(data=data)
