"""Read-only HTTP projection backed by actual isolated MySQL."""
import os
import pytest
from backend.utils.admin_auth import get_current_admin
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step035_api import (
    build_api, test_five_roles_read_no_writes as check_read,
    test_auth_validation_and_no_mutation_routes as check_denials,
    test_user_token_cannot_authenticate_as_admin as check_user_token,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_mysql_http_five_roles_no_mutation(runtime):
    factory=runtime[0]
    app=await build_api(factory)
    await check_denials(app)
    app.dependency_overrides.pop(get_current_admin)
    await check_user_token(app)
    for role in ('super_admin','ai_trainer','tech_ops','ops_admin','observer'):
        for path in ('dictionary','daily?day=2026-09-19'):
            await check_read(app,factory,role,path)
