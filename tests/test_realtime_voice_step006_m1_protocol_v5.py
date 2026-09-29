"""Independent, synthetic v5 protocol proof tests; no external calls/storage."""
from copy import deepcopy
import pytest

from backend.services.realtime_voice_capability_service import (
    CapabilityStateError, _validate_evidence_record, compute_evidence_fingerprint,
)
from tests.test_realtime_voice_step006_evidence_import import (
    _record, _safe_event, _canonical_sha256, RUN_ID, VERIFIED_AT, EXPIRES_AT,
)


def rehash(record):
    record['report_sha256'] = _canonical_sha256({k:v for k,v in record.items() if k != 'report_sha256'})
    return record


def native_record():
    record = _record(RUN_ID, 'supports_context_truncate')
    record.update(adapter_version='b937a78-step004-evidence-v7', evidence_suite_version='step004-o01-v7',
                  verification_result='passed', verified_at=VERIFIED_AT, expires_at=EXPIRES_AT)
    record['evidence_fingerprint'] = compute_evidence_fingerprint(record)
    events = [_safe_event(event_id=e, ordinal=i, received_at_ms=i*1000, audio=e==352)
              for i,e in enumerate((350,352,359), 1)]
    events[1]['payload_shape']['binary_fields'] = {'payload':480000}
    item_token, prefix_token = 'hmac256:'+'3'*24, 'hmac256:'+'b'*24
    for ordinal, event_id in ((4,569),(5,570),(6,569)):
        event = _safe_event(ordinal=ordinal, received_at_ms=ordinal*1000)
        event.update(event_id=event_id, event_name='ProviderEvent', target_event=False)
        event['correlation_tokens'] = {'frame.session_id':'hmac256:'+'1'*24}
        if event_id == 569:
            event['correlation_tokens']['payload.items.0.item_id'] = item_token
            event['payload_shape']['list_lengths'] = {'payload.items':1}
            event['payload_shape']['text_fields'] = {
                'payload.items.0.text':{'chars':20 if ordinal == 4 else 8, 'token':prefix_token if ordinal == 6 else 'hmac256:'+'c'*24},
                'payload.items.0.role':{'chars':9, 'token':'hmac256:'+'d'*24},
            }
        events.append(event)
    proof = {
        'status':'verified', 'reason':'truncate_target_prefix_retained',
        'target_token':'hmac256:'+'3'*24, 'item_token':item_token, 'prefix_token':prefix_token,
        'session_token':'hmac256:'+'1'*24, 'stop_token':'hmac256:'+'e'*24,
        'reply_generation':1, 'played_ms':2500, 'received_samples':240000,
        'progress_at_ms':3000, 'progress_ordinal':3, 'before_chars':20, 'after_chars':8,
        'retained_prefix':True,
        'operations':[
            {'request_event':request, 'before_ordinal':ack-1, 'after_ordinal':ack-1,
             'sent_at_ms':(ack-1)*1000+1, 'ack_event':ack_event, 'ack_ordinal':ack, 'ack_at_ms':ack*1000}
            for request,ack_event,ack in ((512,569,4),(513,570,5),(512,569,6))],
    }
    payload = record['evidence_payload']
    payload.update(schema_version='phase0-capability-evidence/v5', capability_status='verified',
                   reason_code='truncate_target_prefix_retained', event_evidence=events,
                   protocol_evidence={'truncate':proof}, action_evidence=[{
                       'action':'client_stop_playback_applied', 'success':True, 'at_ms':3000,
                       'stop_token':proof['stop_token'], 'target_reply_generation':1,
                       'provider_ordinal_after_ack':3}])
    return rehash(record)


def validate(record):
    return _validate_evidence_record(record, expected_source='phase0_import', allow_error=False, path='record')


def native_bundle_v7():
    from tests.test_realtime_voice_step006_context_evidence_v4 import playback_bundle_v6
    from tests.test_realtime_voice_step006_evidence_import import _rehash
    bundle = playback_bundle_v6()
    truncate = native_record()
    for index, record in enumerate(bundle['records']):
        if record['capability_key'] == 'supports_context_truncate':
            bundle['records'][index] = deepcopy(truncate)
            record = bundle['records'][index]
        record.update(adapter_version='b937a78-step004-evidence-v7', evidence_suite_version='step004-o01-v7')
        record['evidence_fingerprint'] = compute_evidence_fingerprint(record)
        payload = record['evidence_payload']
        payload.update(schema_version='phase0-capability-evidence/v5',
                       protocol_evidence=deepcopy(truncate['evidence_payload']['protocol_evidence']))
        if record['capability_key'] == 'supports_current_turn_rag_gate':
            record.update(verification_result='failed', verified_at=None, expires_at=None)
            payload.update(capability_status='failed', reason_code='same_turn_probe_not_confirmed_or_double_reply')
            for event in payload['event_evidence']: event.pop('probe_match', None)
    return _rehash(bundle)


def test_six_v7_records_can_form_one_strict_bundle_with_credible_false_capabilities():
    from backend.services.realtime_voice_capability_service import validate_phase0_evidence_bundle
    bundle = native_bundle_v7()
    assert validate_phase0_evidence_bundle(bundle)['record_count'] == 6


