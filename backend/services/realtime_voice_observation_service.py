"""UTC telemetry projection; capability-dependent values require sample evidence.

Legacy pooled counters remain unavailable. Unique reply observations carry the
adapter's capability decision at observation time; no current switch is used to
reinterpret old buckets. Retained observations never claim full-day completeness.
"""
from backend.services.realtime_voice_metric_read_service import read_counter_day, read_duration_day

CAPABILITY_METRICS = {
    'voice.barge_in.truncate': ('truncate_success_rate', 'ConversationTruncated'),
    'voice.effective_text.evidence': ('effective_text_evidence_distribution', 'playback_mapping_or_sentence_ack'),
    'voice.recall.double_reply': ('double_reply_count', 'ChatResponse_ChatEnded'),
    'voice.provider.usage': ('provider_usage_business_cost_ratio', 'UsageResponse'),
}
REASON = 'capability_evidence_unavailable_for_bucket'


async def read_observations(cache, day):
    counters = await read_counter_day(cache, day)
    durations = await read_duration_day(cache, day)
    text_event = next((event for event in counters['events'] if event['name']=='voice.effective_text.observed'), None)
    text_distribution = None
    text_sample_count = 0
    if text_event and text_event['status']=='available':
        samples = [sample for sample in text_event['samples'] if sample['value'] > 0]
        if samples and all(sample['dimensions']['evidence']=='verified' for sample in samples):
            counts = dict.fromkeys(('exact_played','confirmed_sentences','full','none'), 0)
            for sample in samples:
                counts[sample['dimensions']['level']] += sample['value']
            text_sample_count = sum(counts.values())
            text_distribution = {level:count/text_sample_count for level,count in counts.items()}
        else:
            text_event.update(status='not_measurable',samples=None,reason=REASON)
    truncate_event = next((event for event in counters['events'] if event['name']=='voice.barge_in.truncate_outcome'), None)
    truncate_rate = None
    if truncate_event and truncate_event['status']=='available':
        samples = [sample for sample in truncate_event['samples'] if sample['value'] > 0]
        if samples and all(sample['dimensions']['evidence']=='verified' and
                           sample['dimensions']['result'] in ('success','failure') for sample in samples):
            total = sum(sample['value'] for sample in samples)
            truncate_rate = sum(sample['value'] for sample in samples if sample['dimensions']['result']=='success') / total
        else:
            truncate_event.update(status='not_measurable',samples=None,reason=REASON)
    reply_event = next((event for event in counters['events'] if event['name']=='voice.recall.reply_observed'), None)
    reply_count = None
    if reply_event and reply_event['status']=='available':
        samples = [sample for sample in reply_event['samples'] if sample['value'] > 0]
        if samples and all(sample['dimensions']['evidence']=='verified' and
                           sample['dimensions']['kind']!='overflow' for sample in samples):
            reply_count = sum(sample['value'] for sample in samples if sample['dimensions']['kind']=='extra')
        else:
            reply_event.update(status='not_measurable',samples=None,reason=REASON)
    for event in counters['events']:
        if event['name'] in CAPABILITY_METRICS:
            event.update(status='not_measurable', samples=None, reason=REASON)
    metrics = [dict(name=name, required_evidence=evidence,
                status='not_measurable', value=None, reason=REASON)
                for name, evidence in CAPABILITY_METRICS.values()]
    if reply_count is not None:
        item = next(item for item in metrics if item['name']=='double_reply_count')
        item.update(status='measured',value=reply_count,reason=None,unit='extra_reply',
                    source='voice.recall.reply_observed')
    if truncate_rate is not None:
        item = next(item for item in metrics if item['name']=='truncate_success_rate')
        item.update(status='measured',value=truncate_rate,reason=None,
                    source='voice.barge_in.truncate_outcome',unit='terminal_request')
    if text_distribution is not None:
        item = next(item for item in metrics if item['name']=='effective_text_evidence_distribution')
        item.update(status='measured',value=text_distribution,reason=None,
                    source='voice.effective_text.observed',unit='text_snapshot',sample_count=text_sample_count)
    return {**counters, 'durations': durations['events'], 'capability_metrics': metrics}
