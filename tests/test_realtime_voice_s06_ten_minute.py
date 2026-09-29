"""The approved duration amendment preserves history and permits only S06 once."""

import json
from copy import deepcopy

import pytest

from scripts import realtime_voice_m1_campaign_runner as runner
from tests.test_realtime_voice_m1_authorized_retest import campaign
from tests.test_realtime_voice_m1_fifth_round import fifth


def amendment(campaign):
    common, evidence, _, _ = fifth(campaign)
    runner.advance_campaign_to_final_batch(
        **common, regression_evidence_path=evidence, authorized_retest=True
    )
    while len(json.loads(common['ledger_path'].read_text())['attempts']) < 15:
        runner.reserve_provider_attempt(**common, attempt_kind='s05_start_session')
    before = json.loads(common['ledger_path'].read_text())
    approval = {
        'passed': True, 'authorized_additional_round': True,
        'target_baseline_epoch': 6, 'max_provider_attempts': 16,
        'prior_ledger_sha256': runner._file_sha256(common['ledger_path']),
        'authorization_scope': 's06_ten_minute_only', 'required_minutes': 10,
    }
    common.update(matrix_sha256='5' * 64, runtime_manifest_sha256='6' * 64)
    evidence.write_text(json.dumps(approval))
    return common, evidence, before, approval


def test_duration_amendment_preserves_old_evidence_and_permits_only_one_s06(campaign):
    common, evidence, before, _ = amendment(campaign)
    runner.advance_campaign_to_final_batch(
        **common, regression_evidence_path=evidence, authorized_retest=True
    )
    after = json.loads(common['ledger_path'].read_text())
    assert after['baseline_epochs'][:5] == before['baseline_epochs']
    assert after['attempts'] == before['attempts']
    assert after['max_provider_attempts'] == 16
    for kind in ('s01_start_session', 's01_reconnect', 'admin_connection', 'admin_ack'):
        with pytest.raises(ValueError):
            runner.reserve_provider_attempt(**common, attempt_kind=kind)
        assert json.loads(common['ledger_path'].read_text()) == after
    receipt = runner.reserve_provider_attempt(**common, attempt_kind='s06_start_session')
    assert receipt['attempt_ordinal'] == 16 and receipt['remaining_attempts'] == 0
    context = {
        **{key: receipt[key] for key in ('campaign_id', 'attempt_id', 'attempt_ordinal', 'attempt_kind', 'baseline_epoch')},
        'matrix_sha256': common['matrix_sha256'],
        'runtime_manifest_sha256': common['runtime_manifest_sha256'],
        'attempt_directory': common['ledger_path'].parent / 'attempt-reservations',
        'fresh_admin_worker': False,
    }
    assert runner._validate_worker_campaign_attempt(context)['attempt_ordinal'] == 16
    with pytest.raises(RuntimeError):
        runner.reserve_provider_attempt(**common, attempt_kind='s06_start_session')


@pytest.mark.parametrize('change', [
    {'required_minutes': 30}, {'authorization_scope': 'all_scenarios'},
    {'max_provider_attempts': 18}, {'prior_ledger_sha256': '0' * 64},
    {'passed': False}, {'authorized_additional_round': False},
])
def test_duration_amendment_rejects_unbound_or_wider_approval(campaign, change):
    common, evidence, before, approval = amendment(campaign)
    evidence.write_text(json.dumps({**approval, **change}))
    with pytest.raises((ValueError, RuntimeError)):
        runner.advance_campaign_to_final_batch(
            **common, regression_evidence_path=evidence, authorized_retest=True
        )
    assert json.loads(common['ledger_path'].read_text()) == before


def test_duration_amendment_cannot_change_provider_or_draft_baseline(campaign):
    common, evidence, before, _ = amendment(campaign)
    common['baseline'] = deepcopy(common['baseline'])
    common['baseline']['voice_draft_sha256'] = '7' * 64
    with pytest.raises(ValueError):
        runner.advance_campaign_to_final_batch(
            **common, regression_evidence_path=evidence, authorized_retest=True
        )
    assert json.loads(common['ledger_path'].read_text()) == before
