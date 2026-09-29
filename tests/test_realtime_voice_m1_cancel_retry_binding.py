from copy import deepcopy
import json
import pytest
from tests.test_realtime_voice_m1_recovery_binding import prepared

def test_cancel_only_retains_four_attempts_and_allows_only_fifth(tmp_path):
    m,ledger,prior,receipt,kw=prepared(tmp_path)
    m.advance_campaign_to_final_batch(**kw)
    reserve={k:v for k,v in kw.items() if k!='regression_evidence_path'}
    for _ in range(2): m.reserve_provider_attempt(**reserve,attempt_kind='s01_start_session')
    before=json.loads(ledger.read_text())
    m.configure_m1_protocol_profile(recovery=True,cancel_only=True)
    assert m.PHASE0_ADAPTER_VERSION.endswith('v9')
    baseline=deepcopy(kw['baseline'])
    baseline['evidence_dimensions'].update(adapter_version=m.PHASE0_ADAPTER_VERSION,evidence_suite_version=m.PHASE0_EVIDENCE_SUITE_VERSION)
    baseline['evidence_fingerprint']=m._canonical_sha256(baseline['evidence_dimensions'])
    baseline['voice_draft_sha256']='9'*64
    m._M1_PROTOCOL_AUTHORIZATION=(kw['campaign_id'],'e'*64,'f'*64)
    receipt.write_text(json.dumps(dict(passed=True,authorization_scope='m1_reply_cancel_only',prior_ledger_sha256=m._file_sha256(ledger),max_provider_attempts=5,automatic_retries=0,target_baseline_epoch=3)))
    kw.update(matrix_sha256='e'*64,runtime_manifest_sha256='f'*64,baseline=baseline)
    m.advance_campaign_to_final_batch(**kw)
    after=json.loads(ledger.read_text())
    assert after['attempts']==before['attempts'] and after['baseline_epochs'][:2]==before['baseline_epochs']
    assert after['active_baseline_epoch']==3 and after['max_provider_attempts']==5
    reserve={k:v for k,v in kw.items() if k!='regression_evidence_path'}
    assert m.reserve_provider_attempt(**reserve,attempt_kind='s01_start_session')['attempt_ordinal']==5
    with pytest.raises(RuntimeError): m.reserve_provider_attempt(**reserve,attempt_kind='s01_start_session')

    before=json.loads(ledger.read_text())
    m.configure_m1_protocol_profile(recovery=True,cancel_only=True,cancel_retry=True)
    m._M1_PROTOCOL_AUTHORIZATION=(kw['campaign_id'],'1'*64,'2'*64)
    receipt.write_text(json.dumps(dict(passed=True,authorization_scope='m1_reply_cancel_only',prior_ledger_sha256=m._file_sha256(ledger),max_provider_attempts=6,automatic_retries=0,target_baseline_epoch=4)))
    kw.update(matrix_sha256='1'*64,runtime_manifest_sha256='2'*64)
    m.advance_campaign_to_final_batch(**kw)
    after=json.loads(ledger.read_text())
    assert after['attempts']==before['attempts'] and after['baseline_epochs'][:3]==before['baseline_epochs']
    assert after['max_provider_attempts']==6
    reserve={k:v for k,v in kw.items() if k!='regression_evidence_path'}
    assert m.reserve_provider_attempt(**reserve,attempt_kind='s01_start_session')['attempt_ordinal']==6
    with pytest.raises(RuntimeError):m.reserve_provider_attempt(**reserve,attempt_kind='s01_start_session')
