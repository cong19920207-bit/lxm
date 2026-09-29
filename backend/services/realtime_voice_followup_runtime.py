"""Compose follow-up dispatch with existing DB, Redis and DeepSeek adapters.

Approved policy bypasses ordinary daily/interval limits; successful sends still
increment the shared counter. All other eligibility checks remain in dispatch.
"""
from datetime import datetime
from math import ceil
from backend.utils.deepseek_client import DEEPSEEK_DEFAULT_TIMEOUT

# Technical recovery timing, not a product retry cap. Leave transaction time
# after the existing provider timeout; expired leases are recoverable.
FOLLOWUP_LEASE_SECONDS=ceil(DEEPSEEK_DEFAULT_TIMEOUT)+30
FOLLOWUP_RETRY_SECONDS=5


async def approved_followup_quota(**kwargs):
    """User approved no additional quota and bypass of the ordinary 8/30 gate."""
    return True


async def build_voice_followup_service(*,quota_available=approved_followup_quota,
        lease_seconds=FOLLOWUP_LEASE_SECONDS,retry_seconds=FOLLOWUP_RETRY_SECONDS,clock=datetime.utcnow):
    from backend.database import async_session_maker
    from backend.redis_client import get_redis
    from backend.services.realtime_voice_followup_job_service import VoiceFollowupJobService
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    from backend.services.realtime_voice_followup_topic_service import VoiceFollowupTopicCheck
    from backend.services.realtime_voice_metric_service import VoiceMetrics
    if not callable(quota_available):raise ValueError('followup_quota_policy_required')
    cache=await get_redis()
    return VoiceFollowupJobService(session_factory=async_session_maker,
        quota_available=quota_available,topic_continued=VoiceFollowupTopicCheck(),
        count_sent=VoiceFollowupCounter(cache=cache,clock=clock),
        lease_seconds=lease_seconds,retry_seconds=retry_seconds,clock=clock,metrics=VoiceMetrics(cache))
