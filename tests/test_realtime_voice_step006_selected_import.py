"""Selected imports retain original facts; they never grant a capability."""
import json
from copy import deepcopy
from io import StringIO

import pytest
from sqlalchemy import select

import backend.services.realtime_voice_capability_service as service
from backend.scripts import import_realtime_voice_phase0_evidence as cli
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.realtime_voice import VoiceCapabilityEvidence
from tests.test_realtime_voice_step006_evidence_import import (
    database, _bundle, _rehash, _config_rows, _stable_state,
    session_factory, role_ids, _redis_state,
)


def selection(bundle, ids):
    validator = getattr(service, 'validate_phase0_evidence_selection', None)
    assert callable(validator), 'selected report validation is missing'
    return validator(bundle, report_ids=ids)


async def ingest(bundle, ids):
    method = getattr(service.realtime_voice_capability_service,
                     'import_phase0_evidence_selection', None)
    assert callable(method), 'selected report import is missing'
    async with session_factory() as db:
        return await method(db, bundle=bundle, report_ids=ids,
                            operator_id=role_ids['super_admin'])


def test_selected_report_retains_original_record_and_exclusions():
    bundle = _bundle()
    ids = [bundle['records'][0]['evidence_report_id']]
    result = selection(bundle, ids)
    assert result['records'] == bundle['records'][:1]
    assert len(result['excluded_records']) == 5
    assert {r['reason'] for r in result['excluded_records']} == {'not_selected'}
    assert result['bundle_sha256'] == bundle['bundle_sha256']


@pytest.mark.parametrize('case', ['empty', 'duplicate', 'missing', 'hash', 'cross_run', 'duplicate_capability'])
def test_selection_rejects_invalid_envelope_or_selection(case):
    bundle = _bundle()
    ids = [bundle['records'][0]['evidence_report_id']]
    if case == 'empty': ids = []
    if case == 'duplicate': ids *= 2
    if case == 'missing': ids = ['44444444-4444-4444-8444-444444444444']
    if case == 'hash': bundle['records'][-1]['tested_at'] = '2026-09-01T00:00:00Z'
    if case == 'cross_run':
        bundle['records'][-1]['evidence_run_id'] = '44444444-4444-4444-8444-444444444444'
        _rehash(bundle)
    if case == 'duplicate_capability':
        bundle['records'][-1]['capability_key'] = bundle['records'][0]['capability_key']
        _rehash(bundle)
    with pytest.raises(service.CapabilityStateError): selection(bundle, ids)


@pytest.mark.asyncio
async def test_disjoint_selections_append_without_overwrite_and_replay_is_noop():
    bundle = _bundle()
    active, draft = await _config_rows()
    before = json.loads(draft.config_value)
    active_value, redis = active.config_value, _redis_state()
    ids = [bundle['records'][0]['evidence_report_id']]
    assert (await ingest(bundle, ids))['record_count'] == 1
    first_state = await _stable_state()
    assert (await ingest(bundle, ids))['idempotent'] is True
    assert await _stable_state() == first_state
    await ingest(bundle, [bundle['records'][1]['evidence_report_id']])
    active, draft = await _config_rows()
    after = json.loads(draft.config_value)
    assert active.config_value == active_value and _redis_state() == redis
    for record in bundle['records'][2:]:
        key = record['capability_key']
        assert after['capabilities'][key] == before['capabilities'][key]
    async with session_factory() as db:
        rows = (await db.execute(select(VoiceCapabilityEvidence))).scalars().all()
        assert len(rows) == 2
        assert {r.evidence_report_id for r in rows} == {r['evidence_report_id'] for r in bundle['records'][:2]}
        audits = (await db.execute(select(AdminOperationLog))).scalars().all()
        assert len(audits) == 2
        assert all(len(a.action) <= AdminOperationLog.__table__.c.action.type.length for a in audits)
        assert len(json.loads(audits[0].after_value)['excluded_records']) == 5


