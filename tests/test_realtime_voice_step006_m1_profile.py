"""New isolated runner profile never rewrites or reuses historical budgets."""
import importlib.util
from pathlib import Path
import sys
import uuid
import pytest


def runner_copy():
    name = 'm1_profile_test_' + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, Path('scripts/realtime_voice_m1_campaign_runner.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_protocol_profile_binds_candidate_dimensions_closure_and_five_slot_cap():
    m = runner_copy()
    m.configure_m1_protocol_profile()
    assert m.PHASE0_RELATIVE_ROOT.as_posix() == 'tmp/phase0-step004-m1-acceptance-20260907'
    assert m.PHASE0_ADAPTER_VERSION == 'b937a78-step004-evidence-v7'
    assert m.PHASE0_EVIDENCE_SUITE_VERSION == 'step004-o01-v7'
    assert m.CAMPAIGN_ATTEMPT_LIMIT == 5
    assert set(m.BASELINE_BATCHES) == {1}
    paths = m.discover_runtime_closure_paths(Path.cwd())
    assert str(m.PHASE0_RELATIVE_ROOT / 'backend/phase0_realtime_voice/m1_protocol.py') in paths
    assert not any('phase0-step004-s01-fix-20260906' in p for p in paths)
    legacy = runner_copy()
    assert legacy.PHASE0_ADAPTER_VERSION.endswith('v5')
    assert legacy.CAMPAIGN_ATTEMPT_LIMIT == 15


def test_protocol_profile_cannot_reserve_without_explicit_frozen_authorization(tmp_path):
    m = runner_copy()
    m.configure_m1_protocol_profile()
    with pytest.raises(ValueError, match='授权'):
        m.reserve_provider_attempt(ledger_path=None, project_root=tmp_path, campaign_id='m1-protocol-test',
                                   matrix_sha256='a'*64, runtime_manifest_sha256='b'*64,
                                   baseline={}, attempt_kind='s01_start_session')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_cli_profile_rejects_provider_modes_before_loading_environment_or_database():
    m = runner_copy()
    args = m._build_argument_parser().parse_args(['reserve-attempt', '--m1-protocol'])
    with pytest.raises(ValueError, match='授权'):
        await m._run_cli(args)


def test_explicit_authorization_is_bound_and_fifth_attempt_exhausts_new_ledger(tmp_path):
    import json
    from tests.test_realtime_voice_step006_campaign_runner import _campaign_baseline
    m = runner_copy()
    m.configure_m1_protocol_profile()
    frozen = m.FrozenCampaign(campaign_id='m1-protocol-unit-fixture', matrix_sha256='a'*64,
                             runtime_manifest_sha256='b'*64, ledger_path=tmp_path/'unused')
    authorization = tmp_path/'synthetic-authorization.json'
    value = {'schema_version':'m1-protocol-user-authorization/v1',
             'campaign_id':frozen.campaign_id, 'matrix_sha256':frozen.matrix_sha256,
             'runtime_manifest_sha256':frozen.runtime_manifest_sha256,
             'max_provider_attempts':5, 'automatic_retries':0,
             'scope':'m1_protocol_reconnect_admin_ack','authorized_by':'user','confirmed_at':'2026-09-07T00:00:00Z'}
    authorization.write_text(json.dumps(value))
    for incorrect_limit in (3, 6, True):
        authorization.write_text(json.dumps({**value, 'max_provider_attempts': incorrect_limit}))
        with pytest.raises(ValueError, match='授权'):
            m.authorize_m1_protocol_campaign(authorization, frozen)
    authorization.write_text(json.dumps(value))
    m.authorize_m1_protocol_campaign(authorization, frozen)
    baseline = _campaign_baseline()
    with pytest.raises(ValueError, match='版本'):
        m.reserve_provider_attempt(ledger_path=None, project_root=tmp_path,
            campaign_id=frozen.campaign_id, matrix_sha256='a'*64, runtime_manifest_sha256='b'*64,
            baseline=baseline, attempt_kind='s01_start_session')
    baseline['evidence_dimensions'].update(adapter_version=m.PHASE0_ADAPTER_VERSION,
        evidence_suite_version=m.PHASE0_EVIDENCE_SUITE_VERSION, model_version='2.2.0.0')
    baseline['evidence_fingerprint'] = m._canonical_sha256(baseline['evidence_dimensions'])
    for kind in ('s01_start_session','s01_reconnect','s01_start_session','s01_reconnect','admin_ack'):
        receipt = m.reserve_provider_attempt(ledger_path=None, project_root=tmp_path,
            campaign_id=frozen.campaign_id, matrix_sha256='a'*64, runtime_manifest_sha256='b'*64,
            baseline=baseline, attempt_kind=kind)
    assert receipt['attempt_ordinal'] == 5
    assert receipt['remaining_attempts'] == 0
    with pytest.raises(RuntimeError):
        m.reserve_provider_attempt(ledger_path=None, project_root=tmp_path,
            campaign_id=frozen.campaign_id, matrix_sha256='a'*64, runtime_manifest_sha256='b'*64,
            baseline=baseline, attempt_kind='s01_start_session')
    value['runtime_manifest_sha256'] = 'c'*64
    authorization.write_text(json.dumps(value))
    with pytest.raises(ValueError): m.authorize_m1_protocol_campaign(authorization, frozen)
