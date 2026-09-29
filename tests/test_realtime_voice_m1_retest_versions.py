"""A repaired probe must not reuse the prior S01 capability fingerprint."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from scripts import realtime_voice_m1_campaign_runner as runner
from tests.test_realtime_voice_step006_campaign_runner import _draft, _phase0_ack_record


@pytest.fixture
def producer():
    root = Path(__file__).resolve().parents[1]
    path = root / runner.PHASE0_RELATIVE_ROOT / "backend/phase0_realtime_voice/provider_evidence.py"
    spec = importlib.util.spec_from_file_location("phase0_retest_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repaired_runtime_changes_fingerprint_and_agrees_with_campaign(producer):
    current = producer.evidence_dimensions(model_version=_draft()["s2s"]["model_version"])
    previous = {**current, "adapter_version": "b937a78-step004-evidence-v4", "evidence_suite_version": "step004-o01-v4"}
    assert producer.evidence_fingerprint(current) != producer.evidence_fingerprint(previous)
    assert current["adapter_version"] == runner.PHASE0_ADAPTER_VERSION
    assert current["evidence_suite_version"] == runner.PHASE0_EVIDENCE_SUITE_VERSION
    assert producer.evidence_fingerprint(current) == runner._canonical_sha256(current)


def test_new_campaign_rejects_old_identity_without_rewriting_old_record(producer):
    current = _phase0_ack_record()
    converted = runner.convert_phase0_ack_record(current, draft_snapshot=_draft())
    assert converted["evidence_fingerprint"] == current["evidence_fingerprint"]
    old = {**current, "adapter_version": "b937a78-step004-evidence-v3", "evidence_suite_version": "step004-o01-v3"}
    old["evidence_fingerprint"] = producer.evidence_fingerprint(old)
    old["report_sha256"] = producer.sha256_canonical({k: v for k, v in old.items() if k != "report_sha256"})
    before = deepcopy(old)
    with pytest.raises(ValueError, match="六维不一致"):
        runner.convert_phase0_ack_record(old, draft_snapshot=_draft())
    assert old == before
