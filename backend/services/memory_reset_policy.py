"""S15 fixed 38 existing + 23 planned table matrix; no substring deletion rules."""
import re
RELATIONSHIP_FIELDS=('relation_description','user_description','character_purpose','character_attitude','future_timestamp','future_action')
PRESERVE=('admin_config admin_users ai_diary feed_comment feed_like feed_post life_plan life_plan_outline login_log '
    'relationship_growth_log relationship_level_history user_api_keys user_timeline_seq users voice_capability_evidence '
    'voice_metric_daily voice_quota_account voice_usage_ledger world_state worldview_event worldview_snapshot '
    'memory_runtime_fence memory_reset_run memory_reset_item memory_use_item chat_resend_quota memory_config_head memory_config_publish').split()
DELETE=('agent_aware_queue agent_message emotion_log conversation_log memory user_short_term_emotion '
    'voice_call_create_idempotency voice_memory_trace chat_submission_message chat_message_state chat_generation_message').split()
NULLS={
 'relationship':RELATIONSHIP_FIELDS,
 'admin_operation_logs':('before_value','after_value'),
 'voice_call':('sort_seq','call_summary','user_emotion','assistant_emotion','unfinished_topics','summary_reasoning'),
 'voice_call_turn':('user_text_final','assistant_text_generated','assistant_text_effective'),
 'voice_memory_job':('extraction_snapshot','lease_owner','lease_expires_at'),
 'voice_postprocess_job':('lease_owner','lease_expires_at'),
 'voice_followup_job':('agent_message_id','lease_owner','lease_expires_at'),
 'voice_crisis_record':('matched_keyword','content_plaintext'),
 'memory_identity':('body_hash','encoder_version','current_operation_id','inflight_operation_id'),
 'memory_operation':('pending_payload','worker_id','lease_until'),
 'memory_index_task':('next_attempt_at','worker_id','lease_until'),
 'memory_use_claim':(),
 'chat_user_state':('current_generation_id',),
 'chat_generation':('lease_owner','lease_until'),
 'chat_submission':('fingerprint','fingerprint_version','accepted_generation_id'),
 'chat_lifecycle_effect':('next_attempt_at','lease_owner','lease_until'),
 'future_consumption':('agent_message_id',),
 'memory_diagnostic_run':('input_text','frozen_versions','context_sources','candidate_snapshots','selection_result','metrics'),
 'memory_backfill_run':('lease_owner','lease_until'),
 'memory_backfill_item':(),
 'memory_maintenance_event':('details','controlled_reason'),
}
EXTRA={
 'relationship':('future_slot_version',),
 'admin_operation_logs':('target_description',),
 'voice_call':('config_snapshot','capability_snapshot','deletion_fence_at','deleted_at','deleted_by','cleared_run_id'),
 'voice_call_turn':('effective_text_cleared_at','generated_text_cleared_at','content_clear_reason'),
 'voice_memory_job':('fail_reason',),'voice_postprocess_job':('fail_reason',),
 'voice_followup_job':('content','cancel_reason','fail_reason'), 'voice_crisis_record':('cleared_at',),
 'memory_identity':('target_epoch','source_state','index_state'), 'memory_operation':('receipt_summary',),
 'memory_index_task':('state',),'memory_use_claim':('state','closed_at',),
 'chat_user_state':('state_revision',),'chat_submission':('record_state',),
 'chat_lifecycle_effect':('state','last_reason'), 'future_consumption':('slot_action',),
 'memory_diagnostic_run':('snapshot_available','history_state','deleted_at','tombstone_until'),
 'memory_maintenance_event':('display_deleted_at',),
}
POLICIES={name:{'action':'preserve','changed':()} for name in PRESERVE}
POLICIES.update({name:{'action':'delete','changed':()} for name in DELETE})
POLICIES.update({name:{'action':'update','changed':tuple(cols)+EXTRA.get(name,())} for name,cols in NULLS.items()})
POLICIES['relationship_change_history']={'action':'selective_delete','changed':()}
AUDIT_MODULES={'user_memory','private_setting','character_knowledge'}
ORDER=['chat_submission_message','chat_message_state','chat_generation_message','future_consumption','voice_followup_job',
 'agent_aware_queue','agent_message','emotion_log','conversation_log','relationship_change_history','relationship']
ORDER+=sorted(set(POLICIES)-set(ORDER))
# Concrete strict shapes only. Statistical/authorization/configuration families
# are preserved by default even when they share an English prefix.
REDIS_DELETE=[r'chat:gen:\d+',r'chat:debounce_tok:\d+',r'chat:resend:\d+:[^:]+',r'chat:bundle:lock:\d+',
 r'emb:[0-9a-f]{32}',r'emb:v2:[0-9a-f]{64}:text-embedding-v4:1024:l2-v1:[0-9a-f]{64}',
 r'(?:user_emotion|ai_emotion):\d+',r'voice:session_context:[A-Za-z0-9_-]+',
 r'voice:lease:(?:active|users|user:\d+)',r'voice:cooldown:\d+',r'voice:quota:[A-Za-z0-9_-]+',
 r'voice:admin_playback:(?:test|ack):[A-Za-z0-9_-]+',r'voice:admin_playback:owner:\d+',
 r'active_config:(?:vector_db_config|third_party:dashvector|third_party:embedding)']

