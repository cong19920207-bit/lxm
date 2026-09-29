"""Stage the occurrence card once; summary generation belongs to STEP-031."""
import re
from datetime import datetime
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCallTurn
from backend.services.timeline_seq_service import allocate_sort_seq

CALL_FIELDS = ('call_id','call_status','duration_seconds','summary_status','call_summary')


def meaningful_user_text(value):
    compact = re.sub(r'[\s，。！？、,.!?～~…]+','',value or '')
    return bool(compact and not re.fullmatch(r'(?:嗯|啊|哦|噢|对|是的?|好的?|哈|呵|诶|唉|呃)+',compact))


async def summary_eligible(db, call):
    if call.connected_at is None or call.duration_seconds < 15:
        return False
    rows = await db.scalars(select(VoiceCallTurn.user_text_final).where(
        VoiceCallTurn.call_id == call.call_id,
        VoiceCallTurn.turn_status.in_(['finalized','interrupted']),
        VoiceCallTurn.effective_text_evidence != 'none',
        VoiceCallTurn.assistant_text_effective.is_not(None),
        VoiceCallTurn.assistant_text_effective != '',
        VoiceCallTurn.user_content_safety_status == 'passed',
        VoiceCallTurn.assistant_content_safety_status == 'passed',
        VoiceCallTurn.user_crisis_status == 'passed', VoiceCallTurn.assistant_crisis_status == 'passed'))
    for value in rows:
        if meaningful_user_text(value):
            return True
    return False


async def stage_call_card(db, call):
    """Caller holds user/call locks and owns the terminal transaction."""
    if call.sort_seq is not None or call.deletion_fence_at is not None:
        return False
    if call.status not in {'ended','missed'}:
        return False
    call.summary_status = 'pending' if await summary_eligible(db,call) else 'not_applicable'
    call.sort_seq = (await allocate_sort_seq(call.user_id,1,db))[0]
    from backend.services.realtime_voice_metric_service import stage_voice_metrics
    stage_voice_metrics(db,[('voice.timeline.insert',{'status':call.status},1)])
    return True


def timeline_call_item(call):
    readable = call.transcript_expires_at is None or call.transcript_expires_at > datetime.utcnow()
    display_at = call.created_at if call.status == 'missed' else call.ended_at
    return dict(source='call',sort_seq=call.sort_seq,id=call.id,content=None,
        created_at=display_at.isoformat() if display_at else None,
        emotion_label=None,is_read=None,trigger_type=None,delivery_status=None,skipped_in_prompt=None,
        call_id=call.call_id,call_status=call.status,duration_seconds=call.duration_seconds,
        summary_status=call.summary_status,
        call_summary=call.call_summary if call.summary_status=='ready' and readable else None)
