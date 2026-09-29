"""STEP-016: authenticated playback reports bounded by actually sent PCM.

Only server-observed sentence boundaries are exact positions. Never estimate
characters by audio duration, and never let a client supply transcript text.
"""
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from uuid import uuid4

from backend.services.realtime_voice_turn_service import EffectiveText

logger = logging.getLogger(__name__)
CLIENT_FIELDS = {
    'client_playback_progress': {'played_audio_ms'},
    'client_sentence_played': {'sentence_id'},
    'client_reply_playback_completed': set(),
    'client_barge_in': {'played_audio_ms'},
    'client_audio_playback_completed': {'played_audio_ms'},
}


def observe_playback(method):
    """Flush finite playback observations after the gateway operation releases locks."""
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        playback = self.playback
        try:
            return await method(self, *args, **kwargs)
        finally:
            if playback is not None:
                events = playback.take_metrics()
                if events:
                    await self.metrics.emit_many(events)
    return wrapped


@dataclass
class Sentence:
    text: str = field(repr=False)
    start_bytes: int
    end_bytes: int | None = None
    acked: bool = False


@dataclass
class Reply:
    question_id: str
    text: str = field(default='',repr=False)
    audio_bytes: int = 0
    played_ms: int = 0
    ack_floor_ms: int = 0
    progress_seen: bool = False
    last_progress_at: float | None = None
    sentences: dict = field(default_factory=dict,repr=False)
    current_sentence: str | None = None
    text_finished: bool = False
    tts_finished: bool = False
    audio_completed: bool = False
    completed: bool = False
    interrupted: bool = False


