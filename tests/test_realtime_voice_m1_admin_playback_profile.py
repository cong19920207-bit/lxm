"""The single admin playback allowance cannot authorize another scenario."""
from pathlib import Path
import uuid
import pytest
from scripts import realtime_voice_m1_campaign_runner as r

@pytest.fixture
def profile(monkeypatch):
    for key,value in list(vars(r).items()):
        if key.isupper():monkeypatch.setattr(r,key,value)
    configure=getattr(r,'configure_m1_admin_ack_profile',None)
    assert callable(configure)
    configure()
    return {'attempt_directory':Path('/tmp'),'campaign_id':'m1-admin-playback-20260909','matrix_sha256':'a'*64,'runtime_manifest_sha256':'b'*64,'baseline_epoch':5,'attempt_id':str(uuid.uuid4()),'attempt_ordinal':7,'attempt_kind':'admin_ack','fresh_admin_worker':True}

def test_one_fresh_admin_playback_allowed(profile):
    assert r._validate_worker_campaign_attempt(profile)['attempt_ordinal']==7
    assert r.PHASE0_ADAPTER_VERSION.endswith('v9')
    assert not r.M1_RECOVERY_PROFILE and not r.M1_CANCEL_ONLY_PROFILE

@pytest.mark.parametrize('change',[{'attempt_ordinal':6},{'attempt_ordinal':8},{'baseline_epoch':4},{'attempt_kind':'s01_start_session'},{'attempt_kind':'admin_connection'},{'fresh_admin_worker':False},{'expected_reconnect_ordinal':7}])
def test_other_attempts_rejected(profile,change):
    with pytest.raises(ValueError):r._validate_worker_campaign_attempt({**profile,**change})

@pytest.mark.parametrize('case',['empty','silent','wrong_rate','valid'])
def test_stimulus_must_contain_real_non_silent_pcm(tmp_path,case):
    import struct,wave
    path=tmp_path/'stimulus.wav'
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000 if case=='wrong_rate' else 16000)
        wav.writeframes(b'' if case=='empty' else struct.pack('<h',0 if case=='silent' else 1200)*32000)
    validator=getattr(r,'validate_admin_playback_stimulus',None)
    assert callable(validator)
    if case=='valid':assert validator(path)['pcm_bytes']==64000
    else:
        with pytest.raises(ValueError):validator(path)

def test_explicit_manual_retry_binds_only_next_number(profile):
    r.configure_m1_admin_ack_profile(manual_retry=True)
    retry={**profile,'attempt_ordinal':8}
    assert r._validate_worker_campaign_attempt(retry)['attempt_ordinal']==8
    for number in (7,9):
        with pytest.raises(ValueError):r._validate_worker_campaign_attempt({**retry,'attempt_ordinal':number})
