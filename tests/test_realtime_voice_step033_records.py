from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest


def call_row(**changes):
    values = dict(call_id='call-1', deleted_at=None, deletion_fence_at=None,
        transcript_expires_at=datetime.utcnow()+timedelta(days=1))
    return SimpleNamespace(**(values | changes))


def turn_row(**changes):
    values = dict(id=1, call_id='call-1', turn_index=1, user_text_final='用户最终文字',
        assistant_text_effective='实际播放文字', assistant_text_generated='禁止公开生成正文',
        effective_text_evidence='full', assistant_interrupted=False, turn_status='finalized',
        memory_status='success', user_content_safety_status='passed', assistant_content_safety_status='passed',
        user_crisis_status='passed', assistant_crisis_status='passed',
        effective_text_cleared_at=None, generated_text_cleared_at=None, content_clear_reason=None,
        effective_text_expires_at=datetime.utcnow()+timedelta(days=1),
        generated_text_expires_at=datetime.utcnow()+timedelta(days=1))
    return SimpleNamespace(**(values | changes))


@pytest.mark.parametrize('blocked', ['expired', 'cleared', 'deleted', 'fenced', 'crisis', 'suspected'])
def test_effective_projection_never_leaks_expired_deleted_or_crisis_text(blocked):
    from backend.services.realtime_voice_record_service import effective_turn
    call, turn = call_row(), turn_row()
    if blocked == 'expired': turn.effective_text_expires_at = datetime.utcnow()-timedelta(seconds=1)
    if blocked == 'cleared': turn.effective_text_cleared_at = datetime.utcnow()
    if blocked == 'deleted': call.deleted_at = datetime.utcnow()
    if blocked == 'fenced': call.deletion_fence_at = datetime.utcnow()
    if blocked == 'crisis': turn.user_crisis_status = 'matched'
    if blocked == 'suspected': turn.assistant_crisis_status = 'suspected'
    result = effective_turn(call, turn, now=datetime.utcnow())
    assert result['user_text_final'] is None and result['assistant_text_effective'] is None
    assert 'assistant_text_generated' not in result and 'reasoning' not in str(result)


def test_effective_export_schema_has_only_authorized_fields():
    from backend.services.realtime_voice_record_service import effective_turn, export_turn
    call, turn = call_row(), turn_row()
    result = effective_turn(call, turn, now=datetime.utcnow())
    assert result['user_text_final'] == '用户最终文字'
    assert export_turn(result) == {k: result[k] for k in (
        'call_id','turn_index','user_text_final','assistant_text_effective','effective_text_expires_at')}


from tests.test_realtime_voice_step021_cards import card_env, memory_env, storage


async def r04_application(factory, monkeypatch, role='super_admin', token_kind='valid'):
    from fastapi import FastAPI
    from sqlalchemy import select
    from backend.database import get_db
    from backend.models.admin_user import AdminUser
    from backend.routers.admin.voice_records import router
    from backend.services.realtime_voice_metric_service import VoiceMetrics
    from tests.test_realtime_voice_step031_metrics import CounterCache
    import backend.utils.admin_auth as auth

    monkeypatch.setattr(auth, 'get_admin_jwt_secret', lambda: 'R04-synthetic-signing-key-for-tests-only-0123456789')
    async with factory() as db:
        admin = await db.scalar(select(AdminUser).where(AdminUser.id == 1))
        admin.role = role
        admin.is_active = token_kind != 'disabled'
        admin.is_locked = token_kind == 'locked'
        admin.token_version = 2 if token_kind == 'revoked' else 0
        await db.commit()
    token = auth.create_admin_token(1, role, 0)
    if token_kind == 'invalid':
        token = 'not-a-valid-token'
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    sink = CounterCache()
    app.state.voice_metrics = VoiceMetrics(sink)

    async def session():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = session
    headers = {} if token_kind == 'missing' else {'Authorization': 'Bearer '+token}
    return app, headers, sink


async def r04_logs(factory):
    import json
    from sqlalchemy import select
    from backend.models.admin_operation_log import AdminOperationLog
    async with factory() as db:
        rows = (await db.scalars(select(AdminOperationLog).order_by(AdminOperationLog.id))).all()
        return [dict(id=row.id, admin_user_id=row.admin_user_id, created_at=row.created_at,
                     action=row.action, target=json.loads(row.target_description),
                     payload=json.loads(row.after_value) if row.after_value else None) for row in rows]