class PlaybackEvidence:
    def __init__(self, *, call_id, capability_enabled):
        self.call_id = call_id
        self.capability_enabled = capability_enabled
        self.replies = {}
        self._client_sequence = 0
        self._provider_sequence = {}
        self._observations = {}
        self._evidence_observations = {}

    def metric(self, category):
        logger.info('voice.effective_text.%s=1', category)
        self._observations[category] = min(1000000000, self._observations.get(category, 0) + 1)

    def take_metrics(self):
        observations, self._observations = self._observations, {}
        evidence, self._evidence_observations = self._evidence_observations, {}
        return [('voice.effective_text.evidence', {'level': kind.split('.', 1)[1]}, amount)
                if kind.startswith('evidence.') else
                ('voice.effective_text.event', {'kind': kind}, amount)
                for kind, amount in observations.items()] + [
                    ('voice.effective_text.observed', {'level':level,'evidence':state}, amount)
                    for (level,state), amount in evidence.items()]

    def seen(self, event):
        return event.sequence <= self._provider_sequence.get(event.session_id,0)

    def feed(self, event, *, allow_buffered=False):
        if event.call_id != self.call_id:
            raise ValueError('playback_call_mismatch')
        if not allow_buffered and self.seen(event):
            return {}
        self._provider_sequence[event.session_id]=max(event.sequence, self._provider_sequence.get(event.session_id, 0))
        if not event.reply_id:
            return {}
        if event.reply_id not in self.replies:
            if not event.question_id or len(self.replies)>=4096:
                raise ValueError('playback_reply_identity_invalid')
            self.replies[event.reply_id]=Reply(event.question_id)
        reply=self.replies[event.reply_id]
        if reply.question_id != event.question_id:
            raise ValueError('playback_question_mismatch')
        if reply.interrupted or reply.completed:
            return {}
        if event.kind=='chat_text':
            if not isinstance(event.payload,str) or len(reply.text)+len(event.payload)>131072:
                raise ValueError('playback_text_invalid')
            reply.text+=event.payload
        elif event.kind=='tts_audio':
            if not isinstance(event.payload,bytes) or not event.payload or len(event.payload)%2:
                raise ValueError('playback_audio_invalid')
            reply.audio_bytes+=len(event.payload)
        elif event.kind=='sentence_started':
            # Provider IDs are optional; expose a server-owned boundary token.
            if reply.current_sentence is not None:
                raise ValueError('playback_sentence_overlap')
            sid=str(uuid4())
            content=event.payload.get('text','') if isinstance(event.payload,dict) else ''
            if not isinstance(content,str) or len(content)>131072:
                raise ValueError('playback_sentence_invalid')
            reply.sentences[sid]=Sentence(content,reply.audio_bytes)
            reply.current_sentence=sid
            return {'sentence_id':sid}
        elif event.kind=='sentence_finished':
            sid=reply.current_sentence
            if sid is not None:
                reply.sentences[sid].end_bytes=reply.audio_bytes
                reply.current_sentence=None
                return {'sentence_id':sid}
        elif event.kind=='text_finished':
            reply.text_finished=True
        elif event.kind=='tts_finished':
            reply.tts_finished=True
        return {}

    def is_stopped(self, reply_id):
        reply=self.replies.get(reply_id)
        return reply is not None and (reply.interrupted or reply.completed)

    def release_text(self, reply_id):
        """Release consumed proofs, retaining timing and late-event guards."""
        reply = self.replies[reply_id]
        reply.text = ''
        for sentence in reply.sentences.values():
            sentence.text = ''

    def audio_idle(self):
        return not any(r.audio_bytes and not (r.audio_completed or r.completed or r.interrupted)
                       for r in self.replies.values())

    def client(self, frame):
        kind=frame.get('type')
        required={'type','call_id','reply_id','event_seq'} | CLIENT_FIELDS.get(kind,set())
        if (kind not in CLIENT_FIELDS or set(frame)!=required or frame.get('call_id')!=self.call_id
                or frame.get('reply_id') not in self.replies or type(frame.get('event_seq')) is not int
                or frame['event_seq']<1):
            self.metric('invalid_client_event')
            raise ValueError('playback_event_invalid')
        seq=frame['event_seq']
        if seq<=self._client_sequence:
            self.metric('duplicate_client_event' if seq==self._client_sequence else 'out_of_order_client_event')
            return None
        reply=self.replies[frame['reply_id']]
        if reply.completed or reply.interrupted:
            self.metric('duplicate_client_event')
            return None
        if kind == 'client_audio_playback_completed':
            played = frame['played_audio_ms']
            if (not reply.tts_finished or not reply.audio_bytes or type(played) is not int
                    or played != reply.audio_bytes//48):
                self.metric('invalid_client_event')
                raise ValueError('playback_audio_not_finished')
            if reply.audio_completed:
                self.metric('duplicate_client_event')
                self._client_sequence = seq
                return None
            reply.audio_completed = True
            reply.played_ms = played
            reply.progress_seen = True
        elif kind in {'client_playback_progress','client_barge_in'}:
            played=frame['played_audio_ms']
            if type(played) is not int or not max(reply.played_ms,reply.ack_floor_ms)<=played<=reply.audio_bytes//48:
                self.metric('invalid_client_event')
                raise ValueError('playback_position_invalid')
            if played > reply.played_ms:
                reply.last_progress_at = time.monotonic()
            reply.played_ms=played
            reply.progress_seen=True
        elif kind=='client_sentence_played':
            sentence=reply.sentences.get(frame['sentence_id']) if isinstance(frame['sentence_id'],str) else None
            if sentence is None or sentence.end_bytes is None or sentence.end_bytes<=sentence.start_bytes:
                self.metric('invalid_client_event')
                raise ValueError('playback_sentence_not_sent')
            sentence.acked=True
            reply.ack_floor_ms=max(reply.ack_floor_ms,sentence.end_bytes//48)
        elif kind=='client_reply_playback_completed':
            if not reply.tts_finished or not reply.text_finished or not reply.audio_bytes or not reply.text:
                self.metric('invalid_client_event')
                raise ValueError('playback_reply_not_finished')
            reply.completed=True
            reply.audio_completed=True
            reply.played_ms=reply.audio_bytes//48
            reply.progress_seen=True
        if kind=='client_barge_in':
            reply.interrupted=True
        self._client_sequence=seq
        result=self.snapshot(frame['reply_id'])
        return result

    def snapshot(self, reply_id):
        mapping = self.capability_enabled('supports_playback_text_mapping')
        ack = self.capability_enabled('supports_sentence_playback_ack')
        result = self._snapshot(reply_id, mapping=mapping, ack=ack)
        self.metric('evidence.' + result.evidence)
        key = (result.evidence, 'verified' if mapping or ack else 'unverified')
        self._evidence_observations[key] = min(1000000000, self._evidence_observations.get(key, 0) + 1)
        return result

    def _snapshot(self, reply_id, *, mapping, ack):
        reply=self.replies[reply_id]
        position=reply.played_ms if reply.progress_seen else None
        if reply.completed:
            return EffectiveText(reply.text,'full',position,completed=True)
        # At an exact completed sentence boundary the prefix is known. For an
        # in-sentence position no interpolation or generated-prefix guess exists.
        if mapping and reply.progress_seen:
            prefix=best=''
            for sentence in reply.sentences.values():
                if not sentence.text or sentence.end_bytes is None:
                    break
                prefix+=sentence.text
                if (sentence.end_bytes<=reply.played_ms*48 and sentence.end_bytes>sentence.start_bytes
                        and reply.text.startswith(prefix)):
                    best=prefix
            if best:
                return EffectiveText(best,'exact_played',position,interrupted=reply.interrupted)
        else:
            self.metric('mapping_unavailable')
        if ack:
            confirmed=''.join(s.text for s in reply.sentences.values() if s.acked and s.text)
            if confirmed:
                return EffectiveText(confirmed,'confirmed_sentences',position,interrupted=reply.interrupted)
        else:
            self.metric('ack_unavailable')
        return EffectiveText('','none',position,interrupted=reply.interrupted)
