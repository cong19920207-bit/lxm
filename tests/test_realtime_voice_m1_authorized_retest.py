"""User-authorized continuation preserves historical rounds and shared budget."""

import json
from copy import deepcopy

import pytest

from scripts import realtime_voice_m1_campaign_runner as runner
from tests.test_realtime_voice_step006_campaign_runner import _campaign_baseline


@pytest.fixture
def campaign(tmp_path):
    common = {
        "project_root": tmp_path,
        "ledger_path": runner.campaign_ledger_path("retest", project_root=tmp_path),
        "campaign_id": "retest",
        "matrix_sha256": "a" * 64,
        "runtime_manifest_sha256": "b" * 64,
        "baseline": _campaign_baseline(marker="a"),
    }
    runner.reserve_provider_attempt(**common, attempt_kind="s01_start_session")
    evidence = tmp_path / "regression.json"
    evidence.write_text(json.dumps({"passed": True}))
    common.update(matrix_sha256="c" * 64, runtime_manifest_sha256="d" * 64)
    runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence)
    runner.reserve_provider_attempt(**common, attempt_kind="s01_start_session")
    before = json.loads(common["ledger_path"].read_text())
    common.update(matrix_sha256="e" * 64, runtime_manifest_sha256="f" * 64)
    evidence.write_text(json.dumps({"passed": True, "authorized_additional_round": True}))
    return common, evidence, before


def test_explicit_retest_preserves_old_epochs_attempts_and_shared_cap(campaign):
    common, evidence, before = campaign
    receipt = runner.advance_campaign_to_final_batch(
        **common, regression_evidence_path=evidence, authorized_retest=True,
    )
    assert receipt["active_baseline_epoch"] == 3
    after = json.loads(common["ledger_path"].read_text())
    assert after["baseline_epochs"][:2] == before["baseline_epochs"]
    assert after["attempts"] == before["attempts"]
    assert after["baseline_epochs"][2]["batch"] == "authorized_retest"
    assert after["baseline_epochs"][2]["previous_epoch_sha256"] == before["baseline_epochs"][1]["epoch_sha256"]
    for _ in range(13):
        runner.reserve_provider_attempt(**common, attempt_kind="s02_start_session")
    with pytest.raises(RuntimeError, match="15"):
        runner.reserve_provider_attempt(**common, attempt_kind="s03_start_session")


def test_normal_advance_still_cannot_start_third_round(campaign):
    common, evidence, before = campaign
    with pytest.raises(RuntimeError, match="final|两"):
        runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence)
    assert json.loads(common["ledger_path"].read_text()) == before


def test_retest_requires_authorization_in_evidence_and_cannot_repeat(campaign):
    common, evidence, before = campaign
    evidence.write_text(json.dumps({"passed": True}))
    with pytest.raises(ValueError, match="授权"):
        runner.advance_campaign_to_final_batch(
            **common, regression_evidence_path=evidence, authorized_retest=True,
        )
    assert json.loads(common["ledger_path"].read_text()) == before
    evidence.write_text(json.dumps({"passed": True, "authorized_additional_round": True}))
    runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    with pytest.raises(RuntimeError):
        runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)


def test_worker_accepts_authorized_third_round_receipt(campaign):
    common, evidence, _ = campaign
    runner.advance_campaign_to_final_batch(**common, regression_evidence_path=evidence, authorized_retest=True)
    receipt = runner.reserve_provider_attempt(**common, attempt_kind="s01_start_session")
    context = {
        **{key: receipt[key] for key in ("campaign_id", "attempt_id", "attempt_ordinal", "attempt_kind", "baseline_epoch")},
        "matrix_sha256": common["matrix_sha256"],
        "runtime_manifest_sha256": common["runtime_manifest_sha256"],
        "attempt_directory": common["ledger_path"].parent / "attempt-reservations",
        "fresh_admin_worker": False,
        "expected_reconnect_ordinal": 4,
    }
    assert runner._validate_worker_campaign_attempt(context)["baseline_epoch"] == 3
    invalid = deepcopy(context)
    invalid["baseline_epoch"] = 6
    with pytest.raises(ValueError):
        runner._validate_worker_campaign_attempt(invalid)