@pytest.mark.asyncio
@pytest.mark.parametrize('empty', [False, True])
async def test_r04_list_records_one_safe_request_summary(card_env, monkeypatch, empty):
    from httpx import ASGITransport, AsyncClient
    factory, call_id = card_env
    app, headers, _ = await r04_application(factory, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=headers) as client:
        response = await client.get('/api/admin/voice/calls', params={
            'user_id': 1, 'status': 'ended' if empty else 'connected', 'page_size': 10,
            'started_from': '2020-01-01T08:00:00+08:00', 'private_note': 'R04_PRIVATE_BODY'})
    assert response.status_code == 200
    logs = await r04_logs(factory)
    summaries = [row for row in logs if (row['payload'] or {}).get('kind') == 'request']
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary['admin_user_id'] == 1 and summary['created_at'] is not None
    data = summary['payload']
    assert data['schema_version'] == 1 and data['result'] == 'success' and data['http_status'] == 200
    assert data['permission'] == 'voice_calls.read' and data['failure_category'] is None
    assert data['filters'] == {'user_id': 1, 'status': 'ended' if empty else 'connected',
                               'page': 1, 'page_size': 10, 'audit_view': False,
                               'started_from': '2020-01-01T00:00:00'}
    assert 'R04_PRIVATE_BODY' not in str(logs) and 'private_note' not in str(logs)
    references = [row for row in logs if (row['payload'] or {}).get('kind') == 'call_reference']
    assert [row['target'] for row in references] == ([] if empty else [{'call_id': call_id}])
    assert all(row['payload']['request_id'] == data['request_id'] for row in references)


@pytest.mark.asyncio
async def test_r04_job_metadata_audit_uses_its_own_permission(card_env, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    factory, call_id = card_env
    app, headers, _ = await r04_application(factory, monkeypatch, 'tech_ops')
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=headers) as client:
        metadata = await client.get(f'/api/admin/voice/calls/{call_id}/jobs')
        transcript = await client.get(f'/api/admin/voice/calls/{call_id}/turns')
    assert metadata.status_code == 200 and transcript.status_code == 403
    summaries = [row['payload'] for row in await r04_logs(factory) if row['payload']['kind'] == 'request']
    assert [(row['permission'], row['result']) for row in summaries] == [
        ('voice_jobs.read', 'success'), ('voice_transcript.read', 'rejected')]


@pytest.mark.asyncio
async def test_r04_export_keeps_all_call_links_and_audit_lookup(card_env, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from tests.test_realtime_voice_step009_ops import add_call, StateCache
    factory, call_id = card_env
    other_id = await add_call(factory, 'connected', StateCache())
    app, headers, _ = await r04_application(factory, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=headers) as client:
        response = await client.post('/api/admin/voice/calls/export', json={'call_ids':[call_id, other_id, call_id]})
        assert response.status_code == 200
        logs = await r04_logs(factory)
        summaries = [r for r in logs if (r['payload'] or {}).get('kind') == 'request']
        assert len(summaries) == 1 and len(logs) == 3
        assert summaries[0]['payload']['filters']['call_ids'] == sorted([call_id, other_id])
        assert {r['target']['call_id'] for r in logs if 'call_id' in r['target']} == {call_id, other_id}
        for target in (call_id, other_id):
            audit = await client.get(f'/api/admin/voice/calls/{target}/audit')
            assert sum(item['action'] == 'export' for item in audit.json()['data']['items']) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('case, status, category', [
    ('page', 422, 'invalid_request'), ('deleted', 422, 'invalid_request'),
    ('missing', 404, 'not_found'), ('missing_export', 404, 'not_found'),
    ('body', 422, 'invalid_request'), ('malformed_json', 422, 'invalid_request'),
    ('projection', 500, 'projection_mismatch'),
])
async def test_r04_failed_requests_persist_safe_audit(card_env, monkeypatch, case, status, category):
    from httpx import ASGITransport, AsyncClient
    from tests.test_realtime_voice_step028_jobs import add_turn
    import backend.routers.admin.voice_records as records
    factory, call_id = card_env
    await add_turn(factory, call_id, user_text_final='R04_PRIVATE_BODY')
    app, headers, sink = await r04_application(factory, monkeypatch)
    if case == 'projection':
        original = records.export_turn
        monkeypatch.setattr(records, 'export_turn', lambda item: {**original(item), 'user_text_final':'R04_WRONG_PROJECTION'})
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test', headers=headers) as client:
        if case == 'page': response = await client.get('/api/admin/voice/calls?page=0')
        elif case == 'deleted': response = await client.get('/api/admin/voice/calls?deleted=true')
        elif case == 'missing': response = await client.get('/api/admin/voice/calls/missing-call/config')
        elif case == 'malformed_json': response = await client.post('/api/admin/voice/calls/export', content='{broken:R04_PRIVATE_BODY', headers={'Content-Type':'application/json'})
        else:
            body = {'call_ids': ['missing-call'] if case == 'missing_export' else [call_id]}
            if case == 'body': body['unexpected'] = 'R04_PRIVATE_BODY'
            response = await client.post('/api/admin/voice/calls/export', json=body)
    assert response.status_code == status
    logs = await r04_logs(factory)
    summaries = [r for r in logs if (r['payload'] or {}).get('kind') == 'request']
    assert len(summaries) == 1
    data = summaries[0]['payload']
    assert data['failure_category'] == category and data['http_status'] == status
    assert data['result'] == ('failure' if status == 500 else 'rejected')
    assert 'R04_PRIVATE_BODY' not in str(logs) and 'R04_WRONG_PROJECTION' not in str(logs)
    assert 'Authorization' not in str(logs) and headers['Authorization'] not in str(logs)
    assert any(event[0] == 'voice.admin_record.audit' for batch in sink.batches for event in batch)


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin', 'ops_admin', 'observer', 'tech_ops', 'ai_trainer'])
@pytest.mark.parametrize('operation', ['view', 'export', 'debug'])
async def test_r04_real_auth_role_denials_are_audited(card_env, monkeypatch, role, operation):
    from httpx import ASGITransport, AsyncClient
    factory, call_id = card_env
    app, headers, _ = await r04_application(factory, monkeypatch, role)
    allowed = role in {'view': {'super_admin','ops_admin','observer'}, 'export': {'super_admin','ops_admin'}, 'debug': {'super_admin'}}[operation]
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=headers) as client:
        if operation == 'export': response = await client.post('/api/admin/voice/calls/export', json={'call_ids':[call_id]})
        else: response = await client.get(f'/api/admin/voice/calls/{call_id}/'+('turns' if operation == 'view' else 'debug'))
    assert response.status_code == (200 if allowed else 403)
    summaries = [r for r in await r04_logs(factory) if (r['payload'] or {}).get('kind') == 'request']
    assert len(summaries) == 1 and summaries[0]['admin_user_id'] == 1
    assert summaries[0]['payload']['result'] == ('success' if allowed else 'rejected')
    assert summaries[0]['payload']['failure_category'] == (None if allowed else 'forbidden')


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('model', 'R04_PRIVATE_MODEL'), ('provider', 'R04_PRIVATE_PROVIDER'),
                                       ('model', 'R04_PRIVATE_LONG'*20), ('status', 'R04_PRIVATE_STATUS'),
                                       ('page', 'R04_PRIVATE_PAGE')])
