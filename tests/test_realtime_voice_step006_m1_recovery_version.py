"""Recovery evidence gets a new identity while retaining v7's strict checks."""
from copy import deepcopy
import pytest

from backend.services.realtime_voice_capability_service import (
    CapabilityStateError, compute_evidence_fingerprint, validate_phase0_evidence_bundle,
)
from tests.test_realtime_voice_step006_evidence_import import _rehash
from tests.test_realtime_voice_step006_m1_protocol_v5 import native_bundle_v7


def recovery_bundle():
    bundle = native_bundle_v7()
    for record in bundle['records']:
        record.update(adapter_version='b937a78-step004-evidence-v8', evidence_suite_version='step004-o01-v8')
        record['evidence_fingerprint'] = compute_evidence_fingerprint(record)
    return _rehash(bundle)


@pytest.mark.parametrize('make_bundle', [native_bundle_v7, recovery_bundle])
def test_original_and_recovery_bundles_accept_their_own_paired_versions(make_bundle):
    assert validate_phase0_evidence_bundle(make_bundle())['record_count'] == 6


@pytest.mark.parametrize('adapter,suite', [('v7','v8'), ('v8','v7')])
def test_original_and_recovery_version_components_cannot_be_crossed(adapter, suite):
    bundle = recovery_bundle()
    for record in bundle['records']:
        record.update(adapter_version='b937a78-step004-evidence-'+adapter, evidence_suite_version='step004-o01-'+suite)
        record['evidence_fingerprint'] = compute_evidence_fingerprint(record)
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(bundle))


def test_recovery_bundle_cannot_mix_in_a_valid_original_record():
    bundle = recovery_bundle()
    bundle['records'][0] = deepcopy(native_bundle_v7()['records'][0])
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(bundle))


def test_recovery_truncate_still_requires_the_same_target():
    bundle = recovery_bundle()
    record = next(r for r in bundle['records'] if r['capability_key']=='supports_context_truncate')
    record['evidence_payload']['protocol_evidence']['truncate']['target_token'] = 'hmac256:'+'9'*24
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(bundle))
