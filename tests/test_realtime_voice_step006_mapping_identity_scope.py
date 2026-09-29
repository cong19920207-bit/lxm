"""Identical text is ambiguous within a reply, not across separate replies."""
from copy import deepcopy
import pytest

from backend.services.realtime_voice_capability_service import (
    CapabilityStateError, _validate_mapping_window,
)
from tests.test_realtime_voice_step006_evidence_import import _safe_event


def repeated_text_windows(*, same_reply=False):
    events = []
    for offset in (0, 3):
        for index, event_id in enumerate((350, 352, 351), 1):
            event = _safe_event(event_id=event_id, ordinal=offset+index,
                                received_at_ms=(offset+index)*1000, audio=event_id==352)
            tokens = event['correlation_tokens']
            tokens.pop('payload.sentence_id', None)
            if offset and not same_reply:
                tokens['payload.question_id'] = 'hmac256:'+'d'*24
                tokens['payload.reply_id'] = 'hmac256:'+'e'*24
            if event_id in (350, 351):
                event['payload_shape']['text_fields']['payload.text'] = {
                    'chars':0 if event_id==350 else 20,
                    'token':'hmac256:'+('a' if event_id==350 else 'b')*24,
                }
            events.append(event)
    return events


def test_identical_end_text_in_two_distinct_replies_is_valid():
    assert _validate_mapping_window(repeated_text_windows(), path='fixture')[1]['ordinal']==3


def test_replayed_identical_end_text_within_one_reply_stays_rejected():
    with pytest.raises(CapabilityStateError, match='歧义'):
        _validate_mapping_window(repeated_text_windows(same_reply=True), path='fixture')


def test_separate_reply_cannot_hide_duplicate_boundary_in_first_reply():
    events = repeated_text_windows()
    duplicate = deepcopy(events[:3])
    for event in duplicate:
        event['ordinal'] += 6
        event['received_at_ms'] += 6000
    with pytest.raises(CapabilityStateError, match='歧义'):
        _validate_mapping_window(events+duplicate, path='fixture')