async def test_r04_untrusted_filters_are_hashed_or_omitted(card_env, monkeypatch, field, value):
    import hashlib
    from httpx import ASGITransport, AsyncClient
    factory, _ = card_env
    app, headers, _ = await r04_application(factory, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=headers) as client:
        response = await client.get('/api/admin/voice/calls', params={field:value, 'unknown':'R04_PRIVATE_EXTRA'})
    assert response.status_code == (422 if field == 'page' else 200)
    logs = await r04_logs(factory)
    data = next(row['payload'] for row in logs if row['payload']['kind'] == 'request')
    assert 'R04_PRIVATE' not in str(logs) and 'unknown' not in str(logs)
    if field in {'model','provider'} and len(value) <= 128:
        assert data['filters'][field] == {'sha256':hashlib.sha256(value.encode()).hexdigest()}
    else:
        assert field not in data['filters'] and field in data['omitted_filter_fields']


@pytest.mark.asyncio
async def test_r04_bulk_rejection_keeps_bounded_targets(card_env, monkeypatch):
    import json
    from httpx import ASGITransport, AsyncClient
    factory, _ = card_env
    app, headers, _ = await r04_application(factory, monkeypatch)
    ids = [('x'*60)+f'{index:04}' for index in range(100)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=headers) as client:
        response = await client.post('/api/admin/voice/calls/export', json={'call_ids':ids})
    assert response.status_code == 404
    logs = await r04_logs(factory)
    assert len(logs) == 101
    assert sum(row['payload']['kind'] == 'request' for row in logs) == 1
    assert all(len(json.dumps(row['target'])) < 500 for row in logs)
    assert {row['target']['call_id'] for row in logs if row['payload']['kind'] == 'call_reference'} == set(ids)


@pytest.mark.asyncio
@pytest.mark.parametrize('token_kind', ['missing', 'invalid', 'revoked', 'disabled', 'locked'])
async def test_r04_invalid_identity_never_creates_operator_audit(card_env, monkeypatch, token_kind):
    from httpx import ASGITransport, AsyncClient
    factory, _ = card_env
    app, headers, _ = await r04_application(factory, monkeypatch, token_kind=token_kind)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=headers) as client:
        response = await client.get('/api/admin/voice/calls')
    assert response.status_code == 401 and await r04_logs(factory) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['query', 'audit_once', 'audit_always'])
