"""Independent consumer tests for the versioned 510/567 reconnect proof."""

from copy import deepcopy

import pytest

from backend.services.realtime_voice_capability_service import (
    CapabilityStateError, validate_phase0_evidence_bundle,
)
from tests.test_realtime_voice_step006_evidence_import import (
    _bundle, _rehash, _reconnect_causal_slice, _safe_event, VERIFIED_AT, EXPIRES_AT,
)


def native_bundle():
    bundle = _bundle()
    for record in bundle['records']:
        record['evidence_payload']['schema_version'] = 'phase0-capability-evidence/v4'
    record = next(r for r in bundle['records'] if r['capability_key'] == 'supports_session_reconnect')
    record.update(verification_result='passed', verified_at=VERIFIED_AT, expires_at=EXPIRES_AT)
    payload = record['evidence_payload']
    events, actions = _reconnect_causal_slice()
    payload.update(event_evidence=events, action_evidence=actions, capability_status='verified',
                   reason_code='hidden_seed_preserved_across_same_session_reconnect')
    events, actions = payload['event_evidence'], payload['action_evidence']
    for event in events:
        event['ordinal'] *= 10
    for action in actions:
        for key, value in action.items():
            if 'ordinal' in key and type(value) is int:
                action[key] *= 10
    seed = actions[0]
    seed['context_ack_ordinal'] = 15
    nonce = seed['correlation_tokens']['phase0.reconnect_seed']
    ack = deepcopy(events[0])
    ack.update(ordinal=15, received_at_ms=events[0]['received_at_ms'] + 20,
               event_id=567, event_name='ConversationCreated', target_event=False)
    ack['correlation_tokens'] = {
        'frame.session_id': seed['session_token'], 'phase0.reconnect_seed': nonce,
        'payload.items.0.item_id': 'hmac256:aaaaaaaaaaaaaaaaaaaaaaaa',
        'payload.items.1.item_id': 'hmac256:bbbbbbbbbbbbbbbbbbbbbbbb',
    }
    ack['payload_shape']['list_lengths'] = {'payload.items': 2}
    shape = ack['payload_shape']
    shape['object_keys'] = ['payload.items'] + [
        f'payload.items.{i}.{field}' for i in (0, 1)
        for field in ('item_id', 'role', 'text', 'timestamp')]
    shape['text_fields'] = {
        f'payload.items.{i}.{field}': {'chars': chars, 'token': 'hmac256:dddddddddddddddddddddddd'}
        for i, role_chars in ((0, 4), (1, 9))
        for field, chars in (('role', role_chars), ('text', 10))}
    shape['numeric_fields'] = {
        f'payload.items.{i}.timestamp': {'kind': 'integer'} for i in (0, 1)}
    events.insert(1, ack)
    actions.append({
        'action': 'provider_reconnect_context_written', 'success': True,
        'at_ms': events[0]['received_at_ms'] + 10,
        'provider_ordinal_after_send': 10, 'session_token': seed['session_token'],
        'correlation_tokens': {'phase0.reconnect_seed': nonce},
    })
    return _rehash(bundle)


def reconnect_payload(bundle):
    return next(r['evidence_payload'] for r in bundle['records']
                if r['capability_key'] == 'supports_session_reconnect')


def test_complete_v4_context_and_reconnect_chain_is_accepted():
    bundle = native_bundle()
    assert validate_phase0_evidence_bundle(bundle)['bundle_sha256'] == bundle['bundle_sha256']


@pytest.mark.parametrize('fault', ['missing_ack', 'wrong_session', 'wrong_nonce', 'wrong_type',
                                  'partial_pair', 'duplicate_ack', 'write_failed', 'ack_after_asr',
                                  'missing_fields', 'empty_text', 'invalid_role', 'no_timestamp'])
def test_v4_context_faults_are_rejected_even_with_new_valid_hashes(fault):
    bundle = native_bundle()
    payload = reconnect_payload(bundle)
    ack = payload['event_evidence'][1]
    if fault == 'missing_ack':
        payload['event_evidence'].remove(ack)
    elif fault == 'wrong_session':
        ack['correlation_tokens']['frame.session_id'] = 'hmac256:cccccccccccccccccccccccc'
    elif fault == 'wrong_nonce':
        ack['correlation_tokens']['phase0.reconnect_seed'] = 'hmac256:cccccccccccccccccccccccc'
    elif fault == 'wrong_type':
        ack['message_type'] = 'SERVER_ACK'
    elif fault == 'partial_pair':
        ack['payload_shape']['list_lengths']['payload.items'] = 1
    elif fault == 'duplicate_ack':
        duplicate = deepcopy(ack)
        duplicate['ordinal'] = 16
        payload['event_evidence'].insert(2, duplicate)
    elif fault == 'write_failed':
        payload['action_evidence'][-1]['success'] = False
    elif fault == 'ack_after_asr':
        payload['action_evidence'][0]['context_ack_ordinal'] = 25
        ack['ordinal'] = 25
    elif fault == 'missing_fields':
        ack['payload_shape']['object_keys'] = ['payload.items']
        ack['payload_shape']['text_fields'].clear()
        ack['payload_shape']['numeric_fields'].clear()
    elif fault == 'empty_text':
        ack['payload_shape']['text_fields']['payload.items.0.text']['chars'] = 0
    elif fault == 'invalid_role':
        ack['payload_shape']['text_fields']['payload.items.1.role']['chars'] = 4
    else:
        ack['payload_shape']['numeric_fields'].pop('payload.items.0.timestamp')
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(bundle))


