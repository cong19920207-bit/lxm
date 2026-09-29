"""A replay-free playback review proves listening, never production support."""
from copy import deepcopy
import importlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import VoiceCapabilityEvidence
from tests.test_realtime_voice_step006_evidence_import import (
    database, session_factory, role_ids, _stable_state, _config_rows,
)

BASE=Path(__file__).resolve().parents[1]/'docs/design/realtime_voice/P1/execution/evidence/step006/m1-restricted-20260909/admin-playback-manual'

def inputs():
    def read(name):return json.loads((BASE/name).read_text())
    bundle=read('evidence-last-observed.json')
    return {'bundle':bundle,'session':read('session.json'),
            'consumed_attempt':json.loads(next((BASE/'attempt-reservations').glob('*.consumed.json')).read_text()),
            'user_start':read('user-started.json'),'human_confirmation':read('human-heard-confirmation.json'),
            'failed_test':read('admin-route-result.json'),
            'ack_report_id':next(r['evidence_report_id'] for r in bundle['records'] if r['capability_key']=='supports_sentence_playback_ack'),
            'events_report_id':next(r['evidence_report_id'] for r in bundle['records'] if r['capability_key']=='supports_context_truncate')}

def service():return importlib.import_module('backend.services.realtime_voice_admin_playback_review_service')

async def seed(sources):
    async with session_factory() as db:
        _,draft=await _config_rows()
        row=await db.get(AdminConfig,draft.id)
        row.draft_revision=7
        # Preserve normal test fixtures except the revision and six target dimensions.
        live=next(r['content'] for r in json.loads((BASE/'before.json').read_text())['config_rows'] if r['config_key']=='voice_call_config' and r['is_draft'])
        row.config_value=json.dumps(live)
        db.add(AdminOperationLog(id=140,admin_user_id=role_ids['super_admin'],admin_username='review-test',module='voice_config',action='test_capability',after_value=json.dumps(sources['failed_test']['data'])))
        await db.commit()

async def ingest(sources):
    async with session_factory() as db:
        return await service().append_admin_playback_review(db,sources=sources,failure_audit_id=140,operator_id=role_ids['super_admin'])

def test_saved_real_playback_can_be_reviewed_without_changing_original_error():
    sources=inputs();before=deepcopy(sources)
    review=service().validate_admin_playback_review(sources)
    assert sources==before
    assert review['summary']['review_status']=='passed'
    record=review['record']
    assert record['evidence_report_id']!=sources['ack_report_id']
    assert record['evidence_run_id']==sources['bundle']['evidence_run_id']
    assert record['verification_result']=='error'
    assert record['verified_at'] is None and record['expires_at'] is None
    assert record['source_type']=='admin_capability_test'
    assert record['evidence_payload']['reason_code']=='admin_playback_review_only'
    assert 'microphone_permission' not in record['evidence_payload']['runtime_conditions']

@pytest.mark.parametrize('case',['no_hearing','wrong_session','wrong_run','bad_hash','no_ack','wrong_token','no_audio','wrong_admin_target','wrong_attempt','time_outside_test'])
def test_review_rejects_missing_or_conflicting_proofs(case):
    sources=inputs()
    ack=next(r for r in sources['bundle']['records'] if r['evidence_report_id']==sources['ack_report_id'])
    events=next(r for r in sources['bundle']['records'] if r['evidence_report_id']==sources['events_report_id'])
    if case=='no_hearing':sources['human_confirmation']['heard']=False
    if case=='wrong_session':sources['human_confirmation']['session_id']='11111111-1111-4111-8111-111111111111'
    if case=='wrong_run':sources['session']['evidence_run_id']='11111111-1111-4111-8111-111111111111'
    if case=='bad_hash':sources['bundle']['bundle_sha256']='a'*64
    if case=='no_ack':ack['evidence_payload']['action_evidence']=[]
    if case=='wrong_token':ack['evidence_payload']['action_evidence'][0]['sentence_token']='hmac256:'+'a'*24
    if case=='no_audio':events['evidence_payload']['event_evidence']=[e for e in events['evidence_payload']['event_evidence'] if not e['is_audio']]
    if case=='wrong_admin_target':sources['failed_test']['data']['capability_key']='supports_reply_cancel'
    if case=='wrong_attempt':sources['consumed_attempt']['attempt_kind']='s01_start_session'
    if case=='time_outside_test':sources['user_start']['started_at']='2026-09-09T01:00:00Z'
    if case in {'no_ack','wrong_token','no_audio'}:
        from tests.test_realtime_voice_step006_evidence_import import _rehash
        _rehash(sources['bundle'])
    with pytest.raises(ValueError):service().validate_admin_playback_review(sources)