def redis_action(key):
    return 'delete' if any(re.fullmatch(pattern,key) for pattern in REDIS_DELETE) else 'preserve'


def selected(name,row):
    if name=='admin_operation_logs':return row['module'] in AUDIT_MODULES
    if name=='relationship_change_history':return row['field_name'] in RELATIONSHIP_FIELDS
    return True


def cleared_receipt(row):
    """Retain authorization/opaque history, never semantic source IDs or keys."""
    summary=row.get('receipt_summary') or {}
    result={'reason':'cleared','operation_id':row['operation_id']}
    if summary.get('memory_type') in {'user','character_private','character_global','character_knowledge'}:
        result['memory_type']=summary['memory_type']
    if type(summary.get('owner_user_id')) is int:result['owner_user_id']=summary['owner_user_id']
    for key in ('source_counts','index_counts'):
        if isinstance(summary.get(key),dict):
            result[key]={k:v for k,v in summary[key].items() if k in {'succeeded','failed','unknown','pending','ready','not_executed'} and type(v) is int and v>=0}
    if 'items' in summary:
        result['items']=[{k:item[k] for k in ('input_seq','child_operation_id') if k in item} for item in summary['items']]
    return result


def updates(name,row,run):
    values={c:None for c in NULLS.get(name,())}
    now=run.t0
    if name=='relationship' and 'future_slot_version' in row:values['future_slot_version']=row['future_slot_version']+1
    elif name=='admin_operation_logs':values['target_description']='S15 cleared'
    elif name=='voice_call':values.update(config_snapshot={},capability_snapshot={},deletion_fence_at=now,
        deleted_at=now,deleted_by=run.operator_id,cleared_run_id=run.run_id)
    elif name=='voice_call_turn':values.update(effective_text_cleared_at=now,generated_text_cleared_at=now,content_clear_reason='admin_deleted')
    elif name in {'voice_memory_job','voice_postprocess_job'}:values['fail_reason']='s15_cleared'
    elif name=='voice_followup_job':values.update(content='',cancel_reason='s15_cleared',fail_reason='s15_cleared')
    elif name=='voice_crisis_record':values['cleared_at']=now
    elif name=='memory_identity':values.update(target_epoch=run.target_epoch,source_state='deleted',index_state='deleted')
    elif name=='memory_operation':values['receipt_summary']=cleared_receipt(row)
    elif name=='memory_index_task' and row['state']!='completed':values['state']='superseded'
    elif name=='memory_use_claim':
        values['closed_at']=row['closed_at'] or now
        if row['state']=='reserved':values['state']='aborted'
    elif name=='chat_user_state':values['state_revision']=row['state_revision']+1
    elif name=='chat_submission':values['record_state']='tombstone'
    elif name=='chat_lifecycle_effect' and row.get('state')!='done':values.update(state='failed',last_reason='expired')
    elif name=='future_consumption':values['slot_action']=''
    elif name=='memory_diagnostic_run':values.update(snapshot_available=False,history_state='deleted',deleted_at=now)
    elif name=='memory_maintenance_event':values['display_deleted_at']=now
    return {key:value for key,value in values.items() if key in row}


def unsettled(name,row):
    """Never infer settlement from elapsed TTL, process death, or next epoch."""
    if name=='memory_operation':return row['dispatch_state'] not in {'confirmed','not_sent','superseded'} or row['source_result'] in {'pending','unknown'}
    if name=='memory_use_claim':return row['state'] in {'dispatching','unknown'} or (row['state']=='handed_off' and not row['closed_at'])
    if name=='memory_identity':return bool(row['inflight_operation_id'])
    if name=='memory_config_publish':return row.get('state',row.get('commit_state')) in {'accepted','validating','unknown'}
    if name=='voice_call':return row['status'] not in {'ended','missed','failed','cancelled'}
    if name in {'voice_memory_job','voice_postprocess_job','voice_followup_job'}:
        return row['status'] in {'pending','processing','running','retry_wait'} or row.get('next_retry_at') is not None
    if name=='memory_diagnostic_run':
        return (row.get('execution_state') not in {'completed','degraded','budget_blocked','failed','interrupted'}
                or row.get('history_state') not in {'saved','failed','deleted'} or bool(row.get('lease_owner')))
    if name in {'chat_generation','future_consumption'}:
        return row.get('phase') in {'commit_prepared','commit_unknown','reconcile_exhausted'} or row.get('state',row.get('execution_state')) not in {'success','completed','failed','cancelled','expired','committed','rejected','superseded'}
    if name=='chat_lifecycle_effect':return row.get('state') in {'running','unverified','unknown'} or (row.get('effect_kind') in {'normal_decay','handler_proactive','agent_count'} and row.get('state')!='done')
    if name=='memory_backfill_run':return row['execution_state'] in {'running','pending'} or row['unresolved_count']>0 or bool(row['lease_owner'])
    return False