async def test_r04_failed_transaction_uses_independent_audit(card_env, monkeypatch, failure):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    factory, call_id = card_env
    app, headers, sink = await r04_application(factory, monkeypatch)
    attempts = 0

    def fail_sql(conn, cursor, statement, parameters, context, executemany):
        nonlocal attempts
        target = ('FROM voice_call ' in statement or 'FROM voice_call\n' in statement) if failure == 'query' else statement.startswith('INSERT INTO admin_operation_logs')
        if target:
            attempts += 1
            if failure == 'audit_always' or attempts == 1:
                raise OperationalError('R04_PRIVATE_SQL', {}, Exception('R04_PRIVATE_ERROR'))

    engine = factory.kw['bind'].sync_engine
    event.listen(engine, 'before_cursor_execute', fail_sql)
    try:
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test', headers=headers) as client:
            response = await client.get(f'/api/admin/voice/calls/{call_id}/config')
        assert response.status_code == 500 and 'config_snapshot' not in response.text
    finally:
        event.remove(engine, 'before_cursor_execute', fail_sql)
    logs = await r04_logs(factory)
    if failure == 'audit_always':
        assert logs == []
        assert any(event == ('voice.admin_record.audit', {'action':'view','result':'failure'}, 1) for batch in sink.batches for event in batch)
    else:
        summaries = [r for r in logs if (r['payload'] or {}).get('kind') == 'request']
        assert len(summaries) == 1
        assert summaries[0]['payload']['failure_category'] == ('database_error' if failure == 'query' else 'audit_unavailable')
        assert summaries[0]['payload']['result'] == 'failure'
    assert 'R04_PRIVATE' not in str(logs)


@pytest.mark.parametrize('role', ['super_admin', 'tech_ops', 'ops_admin', 'observer', 'ai_trainer'])
def test_config_snapshot_projection_does_not_mutate_frozen_input(monkeypatch, role):
    from copy import deepcopy
    from backend.services.realtime_voice_config_service import project_voice_snapshot_for_role

    monkeypatch.setenv('R02_SYNTHETIC_ACCESS_KEY', 'R02_SYNTHETIC_SECRET')
    snapshot = {'s2s': {'credential_ref': 'R02_SYNTHETIC_ACCESS_KEY',
                       'credential_revision_ref': 'R02_PRIVATE_REVISION'},
                'nested': [{'credential_revision_ref': 'R02_PRIVATE_REVISION', 'status': 'verified'}]}
    original = deepcopy(snapshot)
    result = project_voice_snapshot_for_role(snapshot, role)
    expected_s2s = {'credential_configured': True}
    if role in {'super_admin', 'tech_ops'}:
        expected_s2s['credential_ref'] = 'R02_SYNTHETIC_ACCESS_KEY'
    assert result == {'s2s': expected_s2s, 'nested': [{'credential_configured': False, 'status': 'verified'}]}
    assert snapshot == original
    result['nested'][0]['status'] = 'changed'
    result['s2s']['credential_configured'] = False
    assert snapshot == original


def config_app(factory, role):
    from fastapi import FastAPI
    from backend.database import get_db
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin

    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    if role is not None:
        app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(
            id=1, username='test', role=role)

    async def session():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin', 'ops_admin', 'observer', 'ai_trainer', 'tech_ops', None])
@pytest.mark.parametrize('configured', [True, False])
async def test_config_snapshot_credential_role_projection(card_env, monkeypatch, role, configured):
    from copy import deepcopy
    import json
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from backend.models.admin_operation_log import AdminOperationLog
    from backend.models.realtime_voice import VoiceCall

    ref = 'R02_SYNTHETIC_ACCESS_KEY'
    if configured:
        monkeypatch.setenv(ref, 'R02_SYNTHETIC_SECRET')
    else:
        monkeypatch.delenv(ref, raising=False)
    credentials = {'credential_ref': ref, 'credential_revision_ref': 'R02_PRIVATE_REVISION',
                   'api_key': 'R02_SYNTHETIC_SECRET'}
    snapshot = {'config_version': 7, 'config_content_sha256': 'config-content-hash',
                'script_version': 3, 'script_content_sha256': 'script-content-hash',
                'resolved_config': {'s2s': {**credentials, 'model_version': 'test-model'}},
                'resolved_script': {'memory': {'prompt_template': 'unchanged prompt'}}}
    # Defensive nested case; current capability schema does not emit credentials.
    capability = {'dynamic_context_update': {'status': 'verified',
        'evidence_fingerprint': 'capability-fingerprint', 'nested': [deepcopy(credentials)]}}
    factory, call_id = card_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        call.config_snapshot, call.capability_snapshot = deepcopy(snapshot), deepcopy(capability)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=config_app(factory, role)), base_url='http://test') as client:
        response = await client.get(f'/api/admin/voice/calls/{call_id}/config')
    allowed = role in {'super_admin', 'ops_admin', 'observer'}
    assert response.status_code == (200 if allowed else 401 if role is None else 403)
    assert 'R02_SYNTHETIC_SECRET' not in response.text
    assert 'R02_PRIVATE_REVISION' not in response.text
    if role != 'super_admin':
        assert ref not in response.text
        assert 'credential_ref' not in response.text
    if allowed:
        assert response.headers['cache-control'] == 'no-store'
        expected_credential = {'credential_configured': configured, 'api_key': '[REDACTED]'}
        if role == 'super_admin':
            expected_credential['credential_ref'] = ref
        expected_snapshot = deepcopy(snapshot)
        expected_snapshot['resolved_config']['s2s'] = {**expected_credential, 'model_version': 'test-model'}
        expected_capability = deepcopy(capability)
        expected_capability['dynamic_context_update']['nested'] = [expected_credential]
        assert response.json()['data'] == {'call_id': call_id, 'config_snapshot': expected_snapshot,
                                           'capability_snapshot': expected_capability}
    async with factory() as db:
        call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert call.config_snapshot == snapshot and call.capability_snapshot == capability
        logs = (await db.scalars(select(AdminOperationLog))).all()
        assert len(logs) == (2 if allowed else 0)  # one request + one call reference
        if allowed:
            assert logs[0].action == 'read_config' and logs[0].module == 'voice_calls'
            assert sum(json.loads(row.after_value)['kind'] == 'request' for row in logs) == 1
            assert any(json.loads(row.target_description) == {'call_id': call_id} for row in logs)
            assert all(value not in str((logs[0].target_description, logs[0].before_value, logs[0].after_value))
                       for value in (ref, 'R02_PRIVATE_REVISION', 'R02_SYNTHETIC_SECRET'))