@pytest.mark.asyncio
async def test_atomic_diagnostic_row_review_audit_and_idempotency():
    sources=inputs();await seed(sources)
    first=await ingest(sources);assert first['review_status']=='passed' and not first['idempotent']
    stable=await _stable_state()
    assert (await ingest(sources))['idempotent'] is True
    assert await _stable_state()==stable
    async with session_factory() as db:
        rows=(await db.execute(select(VoiceCapabilityEvidence))).scalars().all();assert len(rows)==1
        assert rows[0].verification_result=='error'
        logs=(await db.execute(select(AdminOperationLog))).scalars().all();assert len(logs)==3
        assert json.loads((await db.get(AdminOperationLog,140)).after_value)==sources['failed_test']['data']
    _,draft=await _config_rows();cap=json.loads(draft.config_value)['capabilities']['supports_sentence_playback_ack']
    assert (cap['verification_status'],cap['enabled'],cap['forced_enabled'],cap['effective_scope'])==('unverified',False,False,'off')

@pytest.mark.asyncio
async def test_conflicting_reuse_and_audit_failure_roll_back(monkeypatch):
    sources=inputs();await seed(sources)
    before=await _stable_state()
    module=service()
    def fail(*args,**kwargs):raise RuntimeError('injected review audit failure')
    with monkeypatch.context() as patch:
        patch.setattr(module,'_review_audit',fail)
        with pytest.raises(RuntimeError):await ingest(sources)
    assert await _stable_state()==before
    await ingest(sources);before=await _stable_state()
    changed=deepcopy(sources);changed['human_confirmation']['statement']+='（changed）'
    with pytest.raises(ValueError):await ingest(changed)
    assert await _stable_state()==before

@pytest.mark.asyncio
async def test_playback_review_cannot_be_forced_or_published():
    from backend.services.realtime_voice_config_service import realtime_voice_config_service,VoiceConfigError
    sources=inputs();await seed(sources);await ingest(sources)
    async with session_factory() as db:
        _,draft=await _config_rows();row=await db.get(AdminConfig,draft.id)
        config=json.loads(row.config_value);config['global']['test_user_ids']=[1]
        row.config_value=json.dumps(config);await db.flush()
        with pytest.raises(VoiceConfigError) as exc:
            await realtime_voice_config_service._force_capability_test_checked(db,capability_key='supports_sentence_playback_ack',effective_scope='test',confirm_text='CONFIRM',reason='review must stay off',admin_user=await db.get(AdminUser,role_ids['super_admin']))
        assert exc.value.code=='VOICE_CAPABILITY_FORCE_STATUS_INVALID'
        config['capabilities']['supports_sentence_playback_ack'].update(enabled=True,effective_scope='all')
        with pytest.raises(VoiceConfigError):await realtime_voice_config_service._ensure_all_scope_evidence(db,config)
        await db.rollback()

def test_consistently_relabelled_session_and_attempt_are_not_original_sources():
    sources=inputs()
    changed='11111111-1111-4111-8111-111111111111'
    sources['session']['session_id']=changed
    sources['human_confirmation']['session_id']=changed
    sources['session']['s2s']['session_id']=changed
    sources['consumed_attempt']['attempt_id']=changed
    sources['consumed_attempt']['campaign_id']='different-campaign'
    with pytest.raises(ValueError):service().validate_admin_playback_review(sources)
