"""Real MySQL row-lock race, isolated disposable database only."""
import asyncio
import os
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.config import get_mysql_url
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.models.admin_operation_log import AdminOperationLog
from backend.services.realtime_voice_master_switch_service import realtime_voice_master_switch_service as service
from backend.services.realtime_voice_config_service import VoiceConfigError

@pytest.mark.asyncio
async def test_two_admins_cannot_publish_the_same_version():
    if not os.getenv('MYSQL_DATABASE','').startswith('lxm_voice_switch_test_'):
        pytest.skip('requires an isolated lxm_voice_switch_test_ database')
    engine = create_async_engine(get_mysql_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            for model in (AdminUser, AdminConfig, AdminOperationLog):
                await conn.run_sync(model.__table__.create)
        async with sessions() as db:
            admin = AdminUser(username='switch-race-test',password_hash='unused',role='super_admin')
            db.add(admin)
            db.add(AdminConfig(config_key='voice_call_master_switch',config_value='{"enabled":true}',version=1,is_active=True,is_draft=False))
            db.add(AdminConfig(config_key='voice_call_config',config_value='draft sentinel',version=0,draft_revision=17,is_active=False,is_draft=True))
            await db.commit()
        async def publish():
            async with sessions() as db:
                try:
                    result = await service.publish(db,enabled=False,expected_version=1,admin_user=admin)
                    return result['version']
                except VoiceConfigError as exc:
                    return exc.code
        results = await asyncio.gather(publish(),publish())
        assert sorted(map(str,results)) == ['2','VOICE_MASTER_SWITCH_CONFLICT']
        async with sessions() as db:
            state = await service.get_state(db)
            assert state['enabled'] is False and state['version'] == 2
            logs = (await db.execute(select(AdminOperationLog))).scalars().all()
            assert len(logs) == 1
            draft = (await db.execute(select(AdminConfig).where(AdminConfig.config_key=='voice_call_config'))).scalars().one()
            assert draft.config_value=='draft sentinel' and draft.draft_revision==17 and draft.is_draft
    finally:
        await engine.dispose()
