from datetime import datetime,timezone
from uuid import uuid4
import pytest


def test_ticket_is_deterministic_bound_short_lived_and_tamper_evident():
    from backend.services.realtime_voice_ticket_service import VoiceTicketCodec,TicketError
    codec=VoiceTicketCodec(b'x'*32)
    now=datetime(2026,9,9,tzinfo=timezone.utc)
    fields=dict(user_id=1,call_id=str(uuid4()),jti=str(uuid4()),device_id=str(uuid4()),expires_ms=int(now.timestamp()*1000)+30000)
    ticket=codec.issue(**fields)
    assert ticket==codec.issue(**fields)
    assert codec.verify(ticket,call_id=fields['call_id'],device_id=fields['device_id'],now=now)['jti']==fields['jti']
    with pytest.raises(TicketError):codec.verify(ticket+'x',call_id=fields['call_id'],device_id=fields['device_id'],now=now)
    with pytest.raises(TicketError):codec.verify(ticket,call_id=fields['call_id'],device_id=str(uuid4()),now=now)
    with pytest.raises(TicketError):codec.verify(ticket,call_id=fields['call_id'],device_id=fields['device_id'],now=datetime.fromtimestamp(fields['expires_ms']/1000,timezone.utc))