@pytest.mark.asyncio
@pytest.mark.parametrize('snapshot, capability, expected', [
    ({}, {}, {}),
    (None, None, {}),
    ({'config_version': 1, 'resolved_config': None}, None, {'config_version': 1, 'resolved_config': None}),
    ({'resolved_config': {'s2s': {}}}, {}, {'resolved_config': {'s2s': {'credential_configured': False}}}),
    ({'resolved_config': {'s2s': {'credential_ref': None, 'credential_revision_ref': None}}}, {},
     {'resolved_config': {'s2s': {'credential_configured': False}}}),
])
async def test_config_snapshot_legacy_empty_compatibility(card_env, snapshot, capability, expected):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from backend.models.realtime_voice import VoiceCall

    factory, call_id = card_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        call.config_snapshot, call.capability_snapshot = snapshot, capability
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=config_app(factory, 'observer')), base_url='http://test') as client:
        response = await client.get(f'/api/admin/voice/calls/{call_id}/config')
    assert response.status_code == 200
    assert response.json()['data']['config_snapshot'] == expected
    assert response.json()['data']['capability_snapshot'] == capability


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['insert', 'commit'])
async def test_config_snapshot_audit_failure_returns_no_data(card_env, failure):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import event, select, func
    from sqlalchemy.orm import Session
    from backend.models.admin_operation_log import AdminOperationLog
    from backend.models.realtime_voice import VoiceCall

    factory, call_id = card_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        call.config_snapshot = {'resolved_script': {'prompt': 'R02_PRIVATE_SNAPSHOT_BODY'}}
        await db.commit()

    def fail(*args):
        raise RuntimeError('synthetic audit failure')

    target, name = (AdminOperationLog, 'before_insert') if failure == 'insert' else (Session, 'before_commit')
    event.listen(target, name, fail)
    try:
        transport = ASGITransport(app=config_app(factory, 'observer'), raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get(f'/api/admin/voice/calls/{call_id}/config')
        assert response.status_code == 500
        assert 'R02_PRIVATE_SNAPSHOT_BODY' not in response.text and 'config_snapshot' not in response.text
    finally:
        event.remove(target, name, fail)
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(AdminOperationLog)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin','ops_admin','observer','ai_trainer','tech_ops'])
@pytest.mark.parametrize('export', [False, True])
async def test_record_role_matrix_and_audit(card_env, role, export):
    import json
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select, func
    from backend.database import get_db
    from backend.models.admin_operation_log import AdminOperationLog
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory, call_id = card_env
    await add_turn(factory, call_id)
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=1, username='test', role=role)
    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    allowed = role in (('super_admin','ops_admin') if export else ('super_admin','ops_admin','observer'))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = (await client.post('/api/admin/voice/calls/export', json={'call_ids':[call_id]}) if export
            else await client.get(f'/api/admin/voice/calls/{call_id}/turns'))
    assert response.status_code == (200 if allowed else 403)
    async with factory() as db:
        count = await db.scalar(select(func.count()).select_from(AdminOperationLog))
        assert count == (2 if allowed else 0)  # one request + one call reference
    if allowed:
        assert response.headers['cache-control'] == 'no-store'
        result = response.json()
        assert 'reasoning' not in json.dumps(result) and 'assistant_text_generated' not in json.dumps(result)
        assert result['data']['items'][0]['user_text_final'] == '下月去日本'


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin','ops_admin','observer','ai_trainer','tech_ops'])
async def test_debug_role_expiry_and_each_read_audit(card_env, role):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select, func
    from backend.database import get_db
    from backend.models.admin_operation_log import AdminOperationLog
    from backend.models.realtime_voice import VoiceCall, VoiceCallTurn
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory, call_id = card_env
    await add_turn(factory, call_id, assistant_text_generated='完整调试正文',
                   generated_text_expires_at=datetime.utcnow()+timedelta(days=1))
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.summary_reasoning = '内部判断依据'
        call.reasoning_expires_at = datetime.utcnow()+timedelta(days=1)
        await db.commit()
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=1, username='test', role=role)
    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        first = await client.get(f'/api/admin/voice/calls/{call_id}/debug')
        assert first.status_code == (200 if role == 'super_admin' else 403)
        if role != 'super_admin':
            async with factory() as db:
                assert await db.scalar(select(func.count()).select_from(AdminOperationLog)) == 0
            return
        assert first.json()['data']['reasoning'] == '内部判断依据'
        assert first.json()['data']['items'][0]['assistant_text_generated'] == '完整调试正文'
        async with factory() as db:
            call = await db.scalar(select(VoiceCall))
            call.reasoning_expires_at = datetime.utcnow()-timedelta(seconds=1)
            turn = await db.scalar(select(VoiceCallTurn))
            turn.generated_text_expires_at = datetime.utcnow()-timedelta(seconds=1)
            await db.commit()
        second = await client.get(f'/api/admin/voice/calls/{call_id}/debug')
        assert second.json()['data']['reasoning'] is None
        assert second.json()['data']['items'][0]['assistant_text_generated'] is None
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(AdminOperationLog)) == 4
        logs = (await db.scalars(select(AdminOperationLog))).all()
        assert all('内部判断依据' not in str(log.target_description) for log in logs)


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin','ops_admin','observer','ai_trainer','tech_ops'])
async def test_jobs_metadata_has_no_extraction_body(card_env, role):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from backend.database import get_db
    from backend.models.realtime_voice import VoiceMemoryJob
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory, call_id = card_env
    turn_id = await add_turn(factory, call_id)
    async with factory() as db:
        db.add(VoiceMemoryJob(call_id=call_id, turn_id=turn_id, turn_index=1,
            pipeline_version='voice_memory_v1', status='failed', attempt_count=2,
            fail_reason='SENTINEL_PRIVATE_CONTENT', extraction_snapshot={'private':'SENTINEL_PRIVATE_CONTENT'}))
        await db.commit()
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=1, username='test', role=role)
    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get(f'/api/admin/voice/calls/{call_id}/jobs?kind=memory')
    assert response.status_code == (403 if role=='ai_trainer' else 200)
    assert 'SENTINEL_PRIVATE_CONTENT' not in response.text and 'extraction_snapshot' not in response.text
    if role != 'ai_trainer':
        assert response.json()['data']['items'][0]['attempt_count'] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin','ops_admin','observer','ai_trainer','tech_ops'])