def test_independent_consumer_accepts_complete_progress_request_ack_readback_chain():
    assert validate(native_record())['verification_result'] == 'passed'


def test_candidate_producer_and_independent_consumer_agree_on_new_truncate_record():
    import importlib.util
    from pathlib import Path
    from datetime import datetime, timezone
    import uuid
    path = Path('tmp/phase0-step004-m1-acceptance-20260907/backend/phase0_realtime_voice/provider_evidence.py')
    spec = importlib.util.spec_from_file_location('isolated_m1_evidence_test', path)
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    payload = native_record()['evidence_payload']
    bundle = producer.build_evidence_bundle(
        events=payload['event_evidence'], actions=payload['action_evidence'], observations={},
        model_version='2.2.0.0', evidence_run_id=str(uuid.uuid4()),
        evidence_report_ids={key:str(uuid.uuid4()) for key in producer.CAPABILITY_KEYS},
        tested_at=datetime.now(timezone.utc), runtime_conditions=payload['runtime_conditions'],
        protocol_evidence=payload['protocol_evidence'])
    record = next(r for r in bundle['records'] if r['capability_key'] == 'supports_context_truncate')
    assert validate(record)['verification_result'] == 'passed'


def test_v5_no_change_readback_is_a_credible_failed_result_not_missing_ack():
    record = native_record()
    payload = record['evidence_payload']
    proof = payload['protocol_evidence']['truncate']
    proof.update(status='failed', reason='truncate_readback_not_shortened', after_chars=20)
    payload['event_evidence'][-1]['payload_shape']['text_fields']['payload.items.0.text']['chars'] = 20
    payload.update(capability_status='failed', reason_code=proof['reason'])
    record.update(verification_result='failed', verified_at=None, expires_at=None)
    assert validate(rehash(record))['verification_result'] == 'failed'


@pytest.mark.parametrize('fault', ['missing_request','wrong_ack','wrong_target','wrong_session','wrong_type',
    'pre_send_ack','wrong_prefix','no_actual_stop','impossible_progress','partial_audio','wrong_generation',
    'no_prefix','unknown_field','raw_token','version_mix','late_question','duplicate_ack','missing_role','wrong_status',
    'splice_audio_reply', 'splice_readback_item', 'late_duplicate_ack'])
def test_fresh_hash_cannot_hide_incomplete_or_forged_protocol_chain(fault):
    record = native_record()
    payload = record['evidence_payload']
    proof = payload['protocol_evidence']['truncate']
    if fault == 'missing_request': proof['operations'].pop(1)
    elif fault == 'wrong_ack': proof['operations'][1]['ack_event'] = 569
    elif fault == 'wrong_target': payload['event_evidence'][5]['correlation_tokens']['payload.items.0.item_id'] = 'hmac256:'+'f'*24
    elif fault == 'wrong_session': payload['event_evidence'][4]['correlation_tokens']['frame.session_id'] = 'hmac256:'+'f'*24
    elif fault == 'wrong_type': payload['event_evidence'][4]['message_type'] = 'SERVER_ACK'
    elif fault == 'pre_send_ack': proof['operations'][1]['after_ordinal'] = 5
    elif fault == 'wrong_prefix': proof['prefix_token'] = 'hmac256:'+'f'*24
    elif fault == 'no_actual_stop': payload['action_evidence'] = []
    elif fault == 'impossible_progress': proof['played_ms'] = 10000
    elif fault == 'partial_audio': proof['received_samples'] -= 1000
    elif fault == 'wrong_generation': proof['reply_generation'] = 2
    elif fault == 'no_prefix': proof['retained_prefix'] = False
    elif fault == 'unknown_field': proof['user_notes'] = 'raw content'
    elif fault == 'raw_token': proof['item_token'] = 'raw-item-id'
    elif fault == 'version_mix': record['adapter_version'] = 'old-adapter'; record['evidence_fingerprint'] = compute_evidence_fingerprint(record)
    elif fault == 'late_question': payload['event_evidence'][4] = _safe_event(event_id=451, ordinal=5, received_at_ms=5000)
    elif fault == 'duplicate_ack': payload['event_evidence'].append(deepcopy(payload['event_evidence'][4]))
    elif fault == 'missing_role': payload['event_evidence'][5]['payload_shape']['text_fields'].pop('payload.items.0.role')
    elif fault == 'wrong_status': proof['status'] = 'failed'
    elif fault == 'splice_audio_reply':
        proof['target_token'] = 'hmac256:'+'f'*24
        for event in payload['event_evidence'][:3]: event['correlation_tokens']['payload.reply_id'] = proof['target_token']
    elif fault == 'splice_readback_item':
        proof['item_token'] = 'hmac256:'+'f'*24
        for event in (payload['event_evidence'][3],payload['event_evidence'][5]):
            event['correlation_tokens']['payload.items.0.item_id'] = proof['item_token']
    elif fault == 'late_duplicate_ack':
        late = deepcopy(payload['event_evidence'][-1])
        late.update(ordinal=7, received_at_ms=7000)
        payload['event_evidence'].append(late)
    with pytest.raises(CapabilityStateError): validate(rehash(record))
