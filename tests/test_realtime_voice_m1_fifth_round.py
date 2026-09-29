"""The authorized fifth round preserves history and permits at most 18 slots."""

import json
from copy import deepcopy

import pytest

from scripts import realtime_voice_m1_campaign_runner as runner
from tests.test_realtime_voice_m1_authorized_retest import campaign
from tests.test_realtime_voice_m1_fourth_round import fourth


def fifth(campaign):
    common, evidence, _, _ = fourth(campaign)
    runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    runner.reserve_provider_attempt(**common, attempt_kind='s01_start_session')
    before = json.loads(common['ledger_path'].read_text())
    approval = {'passed': True, 'authorized_additional_round': True,
                'target_baseline_epoch': 5, 'max_provider_attempts': 18,
                'prior_ledger_sha256': runner._file_sha256(common['ledger_path'])}
    common.update(matrix_sha256='3'*64, runtime_manifest_sha256='4'*64)
    evidence.write_text(json.dumps(approval))
    return common, evidence, before, approval


def test_fifth_round_preserves_history_and_stops_at_18(campaign):
    common, evidence, before, _ = fifth(campaign)
    result = runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    after = json.loads(common['ledger_path'].read_text())
    assert result['active_baseline_epoch'] == 5
    assert after['baseline_epochs'][:4] == before['baseline_epochs']
    assert after['attempts'] == before['attempts']
    assert after['max_provider_attempts'] == 18
    for _ in range(18 - len(before['attempts'])):
        receipt = runner.reserve_provider_attempt(**common, attempt_kind='s02_start_session')
    assert receipt['attempt_ordinal'] == 18 and receipt['remaining_attempts'] == 0
    with pytest.raises(RuntimeError, match='18'):
        runner.reserve_provider_attempt(**common, attempt_kind='s03_start_session')
    with pytest.raises((ValueError, RuntimeError)):
        runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)


@pytest.mark.parametrize('change', [{'target_baseline_epoch': 6}, {'max_provider_attempts': 19},
                                  {'max_provider_attempts': 16}, {'prior_ledger_sha256': '0'*64},
                                  {'authorized_additional_round': False}, {'passed': False}])
def test_fifth_requires_exact_bound_authorization(campaign, change):
    common, evidence, before, approval = fifth(campaign)
    evidence.write_text(json.dumps({**approval, **change}))
    with pytest.raises((ValueError, RuntimeError)):
        runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    assert json.loads(common['ledger_path'].read_text()) == before


def test_only_fifth_worker_can_use_slots_17_and_18(campaign):
    common, evidence, before, _ = fifth(campaign)
    runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    for _ in range(18 - len(before['attempts'])):
        receipt = runner.reserve_provider_attempt(**common, attempt_kind='s02_start_session')
    context = {
        **{key: receipt[key] for key in ('campaign_id','attempt_id','attempt_ordinal','attempt_kind','baseline_epoch')},
        'matrix_sha256': common['matrix_sha256'], 'runtime_manifest_sha256': common['runtime_manifest_sha256'],
        'attempt_directory': common['ledger_path'].parent/'attempt-reservations', 'fresh_admin_worker':False,
    }
    assert runner._validate_worker_campaign_attempt(context)['attempt_ordinal'] == 18
    for epoch in (3, 4, 6):
        old = deepcopy(context); old['baseline_epoch'] = epoch
        with pytest.raises(ValueError):
            runner._validate_worker_campaign_attempt(old)