async def test_summary_retry_http_uses_existing_service_and_role_boundary(card_env, role):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from backend.database import Base, get_db
    from backend.models.realtime_voice import VoiceCall, VoicePostprocessJob
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory, call_id = card_env
    await add_turn(factory, call_id)
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[VoicePostprocessJob.__table__])
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.status, call.summary_status = 'ended', 'failed'
        job = VoicePostprocessJob(call_id=call_id, job_type='call_summary',status='failed',
            attempt_count=2,fail_reason='model_unavailable')
        db.add(job)
        await db.commit()
        job_id = job.id
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=1, username='test', role=role)
    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    allowed = role in {'super_admin','tech_ops'}
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(f'/api/admin/voice/summary-jobs/{job_id}/retry')
        if role == 'super_admin':
            audit = await client.get(f'/api/admin/voice/calls/{call_id}/audit')
            assert any(item['action']=='retry' for item in audit.json()['data']['items'])
    assert response.status_code == (200 if allowed else 403)
    async with factory() as db:
        job = await db.get(VoicePostprocessJob, job_id)
        assert job.status == ('pending' if allowed else 'failed')
        assert job.attempt_count == 2
        if role == 'super_admin':
            await db.delete(job)
            await db.commit()
    if role == 'super_admin':
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            audit = await client.get(f'/api/admin/voice/calls/{call_id}/audit')
            assert any(item['action']=='retry' for item in audit.json()['data']['items'])


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin','ops_admin','observer','ai_trainer','tech_ops'])
async def test_list_filters_and_deleted_audit_boundary(card_env, role):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from backend.database import get_db
    from backend.models.realtime_voice import VoiceCall
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    factory, call_id = card_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.provider = 'doubao'
        call.config_snapshot = {'config_version':7,'resolved_config':{'s2s':{'model_version':'example'}}}
        await db.commit()
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=1, username='test', role=role)
    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/admin/voice/calls?provider=doubao&model=example&config_version=7&user_id=1')
        assert response.status_code == (200 if role in {'super_admin','ops_admin','observer'} else 403)
        if response.status_code != 200: return
        assert response.json()['data']['total'] == 1
        assert (await client.get('/api/admin/voice/calls?model=other')).json()['data']['total'] == 0
        assert (await client.get('/api/admin/voice/calls?deleted=true')).status_code == 422
        async with factory() as db:
            call = await db.scalar(select(VoiceCall))
            call.deleted_at = datetime.utcnow()
            call.call_summary = '删除后不能读取'
            await db.commit()
        assert (await client.get('/api/admin/voice/calls')).json()['data']['total'] == 0
        response = await client.get('/api/admin/voice/calls?audit_view=true&deleted=true')
        assert response.json()['data']['total'] == 1
        assert '删除后不能读取' not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin','ops_admin','observer','ai_trainer','tech_ops'])