def test_v3_record_bytes_remain_valid_and_cannot_smuggle_v4_fields():
    legacy = _bundle()
    assert validate_phase0_evidence_bundle(legacy)['bundle_sha256'] == legacy['bundle_sha256']
    mixed = native_bundle()
    reconnect_payload(mixed)['schema_version'] = 'phase0-capability-evidence/v3'
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(mixed))


@pytest.mark.parametrize('schema', [[], {}, None, 4])
def test_malformed_schema_is_rejected_as_validation_error(schema):
    bundle = native_bundle()
    reconnect_payload(bundle)['schema_version'] = schema
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(bundle))


def test_v3_unknown_567_diagnostic_event_remains_accepted():
    bundle = _bundle()
    # Before v4, 567 was an ordinary unknown ProviderEvent, not a context ACK.
    record = next(r for r in bundle['records'] if r['capability_key'] == 'supports_current_turn_rag_gate')
    payload = record['evidence_payload']
    event = deepcopy(payload['event_evidence'][-1])
    event.update(ordinal=event['ordinal'] + 1, event_id=567, event_name='ProviderEvent', target_event=False)
    payload['event_evidence'].append(event)
    assert validate_phase0_evidence_bundle(_rehash(bundle))


def recognition_prefix_bundle():
    bundle = native_bundle()
    payload = reconnect_payload(bundle)
    events = payload['event_evidence']
    question = next(a for a in payload['action_evidence'] if a['action'] == 'provider_reconnect_question_observed')
    final = next(e for e in events if e['ordinal'] == question['provider_event_ordinal'])
    info = deepcopy(final)
    info.update(ordinal=final['ordinal'] - 2, received_at_ms=final['received_at_ms'] - 2,
                event_id=450, event_name='ASRInfo', target_event=False)
    info['correlation_tokens']['payload.question_id'] = final['correlation_tokens']['payload.question_id']
    info['correlation_tokens'].pop('phase0.reconnect_question', None)
    partial = deepcopy(final)
    partial.update(ordinal=final['ordinal'] - 1, received_at_ms=final['received_at_ms'] - 1)
    partial['correlation_tokens'].pop('phase0.reconnect_question', None)
    events.extend([info, partial])
    events.sort(key=lambda e: e['ordinal'])
    return bundle, info, partial


def test_independent_consumer_accepts_one_continuous_recognition_window():
    bundle, _, _ = recognition_prefix_bundle()
    assert validate_phase0_evidence_bundle(_rehash(bundle))


@pytest.mark.parametrize('fault', ['missing_info', 'different_question', 'early_reply', 'ended', 'parse_error', 'unknown_parse_error'])
def test_independent_consumer_rejects_pollution_before_controlled_question(fault):
    bundle, info, partial = recognition_prefix_bundle()
    if fault == 'missing_info':
        reconnect_payload(bundle)['event_evidence'].remove(info)
    elif fault == 'different_question':
        partial['correlation_tokens']['payload.question_id'] = 'hmac256:' + 'e' * 24
    elif fault == 'early_reply':
        partial.update(event_id=550, event_name='ChatResponse', target_event=True)
    elif fault == 'ended':
        partial.update(event_id=459, event_name='ASREnded', target_event=False)
    elif fault == 'parse_error':
        partial['parse_error'] = True
    else:
        partial.update(event_id=999, event_name='ProviderEvent', target_event=False, parse_error=True)
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(bundle))


