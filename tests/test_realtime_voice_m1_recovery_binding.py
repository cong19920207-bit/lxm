"""Recovery keeps the original campaign's spent slots and accepted epoch."""
import json
from copy import deepcopy

import pytest

from tests.test_realtime_voice_step006_m1_profile import runner_copy
from tests.test_realtime_voice_step006_campaign_runner import _campaign_baseline


def prepared(tmp_path):
    m = runner_copy()
    m.configure_m1_protocol_profile()
    campaign = 'm1-protocol-recovery-fixture'
    old = _campaign_baseline()
    old['evidence_dimensions'].update(adapter_version=m.PHASE0_ADAPTER_VERSION,
        evidence_suite_version=m.PHASE0_EVIDENCE_SUITE_VERSION, model_version='2.2.0.0')
    old['evidence_fingerprint'] = m._canonical_sha256(old['evidence_dimensions'])
    m._M1_PROTOCOL_AUTHORIZATION = (campaign, 'a'*64, 'b'*64)
    for kind in ('s01_start_session', 's01_reconnect'):
        m.reserve_provider_attempt(ledger_path=None, project_root=tmp_path,
            campaign_id=campaign, matrix_sha256='a'*64, runtime_manifest_sha256='b'*64,
            baseline=old, attempt_kind=kind)
    ledger = m.campaign_ledger_path(campaign, project_root=tmp_path)
    prior = json.loads(ledger.read_text())
    m.configure_m1_protocol_profile(recovery=True)
    baseline = deepcopy(old)
    baseline['evidence_dimensions'].update(adapter_version=m.PHASE0_ADAPTER_VERSION,
        evidence_suite_version=m.PHASE0_EVIDENCE_SUITE_VERSION)
    baseline['evidence_fingerprint'] = m._canonical_sha256(baseline['evidence_dimensions'])
    baseline['voice_draft_sha256'] = 'f'*64
    m._M1_PROTOCOL_AUTHORIZATION = (campaign, 'c'*64, 'd'*64)
    receipt = tmp_path/'regression.json'
    receipt.write_text(json.dumps({'passed': True, 'authorization_scope': 'm1_missing_cancel_truncate_only',
        'prior_ledger_sha256': m._file_sha256(ledger), 'max_provider_attempts': 5,
        'automatic_retries': 0, 'target_baseline_epoch': 2}))
    kwargs = dict(ledger_path=None, project_root=tmp_path, campaign_id=campaign,
        matrix_sha256='c'*64, runtime_manifest_sha256='d'*64,
        baseline=baseline, regression_evidence_path=receipt)
    return m, ledger, prior, receipt, kwargs


def test_recovery_carries_two_used_slots_and_old_epoch_without_changing_legacy_profile(tmp_path):
    m, ledger, prior, receipt, kw = prepared(tmp_path)
    assert str(m.PHASE0_RELATIVE_ROOT) == 'tmp/phase0-step004-m1-recovery-20260908'
    m.advance_campaign_to_final_batch(**kw)
    current = json.loads(ledger.read_text())
    assert current['attempts'] == prior['attempts']
    assert current['baseline_epochs'][0] == prior['baseline_epochs'][0]
    assert current['max_provider_attempts'] == 5
    assert current['active_baseline_epoch'] == 2
    reserve_kw = {k:v for k,v in kw.items() if k != 'regression_evidence_path'}
    result = m.reserve_provider_attempt(**reserve_kw, attempt_kind='s01_start_session')
    assert result['attempt_ordinal'] == 3 and result['remaining_attempts'] == 2
    for _ in range(2):
        m.reserve_provider_attempt(**reserve_kw, attempt_kind='s01_start_session')
    with pytest.raises(RuntimeError):
        m.reserve_provider_attempt(**reserve_kw, attempt_kind='s01_start_session')
    legacy = runner_copy()
    legacy.configure_m1_protocol_profile()
    assert legacy.PHASE0_ADAPTER_VERSION.endswith('v7') and set(legacy.BASELINE_BATCHES) == {1}


@pytest.mark.parametrize('mutation', ['ledger', 'budget', 'scope', 'authorization', 'baseline', 'profile'])
def test_recovery_rejects_drift_before_writing(tmp_path, mutation):
    m, ledger, prior, receipt, kw = prepared(tmp_path)
    proof = json.loads(receipt.read_text())
    if mutation == 'ledger': proof['prior_ledger_sha256'] = '0'*64
    if mutation == 'budget': proof['max_provider_attempts'] = 6
    if mutation == 'scope': proof['authorization_scope'] = 'retest_everything'
    if mutation == 'authorization': m._M1_PROTOCOL_AUTHORIZATION = None
    if mutation == 'baseline':
        kw['baseline']['evidence_dimensions']['adapter_version'] = 'wrong'
        kw['baseline']['evidence_fingerprint'] = m._canonical_sha256(kw['baseline']['evidence_dimensions'])
    if mutation == 'profile': m.configure_m1_protocol_profile()
    receipt.write_text(json.dumps(proof))
    before = ledger.read_bytes()
    with pytest.raises((ValueError, RuntimeError)):
        m.advance_campaign_to_final_batch(**kw)
    assert ledger.read_bytes() == before


def test_recovery_cannot_create_fresh_budget(tmp_path):
    m, ledger, prior, receipt, kw = prepared(tmp_path)
    reserve_kw = {k:v for k,v in kw.items() if k != 'regression_evidence_path'}
    ledger.unlink()
    with pytest.raises(ValueError, match='原账本'):
        m.reserve_provider_attempt(**reserve_kw, attempt_kind='s01_start_session')
    assert not ledger.exists()


@pytest.mark.parametrize('kind', ['s01_reconnect', 'admin_ack'])
def test_recovery_only_reserves_missing_probe_session(tmp_path, kind):
    m, ledger, prior, receipt, kw = prepared(tmp_path)
    m.advance_campaign_to_final_batch(**kw)
    before = ledger.read_bytes()
    with pytest.raises(ValueError, match='仅允许打断和截断'):
        m.reserve_provider_attempt(**{k:v for k,v in kw.items() if k != 'regression_evidence_path'}, attempt_kind=kind)
    assert ledger.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize('extra', [['ack'], ['serve-direct', '--expected-reconnect-ordinal', '4']])
async def test_recovery_cli_rejects_extra_actions_before_runtime(tmp_path, extra):
    m = runner_copy()
    args = m._build_argument_parser().parse_args(extra + ['--m1-protocol', '--m1-recovery', '--m1-authorization', str(tmp_path/'not-read')])
    with pytest.raises(ValueError, match='仅允许打断和截断'):
        await m._run_cli(args)