@pytest.mark.parametrize('tab', ['usage','audit','config'])
async def test_record_metadata_tabs_role_and_projection(card_env, role, tab):
    import json
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from backend.database import get_db
    from backend.models.admin_operation_log import AdminOperationLog
    from backend.models.realtime_voice import VoiceCall
    from sqlalchemy import select
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    factory, call_id = card_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.config_snapshot = {'config_version':7,'resolved_config':{'api_key':'SENTINEL_PRIVATE_AUDIT'}}
        db.add(AdminOperationLog(admin_user_id=1, admin_username='test', module='voice_calls',
            action='read_debug', target_description=json.dumps({'call_id':call_id}),
            after_value='SENTINEL_PRIVATE_AUDIT'))
        await db.commit()
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=1, username='test', role=role)
    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get(f'/api/admin/voice/calls/{call_id}/{tab}')
    assert response.status_code == (200 if role in {'super_admin','ops_admin','observer'} else 403)
    assert 'SENTINEL_PRIVATE_AUDIT' not in response.text
    if response.status_code == 200:
        data = response.json()['data']
        if tab == 'usage':
            assert data['ledger'] == []  # checkpoint observations have not yet been settled
            assert data['growth'] == []
        elif tab == 'config':
            assert data['config_snapshot']['config_version'] == 7
            assert data['config_snapshot']['resolved_config']['api_key'] == '[REDACTED]'
        else:
            assert data['items'][0]['action'] == 'read_debug'
            assert 'before_value' not in data['items'][0] and 'after_value' not in data['items'][0]


@pytest.mark.asyncio
async def test_list_statistics_count_records_without_exposing_job_bodies(card_env):
    from sqlalchemy import select
    from backend.database import Base
    from backend.models.realtime_voice import VoiceCall, VoiceMemoryJob, VoiceFollowupJob
    from backend.services.realtime_voice_record_service import record_statistics
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory, call_id = card_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[VoiceFollowupJob.__table__])
    turn_id = await add_turn(factory, call_id, assistant_interrupted=True, user_content_safety_status='matched')
    async with factory() as db:
        db.add(VoiceMemoryJob(call_id=call_id,turn_id=turn_id,turn_index=1,status='failed',
            pipeline_version='voice_memory_v1',extraction_snapshot={'phase':'ready','dropped':2,'items':['PRIVATE']}))
        await db.commit()
        stats = await record_statistics(db, [call_id])
        row = stats[call_id]
        assert row['turn_count']==1 and row['interrupted_count']==1 and row['safety_matched_count']==1
        assert row['memory_failed_count']==1 and row['memory_trace_count']==0
        assert row['memory_dropped_count']==2 and 'PRIVATE' not in str(row)