def playback_bundle_v6():
    from backend.services.realtime_voice_capability_service import compute_evidence_fingerprint
    bundle = native_bundle()
    for record in bundle['records']:
        record.update(adapter_version='b937a78-step004-evidence-v6', evidence_suite_version='step004-o01-v6')
        record['evidence_fingerprint'] = compute_evidence_fingerprint(record)
    payload = reconnect_payload(bundle)
    events, actions = payload['event_evidence'], payload['action_evidence']
    end_time = events[-1]['received_at_ms']
    for ordinal, event_id in ((81, 350), (82, 352), (83, 351), (84, 359), (85, 152)):
        events.append(_safe_event(event_id=event_id, ordinal=ordinal,
            received_at_ms=end_time + (ordinal - 80) * 20,
            audio=event_id == 352, sentence_boundary=event_id in (350, 351, 352)))
    confirmation = next(a for a in actions if a['action'] == 'provider_reconnect_context_confirmed')
    confirmation.update(at_ms=end_time + 200, provider_ordinal_after_ack=84)
    actions.append({'action': 'client_sentence_played', 'success': True,
        'at_ms': end_time + 90, 'provider_ordinal_after_ack': 84,
        'sentence_boundary_ordinal': 83, 'sentence_token': 'hmac256:' + '4' * 24})
    return bundle


def test_v6_post_end_confirmation_keeps_full_playback_proof_and_real_time():
    assert validate_phase0_evidence_bundle(_rehash(playback_bundle_v6()))


@pytest.mark.parametrize('repeat', [False, True])
def test_v6_playback_does_not_require_provider_sentence_text_mapping(repeat):
    bundle = playback_bundle_v6()
    payload = reconnect_payload(bundle)
    events, actions = payload['event_evidence'], payload['action_evidence']
    if repeat:
        second = [deepcopy(e) for e in events if 81 <= e['ordinal'] <= 83]
        for event in events:
            if event['ordinal'] >= 84:
                event['ordinal'] += 3
                event['received_at_ms'] += 60
        for event in second:
            event['ordinal'] += 3
            event['received_at_ms'] += 60
            event['correlation_tokens']['phase0.sentence_boundary'] = 'hmac256:' + '6' * 24
        events.extend(second)
        events.sort(key=lambda e: e['ordinal'])
        ack = deepcopy(actions[-1])
        ack.update(sentence_boundary_ordinal=86, provider_ordinal_after_ack=87,
                   sentence_token='hmac256:' + '6' * 24, at_ms=ack['at_ms'] + 60)
        actions.append(ack)
        next(a for a in actions if a['action'] == 'provider_reconnect_context_confirmed')['provider_ordinal_after_ack'] = 87
    for event in events:
        if event['event_name'] in ('TTSSentenceStart', 'TTSSentenceEnd'):
            event['correlation_tokens'].pop('payload.sentence_id', None)
            if repeat:
                # Repeated spoken text is legal; each ACK still binds a unique boundary.
                shape = event['payload_shape']
                shape['text_fields']['payload.text'] = {
                    'chars': 0 if event['event_name'] == 'TTSSentenceStart' else 4,
                    'token': 'hmac256:' + 'd' * 24,
                }
    assert validate_phase0_evidence_bundle(_rehash(bundle))


@pytest.mark.parametrize('fault', ['no_audio', 'no_tts_end', 'no_ack', 'duplicate_ack',
    'wrong_ack', 'late_ack', 'no_playback_tail', 'new_question', 'new_reply', 'unknown_parse_error'])
def test_v6_consumer_recomputes_playback_proof_even_with_valid_rehashed_record(fault):
    bundle = playback_bundle_v6()
    payload = reconnect_payload(bundle)
    events, actions = payload['event_evidence'], payload['action_evidence']
    ack = actions[-1]
    if fault == 'no_audio':
        events[:] = [e for e in events if not e['is_audio']]
    elif fault == 'no_tts_end':
        events[:] = [e for e in events if e['event_name'] != 'TTSEnded']
    elif fault == 'no_ack':
        actions.remove(ack)
    elif fault == 'duplicate_ack':
        actions.append(deepcopy(ack))
    elif fault == 'wrong_ack':
        ack['sentence_boundary_ordinal'] = 82
    elif fault == 'late_ack':
        ack['at_ms'] = events[-1]['received_at_ms'] + 1
    elif fault == 'no_playback_tail':
        events[:] = [e for e in events if e['ordinal'] <= 80]
    else:
        event = deepcopy(events[-1])
        event.update(ordinal=86, received_at_ms=event['received_at_ms'] + 1)
        if fault == 'new_question':
            event.update(event_id=451, event_name='ASRResponse', target_event=False)
        elif fault == 'new_reply':
            event.update(event_id=550, event_name='ChatResponse', target_event=True)
            event['correlation_tokens']['payload.reply_id'] = 'hmac256:' + 'e' * 24
        else:
            event.update(event_id=999, event_name='ProviderEvent', target_event=False, parse_error=True)
        events.append(event)
    with pytest.raises(CapabilityStateError):
        validate_phase0_evidence_bundle(_rehash(bundle))
