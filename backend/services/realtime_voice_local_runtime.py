"""In-process call owner handles; Redis failure must not prevent local stop.

The gateway must register before CONNECTED and remove only after end commits.
These handles contain no public/client-supplied meter or provider credentials.
"""
from dataclasses import dataclass
from typing import Awaitable, Callable
from backend.services.realtime_voice_quota_service import ConnectedMeter


@dataclass
class LocalVoiceCall:
    meter: ConnectedMeter
    stop: Callable[[], Awaitable[None]]
    set_end_reason: Callable[[str], None] | None = None
    # Hooks stage facts/jobs in the same DB transaction as the terminal state.
    # They must not commit or perform irreversible external writes.
    final_flush: Callable[..., Awaitable[None]] | None = None
    on_finalize: Callable[..., Awaitable[None]] | None = None
    reconnect: object | None = None
    closed_event: object | None = None


local_voice_calls: dict[str, LocalVoiceCall] = {}
