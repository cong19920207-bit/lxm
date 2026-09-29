"""Independent voice switch: transactional publication and config isolation."""
import json
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from tests.test_realtime_voice_step005_config_control import (
    database, client, app, session_factory, role_ids,
)
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.constants.realtime_voice_config import get_default_voice_call_config
from backend.routers.admin.voice_master_switch import router
from backend.services.realtime_voice_master_switch_service import (
    realtime_voice_master_switch_service as service, parse_master_switch_rows,
)
from backend.services.realtime_voice_config_service import VoiceConfigError

app.include_router(router, prefix='/api/admin/voice')
KEY = 'voice_call_master_switch'

async def seed(enabled=False):
    config = get_default_voice_call_config({"version": 1, "content_sha256": "sha256:" + "a" * 64})
    draft = deepcopy(config)
    draft['global']['maintenance_message'] = 'UNPUBLISHED DRAFT'
    async with session_factory() as db:
        db.add_all([
            AdminConfig(config_key=KEY, config_value=json.dumps({'enabled': enabled}), version=1, is_active=True, is_draft=False),
            AdminConfig(config_key='voice_call_config', config_value=json.dumps(config), version=7, is_active=True, is_draft=False),
            AdminConfig(config_key='voice_call_config', config_value=json.dumps(draft), version=0, draft_revision=3, is_active=False, is_draft=True),
        ])
        await db.commit()

async def config_rows():
    async with session_factory() as db:
        rows = (await db.execute(select(AdminConfig).where(AdminConfig.config_key != KEY).order_by(AdminConfig.id))).scalars().all()
        return [(r.id, r.config_key, r.config_value, r.version, r.draft_revision, r.is_active, r.is_draft, r.updated_at, r.updated_by) for r in rows]

@pytest.mark.asyncio
async def test_disable_is_independent_and_stale_write_is_rejected(client, monkeypatch):
    await seed(True)
    before = await config_rows()
    async def never_read_config(*args):
        raise AssertionError('Disable must not depend on voice configuration readiness')
    monkeypatch.setattr(service, '_validate_enable', never_read_config)
    response = await client.post('/api/admin/voice/master-switch/publish', headers={'x-admin-role': 'tech_ops'}, json={'enabled': False, 'expected_version': 1})
    assert response.status_code == 200, response.text
    assert response.json()['data']['enabled'] is False
    assert response.json()['data']['version'] == 2
    assert await config_rows() == before
    stale = await client.post('/api/admin/voice/master-switch/publish', headers={'x-admin-role': 'super_admin'}, json={'enabled': True, 'expected_version': 1})
    assert stale.status_code == 409
    async with session_factory() as db:
        history = (await db.execute(select(AdminConfig).where(AdminConfig.config_key == KEY).order_by(AdminConfig.version))).scalars().all()
        assert [(r.version, r.is_active, r.is_draft) for r in history] == [(1, False, False), (2, True, False)]
        logs = (await db.execute(select(AdminOperationLog).where(AdminOperationLog.module == 'voice_master_switch'))).scalars().all()
        assert len(logs) == 1
        assert json.loads(logs[0].before_value)['enabled'] is True
        assert json.loads(logs[0].after_value)['enabled'] is False

@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin', 'tech_ops', 'ai_trainer', 'ops_admin', 'observer'])
async def test_role_boundary(client, role):
    await seed(True)
    assert (await client.get('/api/admin/voice/master-switch', headers={'x-admin-role':role})).status_code == 200
    result = await client.post('/api/admin/voice/master-switch/publish', headers={'x-admin-role':role}, json={'enabled':False, 'expected_version':1})
    assert result.status_code == (200 if role in ('super_admin', 'tech_ops') else 403)

@pytest.mark.asyncio
async def test_enable_checks_active_only_and_preserves_draft(client, monkeypatch):
    await seed(False)
    before = await config_rows()
    import backend.services.realtime_voice_config_service as config_module
    observed = []
    def validate(key, config):
        observed.append(config['global']['maintenance_message'])
        return []
    async def persona(*args): return None
    async def evidence(*args): return None
    monkeypatch.setattr(config_module, 'validate_trusted_voice_bundle', validate)
    monkeypatch.setattr(config_module, '_validate_published_persona_ref', persona)
    monkeypatch.setattr(config_module.realtime_voice_config_service, '_ensure_all_scope_evidence', evidence)
    result = await client.post('/api/admin/voice/master-switch/publish', headers={'x-admin-role':'super_admin'}, json={'enabled':True,'expected_version':1})
    assert result.status_code == 200, result.text
    assert observed and 'UNPUBLISHED DRAFT' not in observed
    assert await config_rows() == before

