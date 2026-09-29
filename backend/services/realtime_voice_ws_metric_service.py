"""Process-local accepted ASGI stream observations, without connection IDs."""
from contextlib import asynccontextmanager

_active_streams=0


def stream_metrics(socket):
    return getattr(getattr(getattr(socket,'app',None),'state',None),'voice_metrics',None)


async def observe_ws(metrics,events):
    if metrics is not None:await metrics.emit_many(events)


def ws_rejection(exc):
    from backend.services.realtime_voice_ticket_service import TicketError
    if isinstance(exc,TicketError):
        return {'socket_origin_or_url_rejected':'origin','wss_required':'tls'}.get(str(exc),'ticket')
    return 'connection'


def _concurrency():
    count=_active_streams
    bucket='0' if count==0 else '1' if count==1 else '2_5' if count<=5 else '6_10' if count<=10 else 'over_10'
    return ('voice.ws.concurrency',{'scope':'process_handlers','bucket':bucket},1)


@asynccontextmanager
async def observed_stream(metrics,channel):
    global _active_streams
    _active_streams+=1
    try:
        await observe_ws(metrics,[('voice.ws.connection',{'channel':channel,'result':'accepted'},1),_concurrency()])
        yield
    finally:
        _active_streams-=1
        await observe_ws(metrics,[('voice.ws.connection',{'channel':channel,'result':'disconnected'},1),_concurrency()])
