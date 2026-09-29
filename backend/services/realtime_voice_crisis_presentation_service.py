"""Public frozen resource copy; never select crisis text or matching keywords."""
from datetime import datetime
from sqlalchemy import func, select
from backend.models.realtime_voice import VoiceCrisisRecord
from backend.constants.realtime_voice_config import get_default_voice_call_script


async def crisis_presentations(db, calls, *, now=None):
    now = now or datetime.utcnow()
    live = {call.call_id: call for call in calls
            if call.deleted_at is None and call.deletion_fence_at is None}
    if not live:
        return {}
    rows = await db.execute(select(VoiceCrisisRecord.call_id, func.max(VoiceCrisisRecord.expires_at))
        .where(VoiceCrisisRecord.call_id.in_(live), VoiceCrisisRecord.cleared_at.is_(None),
               VoiceCrisisRecord.expires_at > now).group_by(VoiceCrisisRecord.call_id))
    result = {}
    defaults = get_default_voice_call_script()['crisis']
    for call_id, expires_at in rows:
        script = live[call_id].config_snapshot.get('resolved_script', {}).get('crisis', {})
        def copy(key):
            value = script.get(key)
            return value if isinstance(value, str) and value.strip() else defaults[key]
        result[call_id] = dict(banner=copy('in_call_banner'),
            resource=copy('post_call_resource_card'), expires_at=expires_at.isoformat()+'Z')
    return result
