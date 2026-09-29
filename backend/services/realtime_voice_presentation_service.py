"""Public call status, using the call's immutable script version. No transcript."""
from backend.constants.realtime_voice_config import get_default_voice_call_script


def call_presentation(row):
    connected = row.connected_at is not None
    defaults = get_default_voice_call_script()
    script = row.config_snapshot.get('resolved_script', {})
    reason = row.end_reason
    copy = script.get('end_reason', {}).get(reason, defaults['end_reason'].get(reason))
    if isinstance(copy, dict):
        copy = copy.get('after_connected' if connected else 'before_connected')
    if row.status == 'missed':
        # The result page is distinct from the separately scheduled follow-up.
        copy = '她现在可能不方便'
    if not isinstance(copy, str) or not copy.strip():
        copy = '通话已结束' if connected else '暂时无法接通'
    return {'call_id': row.call_id, 'status': row.status, 'end_reason': reason,
            'has_connected': connected, 'duration_seconds': row.duration_seconds if connected else 0,
            'end_message': copy, 'show_end_page': row.status != 'cancelled' and reason != 'user_cancel'}