@pytest.mark.asyncio
async def test_error_is_auditable_but_never_verified_or_enabled():
    bundle = _bundle()
    record = bundle['records'][1]
    record['verification_result'] = 'error'
    record['evidence_payload']['capability_status'] = 'unverified'
    record['evidence_payload']['reason_code'] = 'active_reply_interrupt_missing_causal_anchors'
    _rehash(bundle)
    await ingest(bundle, [record['evidence_report_id']])
    _, draft = await _config_rows()
    cap = json.loads(draft.config_value)['capabilities'][record['capability_key']]
    assert (cap['verification_status'], cap['enabled'], cap['forced_enabled'], cap['effective_scope']) == ('unverified', False, False, 'off')
    with pytest.raises(service.CapabilityStateError): service.validate_phase0_evidence_bundle(bundle)


@pytest.mark.asyncio
async def test_phase0_diagnostic_cannot_be_forced_to_test():
    from backend.models.admin_user import AdminUser
    from backend.services.realtime_voice_config_service import realtime_voice_config_service, VoiceConfigError
    bundle = _bundle()
    record = bundle['records'][1]
    record['verification_result'] = 'error'
    record['evidence_payload']['capability_status'] = 'unverified'
    _rehash(bundle)
    await ingest(bundle, [record['evidence_report_id']])
    before = await _stable_state()
    async with session_factory() as db:
        admin = await db.get(AdminUser, role_ids['super_admin'])
        with pytest.raises(VoiceConfigError) as error:
            await realtime_voice_config_service._force_capability_test_checked(
                db, capability_key=record['capability_key'], effective_scope='test',
                confirm_text='CONFIRM', reason='cannot promote diagnostic', admin_user=admin)
        assert error.value.code == 'VOICE_CAPABILITY_FORCE_STATUS_INVALID'
    assert await _stable_state() == before


@pytest.mark.asyncio
async def test_conflicting_selection_does_not_insert_other_records():
    bundle = _bundle()
    await ingest(bundle, [bundle['records'][0]['evidence_report_id']])
    before = await _stable_state()
    changed = deepcopy(bundle)
    changed['records'][0]['evidence_payload']['production_import_ready'] = True
    _rehash(changed)
    with pytest.raises(service.CapabilityStateError):
        await ingest(changed, [r['evidence_report_id'] for r in changed['records'][:2]])
    assert await _stable_state() == before


@pytest.mark.asyncio
async def test_draft_failure_rolls_back_selected_rows(monkeypatch):
    bundle = _bundle()
    before = await _stable_state()
    def fail(*args, **kwargs): raise RuntimeError('injected draft failure')
    monkeypatch.setattr(service, '_advance_draft', fail)
    with pytest.raises(RuntimeError): await ingest(bundle, [bundle['records'][0]['evidence_report_id']])
    assert await _stable_state() == before


def test_cli_report_id_selects_before_opening_database(tmp_path, monkeypatch):
    bundle = _bundle()
    path = tmp_path / 'original.json'
    path.write_text(json.dumps(bundle))
    async def imported(**kwargs):
        assert kwargs['report_ids'] == [bundle['records'][0]['evidence_report_id']]
        return {'idempotent': False, 'record_count': 1, 'draft_revision': 4}
    monkeypatch.setattr(cli, '_database_import', imported)
    out, err = StringIO(), StringIO()
    result = cli.main(['--bundle', str(path), '--report-id', bundle['records'][0]['evidence_report_id'], '--operator-id', '1', '--confirm', 'CONFIRM'], stdout=out, stderr=err)
    assert result == 0, err.getvalue()
    assert json.loads(out.getvalue())['record_count'] == 1

@pytest.mark.asyncio
async def test_storage_precision_loss_rolls_back_entire_selection(monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    bundle = _bundle()
    before = await _stable_state()
    original_refresh = AsyncSession.refresh
    async def lossy_refresh(db, instance, *args, **kwargs):
        await original_refresh(db, instance, *args, **kwargs)
        if isinstance(instance, VoiceCapabilityEvidence):
            from datetime import timedelta
            instance.tested_at += timedelta(seconds=1)
    monkeypatch.setattr(AsyncSession, 'refresh', lossy_refresh)
    with pytest.raises(service.CapabilityStateError) as error:
        await ingest(bundle, [bundle['records'][0]['evidence_report_id']])
    assert error.value.code == 'VOICE_CAPABILITY_EVIDENCE_STORAGE_MISMATCH'
    assert await _stable_state() == before