@pytest.mark.asyncio
async def test_failure_rolls_back_switch_and_audit(client, monkeypatch):
    await seed(True)
    import backend.services.realtime_voice_master_switch_service as module
    async def failed_log(**kwargs): raise RuntimeError('controlled failure')
    monkeypatch.setattr(module, 'log_operation', failed_log)
    result = await client.post('/api/admin/voice/master-switch/publish', headers={'x-admin-role':'super_admin'}, json={'enabled':False,'expected_version':1})
    assert result.status_code == 503
    result = await client.get('/api/admin/voice/master-switch')
    assert result.json()['data']['enabled'] is True
    assert result.json()['data']['version'] == 1

@pytest.mark.asyncio
async def test_unavailable_and_strict_input(client):
    assert (await client.get('/api/admin/voice/master-switch')).status_code == 503
    await seed()
    for body in ({'enabled':'true','expected_version':1}, {'enabled':True,'expected_version':True}, {'enabled':True,'expected_version':1,'content':{}}):
        assert (await client.post('/api/admin/voice/master-switch/publish', headers={'x-admin-role':'super_admin'}, json=body)).status_code == 422
    async with session_factory() as db:
        db.add(AdminConfig(config_key=KEY,config_value='{"enabled":true}',version=2,is_active=True,is_draft=False))
        await db.commit()
    assert (await client.get('/api/admin/voice/master-switch')).status_code == 503

@pytest.mark.parametrize('value', ['null', '{}', '{"enabled":1}', '{"enabled":true,"extra":1}', 'bad'])
def test_invalid_state_fails_closed(value):
    row = SimpleNamespace(config_key=KEY, config_value=value, version=1, is_active=True, is_draft=False, updated_by=None, updated_at=datetime.utcnow())
    assert parse_master_switch_rows([row]) is None

@pytest.mark.asyncio
async def test_old_global_editor_cannot_change_switch(client):
    await seed()
    before = await config_rows()
    async with session_factory() as db:
        draft = (await db.execute(select(AdminConfig).where(AdminConfig.config_key=='voice_call_config', AdminConfig.is_draft.is_(True)))).scalars().one()
        content = json.loads(draft.config_value)['global']
    content['enabled'] = not content['enabled']
    result = await client.patch('/api/admin/voice/config/config/draft/global', headers={'x-admin-role':'super_admin'}, json={'base_version':7,'draft_revision':3,'content':content})
    assert result.status_code == 400
    assert result.json()['data']['error_code'] == 'VOICE_MASTER_SWITCH_MANAGED'
    assert await config_rows() == before

@pytest.mark.asyncio
async def test_config_publish_and_rollback_leave_master_switch_untouched():
    from tests.test_realtime_voice_step005_config_control import _seed, _admin, _save_changed_section
    from backend.services.realtime_voice_config_service import realtime_voice_config_service as configs
    await _seed()
    async with session_factory() as db:
        db.add(AdminConfig(config_key=KEY,config_value='{"enabled":true}',version=9,is_active=True,is_draft=False))
        await db.commit()
        before = await service.get_state(db)
    await _save_changed_section(config_key='voice_call_config',section='global',role='tech_ops',mutate=lambda c:c.update(soft_stop=True))
    async with session_factory() as db:
        await configs.publish(db,config_key='voice_call_config',confirm_text='CONFIRM',change_note='isolation test',admin_user=await _admin(db,'tech_ops'))
        assert await service.get_state(db) == before
        await configs.rollback(db,config_key='voice_call_config',version=1,confirm_text='CONFIRM',change_note='isolation rollback',admin_user=await _admin(db,'tech_ops'))
        assert await service.get_state(db) == before

@pytest.mark.asyncio
async def test_enable_readiness_failure_preserves_off_state(client, monkeypatch):
    from tests.test_realtime_voice_step005_config_control import _seed
    await _seed()
    async with session_factory() as db:
        db.add(AdminConfig(config_key=KEY,config_value='{"enabled":false}',version=1,is_active=True,is_draft=False))
        await db.commit()
    monkeypatch.delenv('DOUBAO_S2S_ACCESS_KEY',raising=False)
    before = await config_rows()
    result = await client.post('/api/admin/voice/master-switch/publish',headers={'x-admin-role':'tech_ops'},json={'enabled':True,'expected_version':1})
    assert result.status_code == 400
    assert result.json()['data']['error_code'] == 'VOICE_CONFIG_CREDENTIAL_MISSING'
    assert (await client.get('/api/admin/voice/master-switch')).json()['data']['enabled'] is False
    assert await config_rows() == before
