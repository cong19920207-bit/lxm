"""Purpose-separated deterministic HMAC tickets; no long-lived JWT in a URL."""
import base64
import asyncio
import hashlib
import hmac
import json
from datetime import datetime


class TicketError(ValueError):
    pass


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


class VoiceTicketCodec:
    def __init__(self, secret: bytes, *, purpose="voice_call_v1"):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise TicketError('ticket_signing_key_unavailable')
        if purpose not in {"voice_call_v1", "voice_reconnect_v1"}:
            raise TicketError("ticket_purpose_invalid")
        self._secret = secret
        self._purpose = purpose

    def issue(self, *, user_id, call_id, jti, device_id, expires_ms):
        payload = dict(purpose=self._purpose, user_id=user_id, call_id=call_id, jti=jti,
                       device=hashlib.sha256(device_id.encode()).hexdigest(), expires_ms=expires_ms)
        body = _b64(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode())
        return body+'.'+_b64(hmac.digest(self._secret, body.encode(), 'sha256'))

    def verify(self, ticket, *, call_id, device_id, now: datetime):
        try:
            if not isinstance(ticket, str) or len(ticket) > 2048 or now.tzinfo is None:
                raise ValueError()
            body, signature = ticket.split('.')
            if not hmac.compare_digest(signature, _b64(hmac.digest(self._secret, body.encode(), 'sha256'))):
                raise ValueError()
            value = json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
            if set(value) != {'purpose','user_id','call_id','jti','device','expires_ms'}:
                raise ValueError()
            if (value['purpose'] != self._purpose or value['call_id'] != call_id
                    or value['device'] != hashlib.sha256(device_id.encode()).hexdigest()
                    or type(value['expires_ms']) is not int or value['expires_ms'] <= int(now.timestamp()*1000)):
                raise ValueError()
            return value
        except (ValueError, TypeError, AttributeError):
            raise TicketError('ticket_invalid_or_expired') from None


async def consume_voice_ticket(db, *, codec, cache, leases, ticket, call_id, device_id, now):
    """One SQL winner; Origin and transport policy must be checked before this."""
    from sqlalchemy import select
    from backend.models.user import User
    from backend.models.realtime_voice import VoiceCall, VoiceCallCreateIdempotency
    value = codec.verify(ticket, call_id=call_id, device_id=device_id, now=now)
    try:
        user = await db.scalar(select(User).where(User.id == value['user_id']).with_for_update().execution_options(populate_existing=True))
        if user is None or user.is_banned or await cache.get(f'user_banned:{user.id}'):
            raise TicketError('ticket_user_unavailable')
        record = await db.scalar(select(VoiceCallCreateIdempotency).where(
            VoiceCallCreateIdempotency.call_id == call_id,
            VoiceCallCreateIdempotency.user_id == user.id).with_for_update().execution_options(populate_existing=True))
        call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id,
                                                     VoiceCall.user_id == user.id).with_for_update().execution_options(populate_existing=True))
        if (record is None or call is None or record.ticket_jti != value['jti']
                or record.ticket_consumed_at is not None or record.ticket_expires_at <= now.replace(tzinfo=None)
                or call.status not in ('deciding','ringing')):
            raise TicketError('ticket_not_consumable')
        if not await leases.owner_matches(user_id=user.id, call_id=call_id):
            raise TicketError('ticket_lease_expired')
        record.ticket_consumed_at = now.replace(tzinfo=None)
        await db.commit()
        return call
    except (Exception, asyncio.CancelledError):
        await db.rollback()
        raise
