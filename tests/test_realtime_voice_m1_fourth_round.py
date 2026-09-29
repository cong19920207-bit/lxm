"""Explicit fourth-round authorization extends only this ledger to 16 slots."""

import json
from copy import deepcopy

import pytest

from scripts import realtime_voice_m1_campaign_runner as runner
from tests.test_realtime_voice_m1_authorized_retest import campaign


def fourth(campaign):
    common, evidence, _ = campaign
    runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    runner.reserve_provider_attempt(**common, attempt_kind='s01_start_session')
    before = json.loads(common['ledger_path'].read_text())
    approval = {
        'passed': True, 'authorized_additional_round': True,
        'target_baseline_epoch': 4, 'max_provider_attempts': 16,
        'prior_ledger_sha256': runner._file_sha256(common['ledger_path']),
    }
    common.update(matrix_sha256='1'*64, runtime_manifest_sha256='2'*64)
    evidence.write_text(json.dumps(approval))
    return common, evidence, before, approval


def test_fourth_round_preserves_history_caps_at_16_and_cannot_repeat(campaign):
    common, evidence, before, _ = fourth(campaign)
    result = runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    after = json.loads(common['ledger_path'].read_text())
    assert result['active_baseline_epoch'] == 4
    assert after['baseline_epochs'][:3] == before['baseline_epochs']
    assert after['attempts'] == before['attempts']
    assert after['max_provider_attempts'] == 16
    for _ in range(13):
        receipt = runner.reserve_provider_attempt(**common, attempt_kind='s02_start_session')
    assert receipt['attempt_ordinal'] == 16 and receipt['remaining_attempts'] == 0
    with pytest.raises(RuntimeError, match='16'):
        runner.reserve_provider_attempt(**common, attempt_kind='s03_start_session')
    with pytest.raises((ValueError, RuntimeError)):
        runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)


@pytest.mark.parametrize('change', [
    {'target_baseline_epoch': 3}, {'max_provider_attempts': 17},
    {'prior_ledger_sha256': '0'*64}, {'authorized_additional_round': False},
])
def test_fourth_round_rejects_unbound_or_expanded_authorization(campaign, change):
    common, evidence, before, approval = fourth(campaign)
    evidence.write_text(json.dumps({**approval, **change}))
    with pytest.raises((ValueError, RuntimeError)):
        runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    assert json.loads(common['ledger_path'].read_text()) == before


def test_only_fourth_round_worker_can_use_slot_16(campaign):
    common, evidence, _, _ = fourth(campaign)
    runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    for _ in range(13):
        receipt = runner.reserve_provider_attempt(**common, attempt_kind='s02_start_session')
    context = {
        **{key: receipt[key] for key in ('campaign_id','attempt_id','attempt_ordinal','attempt_kind','baseline_epoch')},
        'matrix_sha256':common['matrix_sha256'], 'runtime_manifest_sha256':common['runtime_manifest_sha256'],
        'attempt_directory':common['ledger_path'].parent/'attempt-reservations', 'fresh_admin_worker':False,
    }
    assert runner._validate_worker_campaign_attempt(context)['attempt_ordinal'] == 16
    old = deepcopy(context); old['baseline_epoch'] = 3
    with pytest.raises(ValueError):
        runner._validate_worker_campaign_attempt(old)
