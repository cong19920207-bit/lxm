"""Pre-T0 readback and original live-runtime drain; never operator 'confirmed'."""
from contextlib import asynccontextmanager
from sqlalchemy import select
from backend.models.memory_control import MemoryOperation,MemoryIdentity,MemoryIndexTask
from backend.models.memory_backfill import MemoryResetItem
from backend.services.memory_reset_service import digest
from backend.services.memory_runtime_service import MemoryControlError

class MemoryResetDrainer:
    def __init__(self,reset):self.reset=reset

    async def terminate_unsent(self,run_id):
        """Pre-T0 only: durable never-dispatched states, under original fence.

        Leases/TTL do not prove anything. Claimed source intents are safe only
        before dispatched_at; the source sender rechecks this fence/state before
        dispatch. Voice jobs are narrower: never claimed, no attempt or result.
        """
        from datetime import timedelta
        from backend.models.memory_control import MemoryUseClaim
        from backend.models.realtime_voice import VoiceCall,VoiceCallTurn,VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob
        async with self.reset.sessions() as db:
            run,fence=await self.reset._run(db,run_id)
            if run.t0:return
            if fence.mode!='maintenance':raise MemoryControlError(20126,'drain_closed')
            operations=(await db.scalars(select(MemoryOperation).with_for_update())).all()
            claims=(await db.scalars(select(MemoryUseClaim).with_for_update())).all()
            # Do not attribute safety to an unrelated job while an external
            # model/source outcome is still unresolved in this environment.
            if any(o.operation_kind!='batch' and (o.dispatch_state in {'dispatching','unknown'} or o.source_result=='unknown') for o in operations):return
            if any(c.state in {'dispatching','unknown'} or c.state=='handed_off' and not c.closed_at for c in claims):return
            now=self.reset.clock()
            def evidence(key,before,proof):
                db.add(MemoryResetItem(run_id=run_id,kind='phase',resource_key='drain:'+key,state='confirmed',
                    fixed_scope={'before_digest':digest(before).hex(),'proof':proof,'epoch':fence.target_epoch}))
            def rowdict(row):return {c.name:getattr(row,c.name) for c in row.__table__.c}
            for op in operations:
                is_index=op.operation_kind=='index'
                if (op.operation_kind=='batch' or op.dispatch_state not in ({'prepared'} if is_index else {'prepared','claimed'})
                        or op.dispatched_at is not None or op.source_result!=('confirmed' if is_index else 'pending')):continue
                identity=await db.get(MemoryIdentity,op.identity_id)
                if (not identity or identity.target_fingerprint!=self.reset.target or op.target_epoch!=fence.target_epoch
                        or identity.inflight_operation_id!=op.operation_id):continue
                task=await db.get(MemoryIndexTask,op.task_id) if op.task_id else None
                if is_index:
                    # A derived index already carries confirmed SOURCE truth.
                    # Cancel only its original unsent task, never downgrade that
                    # source or claim an index was successfully written.
                    if (not task or task.identity_id!=identity.id or task.generation!=op.generation
                            or task.generation!=identity.generation or task.body_hash!=identity.body_hash
                            or task.round_no!=op.round_no or task.attempt!=op.attempt
                            or task.state not in {'running','retry_wait'} or identity.current_operation_id!=task.operation_id):continue
                    # A source read deferral releases the task into retry_wait
                    # while retaining this same prepared intent. Safety comes
                    # from no dispatch permission, never from an expired lease.
                    identity.index_state='not_ready'
                    anchor=await db.get(MemoryOperation,task.operation_id)
                    if anchor and anchor.source_result=='confirmed' and anchor.index_result!='ready':
                        anchor.index_result='superseded';anchor.revision+=1
                evidence('operation:'+op.operation_id,rowdict(op),'durable_index_never_dispatched' if is_index else 'durable_intent_never_dispatched')
                if not is_index:op.source_result='failed'
                op.dispatch_state='not_sent';op.index_result='superseded' if is_index else 'not_required'
                op.receipt_summary={**(op.receipt_summary or {}),'reason':'s15_unsent_cancelled'}
                op.pending_payload=None;op.worker_id=None;op.lease_until=None;op.terminal_at=now
                op.receipt_until=now+timedelta(days=7);op.tombstone_until=now+timedelta(days=30);op.revision+=1
                identity.inflight_operation_id=None;identity.revision+=1
                if task:
                    task.state='superseded';task.worker_id=None;task.lease_until=None;task.next_attempt_at=None
                    task.error_code='s15_unsent_cancelled';task.revision+=1
            # Parent batch states are cached projections, not remote attempts.
            # Recompute only from original owned delete children; a stale parent
            # unknown must not prevent already verified children from settling.
            from backend.services.memory_mutation_service import MemoryMutationService
            from backend.services.admin_memory_write_service import project
            receipts=MemoryMutationService(self.reset.sessions,None,self.reset.environment_id,'s15-receipt-only',clock=self.reset.clock)
            by_id={o.operation_id:o for o in operations}
            for op in operations:
                if (op.operation_kind!='batch' or op.source_result not in {'pending','unknown'}
                        or op.dispatch_state not in {'prepared','unknown'} or op.target_epoch!=fence.target_epoch):continue
                counts={'succeeded':0,'failed':0,'unknown':0,'pending':0};indexes={'ready':0,'pending':0,'failed':0,'unknown':0,'not_executed':0}
                for item in (op.receipt_summary or {}).get('items',[]):
                    child=by_id.get(item.get('child_operation_id'))
                    if (child and child.parent_operation_id==op.operation_id and child.operation_kind=='delete'
                            and child.owner_actor_type==op.owner_actor_type and child.owner_actor_id==op.owner_actor_id
                            and child.target_epoch==op.target_epoch):
                        result=project(receipts._receipt(child),'delete')
                        state,index=result['source_state'],result['index_state']
                    elif not item.get('child_operation_id') and item.get('source_state')=='failed':
                        state,index='failed',item.get('index_state','not_executed')
                    else:state,index='unknown','unknown'
                    counts[state]+=1;indexes[index]+=1
                if counts['unknown'] or counts['pending']:continue
                evidence('operation:'+op.operation_id,rowdict(op),'all_children_terminal_after_unsent_drain')
                op.source_result='confirmed' if counts['succeeded'] else 'failed';op.dispatch_state='confirmed'
                op.index_result=('pending' if indexes['pending'] else 'unknown' if indexes['unknown'] else 'failed' if indexes['failed'] else 'ready')
                op.receipt_summary={**op.receipt_summary,'source_counts':counts,'index_counts':indexes}
                op.terminal_at=now;op.receipt_until=now+timedelta(days=7);op.tombstone_until=now+timedelta(days=30);op.revision+=1
            for claim in claims:
                if claim.state=='reserved' and claim.target_epoch==fence.target_epoch:
                    evidence('claim:'+claim.claim_id,rowdict(claim),'reserved_never_dispatched')
                    claim.state='aborted';claim.closed_at=now;claim.error_code='s15_unsent_cancelled';claim.revision+=1
            for model in (VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob):
                for job in (await db.scalars(select(model).with_for_update())).all():
                    if (job.status!='pending' or job.attempt_count!=0 or job.lease_owner or job.lease_expires_at
                            or job.next_retry_at or getattr(job,'extraction_snapshot',None) or getattr(job,'agent_message_id',None)):continue
                    call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==job.call_id).with_for_update())
                    if not call or call.status not in {'ended','missed','failed','cancelled'} or call.cleared_run_id:continue
                    evidence(model.__tablename__+':'+str(job.id),rowdict(job),'never_claimed_zero_attempt_no_result')
                    job.status='cancelled';job.fail_reason='s15_unsent_cancelled'
                    if isinstance(job,VoiceMemoryJob):
                        turn=await db.get(VoiceCallTurn,job.turn_id)
                        if turn and turn.memory_status=='pending':turn.memory_status='cancelled'
                    elif isinstance(job,VoicePostprocessJob) and call.summary_status=='pending':call.summary_status='not_applicable'
                    elif isinstance(job,VoiceFollowupJob):job.cancel_reason='s15_unsent_cancelled'
            await db.commit()

    async def reconcile_operation(self,manifest,auth,*,operation_id,remote):
        """Fetch only, using the same exact original payload evidence as Q06.

        'remote' is the configured original vector transport, not a user DTO.
        Absence/wrong tag/timeout retain the fence. No dispatch is possible here.
        """
        import asyncio
        from backend.services.memory_mutation_service import MemoryMutationService
        from backend.utils.memory_vector_client import _matches_prepared
        self.reset._authorize(manifest,auth)
        await self.reset._start(manifest,auth)
        async with self.reset.sessions() as db:
            run,fence=await self.reset._run(db,auth['run_id'])
            if run.t0 or fence.mode!='maintenance':raise MemoryControlError(20126,'drain_closed')
            op=await db.get(MemoryOperation,operation_id)
            identity=await db.get(MemoryIdentity,op.identity_id) if op else None
            if not identity or identity.target_fingerprint!=self.reset.target or op.target_epoch!=fence.target_epoch:
                raise MemoryControlError(20127,'drain_operation_changed')
            if op.dispatch_state=='confirmed':return {'state':'confirmed','replayed':True}
            if op.dispatch_state not in {'dispatching','unknown'} or identity.inflight_operation_id!=operation_id:
                raise MemoryControlError(20126,'drain_not_dispatched')
            before=digest({c.name:getattr(op,c.name) for c in op.__table__.c})
            try:fetched=await asyncio.wait_for(remote.fetch(identity.partition_name,identity.doc_id),3)
            except Exception:raise MemoryControlError(20126,'drain_remote_unknown') from None
            if op.operation_kind=='index':
                from backend.services.memory_mutation_service import _hash
                matches=(op.pending_payload and _hash(op.pending_payload)==op.payload_hash and fetched.status=='found'
                    and _matches_prepared(op.pending_payload,fetched.document)
                    and op.pending_payload['fields']['mr_operation_id']==op.remote_tag
                    and op.pending_payload['fields']['mr_epoch']==op.target_epoch
                    and op.pending_payload['fields']['mr_generation']==op.generation)
            else:matches=MemoryMutationService._matches(None,op,identity,fetched)
            if not matches:raise MemoryControlError(20126,'drain_remote_unknown')
            # The fence lock excludes T0 and all joined writers for this readback.
            op.source_result='confirmed';op.dispatch_state='confirmed';op.terminal_at=self.reset.clock()
            op.lease_until=None;op.worker_id=None;op.revision+=1
            identity.inflight_operation_id=None;identity.revision+=1
            if op.task_id:
                task=await db.get(MemoryIndexTask,op.task_id)
                if task:task.state='superseded';task.lease_until=None;task.worker_id=None;task.next_attempt_at=None
            db.add(MemoryResetItem(run_id=run.run_id,kind='phase',resource_key='drain:operation:'+operation_id,state='confirmed',
                fixed_scope={'before_digest':before.hex(),'remote_tag':op.remote_tag,'epoch':op.target_epoch,
                    'generation':op.generation,'payload_hash':op.payload_hash.hex(),'proof':'exact_original_remote_readback'}))
            await db.commit()
        return {'state':'confirmed','replayed':False}

    async def stop_live_voice(self,manifest,auth,*,call_id,cache):
        """Only an extant original runtime may stop/join/flush and settle.

        A restored Redis meter alone cannot prove final input closure. After a
        process restart the caller must leave unknown for external resolution.
        """
        from backend.services.realtime_voice_local_runtime import local_voice_calls
        from backend.services.realtime_voice_ops_service import VoiceOpsService
        self.reset._authorize(manifest,auth)
        if local_voice_calls.get(call_id) is None:raise MemoryControlError(20126,'original_voice_runtime_unavailable')
        await self.reset._start(manifest,auth)
        @asynccontextmanager
        async def scoped_sessions():
            async with self.reset.sessions() as db:
                run,fence=await self.reset._run(db,auth['run_id'])
                if run.t0 or fence.mode!='maintenance':raise MemoryControlError(20126,'drain_closed')
                db.info['s15_drain_call']=call_id
                yield db
        scoped_sessions.s15_drain_scope=True
        # Original finalizer owns stop(), settlement, buffered-turn final_flush,
        # terminal state, relationship growth, card, metrics and lease cleanup.
        return await VoiceOpsService(cache=cache,session_factory=scoped_sessions).end_call(call_id=call_id)