@pytest.mark.asyncio
async def test_crisis_statistics_and_empty_reasons_are_separate_from_safety(card_env):
    from sqlalchemy import select
    from backend.models.realtime_voice import VoiceCall, VoiceCallTurn
    from backend.services.realtime_voice_record_service import transcript_statistics, effective_turn
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory, call_id = card_env
    await add_turn(factory,call_id,1)
    await add_turn(factory,call_id,2,user_crisis_status='suspected',assistant_crisis_status='suspected',
                   user_text_final='ISOLATED_SENTINEL')
    await add_turn(factory,call_id,3,user_crisis_status='matched')
    await add_turn(factory,call_id,4,effective_text_expires_at=datetime.utcnow()-timedelta(days=1))
    await add_turn(factory,call_id,5,user_text_final=None,assistant_text_effective=None)
    async with factory() as db:
        stats = (await transcript_statistics(db,[call_id]))[call_id]
        assert stats['turn_count'] == 5 and stats['safety_matched_count'] == 0
        assert stats['crisis_suspected_count'] == 2 and stats['crisis_matched_count'] == 1
        assert stats['isolated_turn_count'] == 2 and stats['readable_turn_count'] == 1
        call = await db.scalar(select(VoiceCall))
        rows = (await db.scalars(select(VoiceCallTurn).order_by(VoiceCallTurn.turn_index))).all()
        projected = [effective_turn(call,turn,now=datetime.utcnow()) for turn in rows]
        assert [item['content_unavailable_reason'] for item in projected] == [
            None,'crisis_isolated','crisis_isolated','expired','no_effective_text']
        assert projected[1]['user_text_final'] is None and 'ISOLATED_SENTINEL' not in str(projected)
        call.deletion_fence_at = datetime.utcnow()
        await db.flush()
        assert (await transcript_statistics(db,[call_id]))[call_id]['readable_turn_count'] == 0


@pytest.mark.asyncio
async def test_record_api_exposes_crisis_counts_and_masks_isolated_text(card_env):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from backend.database import get_db
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    from tests.test_realtime_voice_step028_jobs import add_turn

    factory, call_id = card_env
    await add_turn(factory, call_id, 1)
    await add_turn(factory, call_id, 2, user_crisis_status='suspected',
                   assistant_crisis_status='suspected', user_text_final='ISOLATED_SENTINEL')
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(
        id=1, username='test', role='observer')

    async def session():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        listing = await client.get('/api/admin/voice/calls')
        detail = await client.get(f'/api/admin/voice/calls/{call_id}')
        turns = await client.get(f'/api/admin/voice/calls/{call_id}/turns')
    assert listing.status_code == detail.status_code == turns.status_code == 200
    for row in (listing.json()['data']['items'][0], detail.json()['data']):
        assert row['safety_matched_count'] == 0
        assert row['crisis_suspected_count'] == 2
        assert row['isolated_turn_count'] == 1
        assert row['readable_turn_count'] == 1
    isolated = turns.json()['data']['items'][1]
    assert isolated['content_unavailable_reason'] == 'crisis_isolated'
    assert isolated['user_text_final'] is None
    assert isolated['assistant_text_effective'] is None
    assert all('ISOLATED_SENTINEL' not in response.text for response in (listing, detail, turns))


@pytest.mark.asyncio
async def test_export_exact_authorized_projection_multiset(card_env):
    from collections import Counter
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from backend.database import get_db
    from backend.models.realtime_voice import VoiceCallTurn
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory, call_id = card_env
    for index in range(1,6):
        changes = {'assistant_text_generated':'PRIVATE_GENERATED'}
        if index==3: changes['effective_text_expires_at']=datetime.utcnow()-timedelta(days=1)
        if index==4: changes['effective_text_cleared_at']=datetime.utcnow()
        if index==5: changes['user_crisis_status']='matched'
        await add_turn(factory,call_id,index,**changes)
    fields=('call_id','turn_index','user_text_final','assistant_text_effective','effective_text_expires_at')
    async with factory() as db:
        rows=(await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.turn_index.in_([1,2])))).all()
        expected=Counter((r.call_id,r.turn_index,r.user_text_final,r.assistant_text_effective,r.effective_text_expires_at.isoformat()) for r in rows)
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username='test',role='ops_admin')
    async def session():
        async with factory() as db: yield db
    app.dependency_overrides[get_db]=session
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/api/admin/voice/calls/export',json={'call_ids':[call_id,call_id]})
    assert response.status_code==200
    items=response.json()['data']['items']
    assert all(set(item)==set(fields) for item in items)
    assert Counter(tuple(item[k] for k in fields) for item in items)==expected
    assert 'PRIVATE_GENERATED' not in response.text


def test_export_openapi_response_is_explicit_and_forbids_debug_fields():
    from fastapi import FastAPI
    from backend.routers.admin.voice_records import router
    from backend.schemas.realtime_voice_records import EffectiveExportTurn, ExportRequest
    from pydantic import ValidationError
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice')
    schema=app.openapi()
    response=schema['paths']['/api/admin/voice/calls/export']['post']['responses']['200']['content']['application/json']['schema']
    assert response['$ref'].endswith('/EffectiveExportResponse')
    props=schema['components']['schemas']['EffectiveExportTurn']['properties']
    assert set(props)=={'call_id','turn_index','user_text_final','assistant_text_effective','effective_text_expires_at'}
    with pytest.raises(ValidationError):
        ExportRequest(call_ids=['x'*65])
    with pytest.raises(ValidationError):
        EffectiveExportTurn(call_id='x',turn_index=1,user_text_final='u',assistant_text_effective='a',
            effective_text_expires_at=datetime.utcnow(),reasoning='forbidden')
