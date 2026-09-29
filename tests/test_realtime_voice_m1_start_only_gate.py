"""Cross-boundary runner env -> real Phase0 gate, without any Provider call."""
import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest
from tests.test_realtime_voice_step006_m1_profile import runner_copy
from tests.test_realtime_voice_step006_campaign_runner import _draft


def fixture(tmp_path):
    name = 'isolated_gate_' + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, Path('tmp/phase0-step004-m1-recovery-20260908/backend/phase0_realtime_voice/campaign_attempt_gate.py'))
    gate = importlib.util.module_from_spec(spec);sys.modules[name] = gate;spec.loader.exec_module(gate)
    m = runner_copy();m.configure_m1_protocol_profile(recovery=True)
    envfile=tmp_path/'env'
    envfile.write_text('MYSQL_HOST=mysql\nMYSQL_PORT=3306\nMYSQL_USER=test\nMYSQL_PASSWORD=test\nMYSQL_DATABASE=business\nREDIS_HOST=redis\nREDIS_PORT=6379\nREDIS_PASSWORD=\nREDIS_DB=3\nPHASE0_DOUBAO_S2S_APP_ID=test\n')
    draft=_draft();draft['s2s']['adapter_version']=m.PHASE0_ADAPTER_VERSION
    aid=str(uuid.uuid4())
    attempt={'attempt_directory':tmp_path,'campaign_id':'m1-protocol-fixture',
        'matrix_sha256':'a'*64,'runtime_manifest_sha256':'b'*64,'baseline_epoch':2,
        'attempt_id':aid,'attempt_ordinal':3,'attempt_kind':'s01_start_session','fresh_admin_worker':False}
    env=m.build_phase0_child_environment(project_env_path=envfile,phase0_root=tmp_path,
        draft_snapshot=draft,secret='synthetic',parent_environ={},campaign_attempt=attempt)
    receipt={k:attempt[k] for k in ('campaign_id','matrix_sha256','runtime_manifest_sha256','baseline_epoch','attempt_id','attempt_ordinal','attempt_kind')}
    receipt.update(schema_version=gate.ATTEMPT_RECEIPT_SCHEMA,reserved_at='2026-09-09T01:28:26Z')
    (tmp_path/f'{aid}.reserved.json').write_text(json.dumps(receipt))
    return gate,env,aid


def test_runner_start_only_env_is_accepted_once_and_cannot_reconnect(tmp_path):
    gate,env,aid=fixture(tmp_path)
    consumed=gate.consume_start_session_attempt(aid,environ=env)
    assert consumed.attempt_ordinal==3
    with pytest.raises(gate.CampaignAttemptGateError) as exc:
        gate.consume_start_session_attempt(aid,environ=env)
    assert exc.value.code==40913
    with pytest.raises(gate.CampaignAttemptGateError):
        gate.consume_reconnect_attempt(str(uuid.uuid4()),start_binding=consumed.binding,environ=env)


@pytest.mark.parametrize('change', ['no_scope','wrong_scope','with_reconnect','wrong_id','wrong_hash'])
def test_start_only_does_not_relax_other_reservation_checks(tmp_path,change):
    gate,env,aid=fixture(tmp_path)
    if change=='no_scope': env.pop('PHASE0_M1_MISSING_PROBES_ONLY',None)
    if change=='wrong_scope': env['PHASE0_M1_MISSING_PROBES_ONLY']='yes'
    if change=='with_reconnect': env['PHASE0_M1_EXPECTED_RECONNECT_ATTEMPT_ORDINAL']='4'
    if change=='wrong_id': aid=str(uuid.uuid4())
    if change=='wrong_hash': env['PHASE0_M1_MATRIX_SHA256']='c'*64
    with pytest.raises(gate.CampaignAttemptGateError): gate.consume_start_session_attempt(aid,environ=env)
    assert not list(tmp_path.glob('*.consumed.json'))
