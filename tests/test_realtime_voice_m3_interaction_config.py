"""Approved M3 defaults stay configurable and do not mutate published configs."""
from copy import deepcopy
import pytest
from backend.constants.realtime_voice_config import get_default_voice_call_config
from backend.services.realtime_voice_config_service import validate_voice_bundle
from tests.test_realtime_voice_m2_shared_extension import REF

DEFAULTS = dict(vad_rms_threshold=0.015, candidate_ms=200, sustained_ms=600,
                goodbye_timeout_ms=10000, post_playback_buffer_ms=800, time_low_seconds=60)


def test_defaults_and_legacy_config():
    config = get_default_voice_call_config(REF)
    assert config['interaction'] == DEFAULTS
    del config['interaction']
    before = deepcopy(config)
    assert validate_voice_bundle('voice_call_config', config) == []
    assert config == before


@pytest.mark.parametrize('patch', [dict(vad_rms_threshold=True), dict(vad_rms_threshold=0),
    dict(vad_rms_threshold=float('nan')), dict(candidate_ms=251), dict(candidate_ms=179),
    dict(sustained_ms=250, candidate_ms=250), dict(sustained_ms=2001),
    dict(goodbye_timeout_ms=999), dict(time_low_seconds=0), dict(time_low_seconds=301),
    dict(unknown=1)])
def test_reject_invalid_interaction(patch):
    config = get_default_voice_call_config(REF)
    config['interaction'] = dict(DEFAULTS, **patch)
    assert any(i['field'].startswith('interaction') for i in validate_voice_bundle('voice_call_config', config))


def test_snapshot_compatibility_and_custom_values():
    from datetime import datetime, timezone
    from backend.constants.realtime_voice_config import get_default_voice_call_script
    from backend.services.realtime_voice_config_service import content_sha256
    from backend.services.realtime_voice_runtime_config_service import LoadedVoiceConfig, VoiceRuntimeBundle, RuntimeConfigSource
    for interaction in (None, dict(candidate_ms=220, time_low_seconds=40)):
        config = get_default_voice_call_config(REF)
        config.pop('interaction', None)
        if interaction is not None:
            config['interaction'] = interaction
        original = deepcopy(config)
        def loaded(key, value):
            return LoadedVoiceConfig(key, 3, 1, content_sha256(value), datetime.now(timezone.utc),
                                     value, RuntimeConfigSource.MYSQL, False)
        snapshot = VoiceRuntimeBundle(config=loaded('voice_call_config', config),
            script=loaded('voice_call_script', get_default_voice_call_script()),
            mysql_anchors_available=True, persona_anchors=(REF,)).build_snapshot().config_snapshot
        assert dict(snapshot['resolved_config']['interaction']) == dict(DEFAULTS, **(interaction or {}))
        assert snapshot['config_content_sha256'] == content_sha256(original)
        assert config == original
