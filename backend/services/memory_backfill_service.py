"""Explicit complete-catalog reconciliation. No web/startup entry or old-store migration.

Actual runs require a completed S15 empty-target baseline and its durable full
partition inventory. External writers must already be sealed by that run.
Unverifiable external full manifests are refused; isolated fixtures are synthetic.
"""
import asyncio
from collections import Counter
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy import func, select
from backend.models.memory_backfill import MemoryBackfillRun, MemoryBackfillItem
from backend.models.memory_control import MemoryIdentity, MemoryOperation, MemoryIndexTask
from backend.services.memory_index_worker import MemoryIndexWorker
from backend.services.memory_hybrid_retrieval import CandidateValidator
from backend.services.memory_mutation_service import _hash, body_hash
from backend.services.memory_runtime_service import MemoryControlError
from backend.utils.memory_vector import normalize_dense

ROUTES={'user':'user','character_private':'cp','character_global':'cg','character_knowledge':'ck'}


class BackfillIndexWorker(MemoryIndexWorker):
    def __init__(self,*args,embed,**kwargs):
        super().__init__(*args,**kwargs)
        self.embed=embed
        self.anchors={}
        self.inflight={}

    async def _source_context(self,ticket):
        result=await super()._source_context(ticket)
        if result:
            async with self.sessions() as db:
                anchor=await db.get(MemoryOperation,result[0].current_operation_id)
                self.anchors[ticket.identity_id]=anchor
                inflight=await db.get(MemoryOperation,result[0].inflight_operation_id) if result[0].inflight_operation_id else None
                self.inflight[ticket.identity_id]=inflight
        return result

    def _source_valid(self,identity,task,tags,fetched):
        if not fetched or fetched.status!='found': return False
        doc={**fetched.document,'score':1.0}
        anchor=self.anchors.get(identity.id)
        ops={anchor.operation_id:anchor} if anchor else {}
        inflight=self.inflight.get(identity.id)
        if inflight:ops[inflight.operation_id]=inflight
        reason,_,_=CandidateValidator._check(doc,identity,ROUTES[identity.memory_type],identity.owner_user_id,
            SimpleNamespace(target_epoch=self.target_epoch,encoder_version=self.encoder_version),'dense',ops)
        # Versioned sources additionally prove the exact committed remote tag.
        return reason is None and (doc['fields'].get('mr_operation_id') in tags or
            (anchor and anchor.operation_kind=='baseline' and 'mr_operation_id' not in doc['fields']))

    async def _document_vector(self,document,value):
        return normalize_dense(await self.embed(value))

    @staticmethod
    def _prepared_source_matches(prepared,document):
        try:
            before,current=dict(prepared['fields']),dict(document['fields'])
            for key in tuple(before):
                if key.startswith('mr_'): before.pop(key,None)
            for key in tuple(current):
                if key.startswith('mr_'): current.pop(key,None)
            return prepared['id']==document['id'] and before==current
        except Exception: return False


class MemoryBackfillService:
    LEASE_SECONDS=15
    MAX_ITEMS=100
    MAX_PASSES=3
    def __init__(self,sessions,remote,encoder,embed,environment_id,target_epoch,target_fingerprint,
                 *,provider_version,allow_isolated=False,clock=None,worker_id=None):
        self.sessions,self.remote=sessions,remote
        self.clock=clock or datetime.utcnow
        self.worker_id=worker_id or str(uuid4())
        self.worker=BackfillIndexWorker(sessions,remote,encoder,environment_id,target_epoch,target_fingerprint,
            embed=embed,clock=self.clock,allow_isolated=allow_isolated)
        self.versions={'encoder_version':encoder.encoder_version,'provider_version':provider_version,
            'dimension':1024,'normalization':'l2-v1','target_epoch':target_epoch}
        if not isinstance(provider_version,str) or not provider_version: raise ValueError('provider_version_required')

    def _query(self,scope):
        return select(MemoryIdentity).where(MemoryIdentity.target_fingerprint==self.worker.target_fingerprint,
            MemoryIdentity.target_epoch==self.worker.target_epoch,MemoryIdentity.partition_name.in_(scope['partitions']))

    async def create(self,*,partitions,baseline,mode='isolated',run_id=None,total_known=True):
        if (mode not in {'isolated','actual'} or not partitions or len(set(partitions))!=len(partitions)
                or any(not isinstance(p,str) or not p or len(p)>64 for p in partitions)):
            raise ValueError('invalid_scope')
        if (not isinstance(baseline,dict) or set(baseline) not in ({'kind','proof_digest'},{'kind','proof_digest','reset_run_id','manifest_hash'}) or baseline['kind'] not in {'empty_catalog','full_manifest'}
                or not isinstance(baseline['proof_digest'],str) or len(baseline['proof_digest'])!=64):
            raise ValueError('trusted_baseline_required')
        bytes.fromhex(baseline['proof_digest'])
        scope={'environment_id':self.worker.environment_id,'target_fingerprint':self.worker.target_fingerprint.hex(),
            'partitions':sorted(partitions),'target_epoch':self.worker.target_epoch}
        async with self.sessions() as db:
            await self.worker._fence(db)
            if mode=='actual':await self._verify_baseline(db,scope,baseline)
            elif not self.worker.allow_isolated or not self.worker.environment_id.startswith('isolated:'):raise ValueError('synthetic_baseline_requires_isolated_environment')
            rows=list((await db.scalars(self._query(scope).order_by(MemoryIdentity.id))).all())
            run=MemoryBackfillRun(run_id=run_id or str(uuid4()),mode=mode,execution_state='pending',stage='scan',
                source_scope=scope,frozen_versions=self.versions,scope_digest=_hash({'scope':scope,'baseline':baseline}),
                baseline=baseline,high_water={'identity_id':max((r.id for r in rows),default=0)},
                checkpoint_summary={'after_id':0,'pass':0},total_known=total_known,
                total_source_ids=len(rows) if total_known else None,source_class_counts={},reconcile_counts={})
            db.add(run); await db.commit()
        return await self.read(run.run_id)

    async def _verify_baseline(self,db,scope,baseline):
        from backend.models.memory_backfill import MemoryResetRun,MemoryResetItem
        from backend.models.memory_control import MemoryRuntimeFence
        from backend.services.memory_reset_service import digest
        def fail():raise MemoryControlError(20126,'backfill_baseline_unverified')
        if baseline.get('kind')!='empty_catalog' or set(baseline)!={'kind','proof_digest','reset_run_id','manifest_hash'}:fail()
        fence=await db.get(MemoryRuntimeFence,self.worker.environment_id)
        run=await db.get(MemoryResetRun,baseline['reset_run_id'])
        if (not run or not fence or fence.reset_run_id!=run.run_id or run.environment_id!=scope['environment_id']
                or run.target_fingerprint!=self.worker.target_fingerprint or run.target_epoch!=self.worker.target_epoch
                or run.state!='opened' or not run.t0 or not run.completed_at or not run.opened_at
                or not run.baseline_digest or baseline['proof_digest']!=run.baseline_digest.hex()
                or baseline['manifest_hash']!=run.manifest_hash.hex()):fail()
        proof=await db.get(MemoryResetItem,(run.run_id,'phase','catalog-baseline'))
        if not proof or proof.state!='confirmed':fail()
        manifest=proof.fixed_scope.get('manifest',{})
        if (digest({k:v for k,v in manifest.items() if k!='manifest_hash'})!=run.manifest_hash
                or manifest.get('manifest_hash')!=run.manifest_hash.hex()
                or manifest.get('environment_id')!=scope['environment_id']
                or manifest.get('target_fingerprint')!=scope['target_fingerprint']):fail()
        resources=[r for r in manifest.get('resources',[]) if r['key'].startswith('vector-new:') or r['key']=='vector-new']
        if not resources or sorted(r['target']['partition'] for r in resources)!=scope['partitions']:fail()
        # Bind resource descriptors to the actual provider client, not an input
        # digest claiming to represent an arbitrary collection or endpoint.
        provider=getattr(self.remote,'config',None)
        if provider is None:fail()
        from backend.services.memory_effective_config import TARGET_COLLECTION
        endpoint=provider.endpoint.rstrip('/')
        import hashlib
        cluster=hashlib.sha256(endpoint.encode()).hexdigest()
        for resource in resources:
            if resource['target']['collection']!=TARGET_COLLECTION or resource['target']['cluster_fingerprint']!=cluster:fail()
            item=await db.get(MemoryResetItem,(run.run_id,'resource',resource['key']))
            if (not item or item.state!='confirmed' or item.after_count!=0
                    or item.fixed_scope.get('target')!=resource['target']
                    or item.result_digest!=digest({'state':'confirmed','count':0,'acknowledged':True})):fail()
        # Original identities cannot disappear or change their immutable scope.
        # All later joined writers retain identities and FK-bound operations.
        for identity_id,key in proof.fixed_scope.get('catalog_keys',[]):
            identity=await db.get(MemoryIdentity,identity_id)
            if not identity or digest([identity.target_fingerprint,identity.partition_name,identity.doc_id,
                    identity.memory_type,identity.owner_user_id]).hex()!=key:fail()
        seals=await db.get(MemoryResetItem,(run.run_id,'phase','seals'))
        if not seals or seals.state!='confirmed' or seals.fixed_scope.get('manifest_hash')!=run.manifest_hash.hex():fail()

    async def _lock(self,db,run_id,lease=None):
        await self.worker._fence(db)
        run=await db.scalar(select(MemoryBackfillRun).where(MemoryBackfillRun.run_id==run_id).with_for_update())
        if run is None: raise MemoryControlError(20126,'backfill_not_found')
        if (run.frozen_versions!=self.versions or run.source_scope['target_fingerprint']!=self.worker.target_fingerprint.hex()
                or run.source_scope['environment_id']!=self.worker.environment_id or run.source_scope['target_epoch']!=self.worker.target_epoch
                or run.scope_digest!=_hash({'scope':run.source_scope,'baseline':run.baseline})):
            raise MemoryControlError(20127,'backfill_scope_changed')
        if run.mode=='actual':await self._verify_baseline(db,run.source_scope,run.baseline)
        if lease is not None and (run.lease_owner!=self.worker_id or run.lease_version!=lease
                or run.lease_until is None or run.lease_until<=self.clock()):
            raise MemoryControlError(20127,'backfill_lease_lost')
        return run

    async def _acquire(self,run_id):
        async with self.sessions() as db:
            run=await self._lock(db,run_id)
            if run.report_complete:return None
            if run.lease_owner and run.lease_until and run.lease_until>self.clock():
                raise MemoryControlError(20126,'backfill_busy')
            run.lease_owner=self.worker_id; run.lease_version+=1;run.lease_until=self.clock()+timedelta(seconds=self.LEASE_SECONDS)
            run.execution_state='running';run.started_at=run.started_at or self.clock();run.revision+=1
            await db.commit();return run.lease_version

    async def _renew(self,run_id,lease):
        while True:
            await asyncio.sleep(5)
            async with self.sessions() as db:
                run=await self._lock(db,run_id,lease)
                run.lease_until=self.clock()+timedelta(seconds=self.LEASE_SECONDS);await db.commit()

    async def _observe(self,run_id,lease,identity):
        classification,state,reason,task_id='identity_or_parse_error','unknown',None,None
        digest=None; attempted=0
        if identity.inflight_operation_id:
            async with self.sessions() as db:
                op=await db.get(MemoryOperation,identity.inflight_operation_id)
            if (op and op.operation_kind=='index' and op.task_id and op.generation==identity.generation
                    and op.target_epoch==self.worker.target_epoch and op.source_result=='confirmed'):
                task_id=op.task_id
                await self.worker.process(task_id)  # The original finite readback intent, no new write.
                async with self.sessions() as db:
                    identity=await db.get(MemoryIdentity,identity.id)
        if identity.source_state=='deleted':
            classification,state='empty','matched'
        elif identity.source_state!='live' or identity.inflight_operation_id:
            reason='source_unverified'
        else:
            try: fetched=await asyncio.wait_for(self.remote.fetch(identity.partition_name,identity.doc_id),3)
            except Exception: fetched=None
            if fetched is None or fetched.status not in {'found','not_found'}:reason='source_read_unverified'
            elif fetched.status=='not_found':state,reason='missing','source_missing'
            elif not isinstance(fetched.document,dict) or not isinstance(fetched.document.get('fields'),dict):
                state,reason='mismatch','source_document_malformed'
            else:
                fields=fetched.document['fields']
                if not isinstance(fields.get('content'),str) or not fields['content'].strip(): classification,reason='empty','empty_content'
                else:
                    async with self.sessions() as db:
                        anchor=await db.get(MemoryOperation,identity.current_operation_id)
                    self.worker.anchors[identity.id]=anchor
                    tags={anchor.remote_tag} if anchor else set()
                    # Include confirmed index tags for a previously indexed source.
                    async with self.sessions() as db:
                        tags.update((await db.scalars(select(MemoryOperation.remote_tag).where(
                            MemoryOperation.identity_id==identity.id,MemoryOperation.generation==identity.generation,
                            MemoryOperation.target_epoch==identity.target_epoch,MemoryOperation.dispatch_state=='confirmed'))).all())
                    if not self.worker._source_valid(identity,None,tags,fetched):state,reason='mismatch','source_identity_mismatch'
                    else:
                        classification='legacy_free_text' if identity.doc_id.startswith('mem_') else 'standard_kv'
                        digest=body_hash(fetched.document)
                        async with self.sessions() as db:
                            await self._lock(db,run_id,lease)
                            current=await db.scalar(select(MemoryIdentity).where(MemoryIdentity.id==identity.id).with_for_update())
                            if (current.generation!=identity.generation or current.body_hash!=digest or current.source_state!='live'
                                    or current.inflight_operation_id or current.target_epoch!=self.worker.target_epoch):
                                state,reason='retry_wait','source_changed'
                            else:
                                task=await db.scalar(select(MemoryIndexTask).where(MemoryIndexTask.identity_id==identity.id,
                                    MemoryIndexTask.generation==identity.generation,MemoryIndexTask.encoder_version==self.worker.encoder_version).with_for_update())
                                if task is None:
                                    now=self.clock();task=MemoryIndexTask(task_id=str(uuid4()),identity_id=identity.id,
                                        operation_id=identity.current_operation_id,generation=identity.generation,encoder_version=self.worker.encoder_version,
                                        body_hash=digest,state='pending',round_no=0,attempt=0,round_started_at=now,
                                        round_deadline_at=now+timedelta(seconds=120),next_attempt_at=now,worker_epoch=0)
                                    db.add(task)
                                    current.encoder_version=self.worker.encoder_version;current.index_state='not_ready';current.revision+=1
                                task_id=task.task_id
                                await db.commit()
                        if task_id and task.state=='completed':
                            try:
                                import math
                                from backend.utils.memory_vector import validate_sparse
                                dense=fetched.document['vector'];unit=normalize_dense(dense)
                                if any(not math.isclose(a,b,rel_tol=0,abs_tol=1e-6) for a,b in zip(dense,unit)):
                                    raise ValueError('dense_not_unit')
                                value=fields['content'] if identity.doc_id.startswith('mem_') else __import__('backend.utils.character_knowledge_validate',fromlist=['parse_value_from_content']).parse_value_from_content(fields['content'])
                                expected=self.worker.encoder.encode_document(value)
                                import inspect
                                if inspect.isawaitable(expected):expected=await asyncio.wait_for(expected,3)
                                if validate_sparse(fetched.document.get('sparse_vector',{}))!=validate_sparse(expected):raise ValueError('sparse_mismatch')
                            except Exception:
                                task_id=None;state,reason='mismatch','completed_vector_invalid'
                        if task_id:
                            before=task.attempt
                            result=await self.worker.process(task_id)
                            attempted=max(0,result.get('attempt',0)-before)
                            state='matched' if result['state']=='completed' else ('retry_wait' if result['state'] in {'pending','running','retry_wait'} else 'unknown')
                            reason=result.get('reason')
        async with self.sessions() as db:
            run=await self._lock(db,run_id,lease)
            key={'target_fingerprint':self.worker.target_fingerprint.hex(),'partition':identity.partition_name,'doc_id':identity.doc_id}
            key_hash=_hash(key)
            item=await db.scalar(select(MemoryBackfillItem).where(MemoryBackfillItem.run_id==run_id,MemoryBackfillItem.identity_digest==key_hash))
            if item and item.identity_key!=key:raise MemoryControlError(20127,'identity_digest_collision')
            if item is None:
                run.unique_source_ids+=1
                item=MemoryBackfillItem(run_id=run_id,item_seq=run.unique_source_ids,identity_id=identity.id,
                    identity_key=key,identity_digest=key_hash,attempt_count=0,revision=1)
                db.add(item)
            item.source_class=classification;item.current_generation=identity.generation;item.content_digest=digest
            item.index_result='ready' if state=='matched' and classification!='empty' else ('not_required' if classification=='empty' and state=='matched' else 'unknown')
            item.reconcile_state=state;item.task_id=task_id or item.task_id;item.reason=reason;item.observed_at=self.clock()
            item.attempt_count+=attempted;item.revision+=1;run.scanned_records+=1;run.attempt_count+=attempted
            run.checkpoint_summary={**(run.checkpoint_summary or {}),'after_id':identity.id}
            run.lease_until=self.clock()+timedelta(seconds=self.LEASE_SECONDS);run.revision+=1
            await db.commit()

    async def _reconcile(self,run_id,lease):
        async with self.sessions() as db:
            run=await self._lock(db,run_id,lease)
            rows=list((await db.scalars(self._query(run.source_scope).order_by(MemoryIdentity.id))).all())
            items=list((await db.scalars(select(MemoryBackfillItem).where(MemoryBackfillItem.run_id==run_id))).all())
            by_id={i.identity_id:i for i in items}; changed=[]
            for row in rows:
                item=by_id.get(row.id)
                if (not item or item.current_generation!=row.generation or
                    (row.source_state=='live' and item.content_digest!=row.body_hash) or item.reconcile_state!='matched'
                    or row.inflight_operation_id):changed.append(row.id)
            extras=set(by_id)-{r.id for r in rows}
            run.source_class_counts=dict(Counter(i.source_class for i in items));run.reconcile_counts=dict(Counter(i.reconcile_state for i in items))
            run.reconcile_counts['extra']=len(extras);run.unresolved_count=len(changed)+len(extras)
            run.total_source_ids=len(rows) if run.total_known else None
            # Environment lock serializes every joined writer. Digest closes all
            # current identities, body hashes and revisions at this exact cutoff.
            if not changed and not extras:
                run.cutoff={'at':self.clock().isoformat()+'Z','catalog_digest':_hash([
                    [r.id,r.generation,r.body_hash.hex() if r.body_hash else None,r.revision,r.source_state] for r in rows]).hex(),
                    'identity_high_water':max((r.id for r in rows),default=0),'epoch':self.worker.target_epoch}
                run.report_complete=True;run.execution_state='completed';run.ended_at=self.clock()
                run.stage='catchup';run.lease_owner=None;run.lease_until=None
            else:
                run.stage='catchup';run.checkpoint_summary={'after_id':0,'pass':(run.checkpoint_summary or {}).get('pass',0)+1}
            run.revision+=1;await db.commit();return not changed and not extras

    async def resume(self,run_id,*,max_items=None,rate_per_second=20):
        if not 0<rate_per_second<=100:raise ValueError('rate_out_of_range')
        lease=await self._acquire(run_id)
        if lease is None:return await self.read(run_id)
        heartbeat=asyncio.create_task(self._renew(run_id,lease));count=0;interrupted=False
        try:
            for _ in range(self.MAX_PASSES):
                async with self.sessions() as db:
                    run=await self._lock(db,run_id,lease)
                    after=(run.checkpoint_summary or {}).get('after_id',0)
                    rows=list((await db.scalars(self._query(run.source_scope).where(MemoryIdentity.id>after).order_by(MemoryIdentity.id))).all())
                for row in rows:
                    await self._observe(run_id,lease,row);count+=1
                    if max_items is not None and count>=max_items:
                        interrupted=True;break
                    await asyncio.sleep(1/rate_per_second)
                if interrupted or await self._reconcile(run_id,lease):break
        finally:
            heartbeat.cancel()
            try:await heartbeat
            except asyncio.CancelledError:pass
            async with self.sessions() as db:
                run=await self._lock(db,run_id)
                if run.lease_owner==self.worker_id and run.lease_version==lease:
                    run.lease_owner=None;run.lease_until=None
                    run.execution_state='manual_required' if run.unresolved_count else 'interrupted'
                    await db.commit()
        return await self.read(run_id)

    async def read(self,run_id):
        async with self.sessions() as db:
            row=await db.get(MemoryBackfillRun,run_id)
            if not row:return None
            names=('run_id','mode','source_scope','execution_state','stage','baseline','high_water','checkpoint_summary','cutoff',
                'scanned_records','unique_source_ids','attempt_count','source_class_counts','reconcile_counts','unresolved_count',
                'report_complete','total_known','total_source_ids','revision')
            result={k:getattr(row,k) for k in names};result['id']=row.run_id
            if row.mode=='actual':
                try:await self._verify_baseline(db,row.source_scope,row.baseline)
                except MemoryControlError:
                    result.update(report_complete=False,total_known=False,total_source_ids=None,
                        execution_state='manual_required',reason='backfill_baseline_unverified')
            result.update(index_version=row.frozen_versions['encoder_version'],encoder_version=row.frozen_versions['encoder_version'])
            for k in ('started_at','ended_at','updated_at'):result[k]=getattr(row,k).isoformat()+'Z' if getattr(row,k) else None
            return result

    async def items(self,run_id,*,after=0,limit=100):
        if not 1<=limit<=100:raise ValueError('invalid_page_size')
        async with self.sessions() as db:
            rows=(await db.execute(select(MemoryBackfillItem,MemoryIdentity).join(MemoryIdentity,MemoryBackfillItem.identity_id==MemoryIdentity.id).where(MemoryBackfillItem.run_id==run_id,
                MemoryBackfillItem.item_seq>after).order_by(MemoryBackfillItem.item_seq).limit(limit))).all()
            return [{'id':str(r.id),'run_id':r.run_id,'item_seq':r.item_seq,'source_identity':r.identity_key,
                'type':identity.memory_type,'user_id':identity.owner_user_id,'source_class':r.source_class,'current_generation':r.current_generation,
                'content_digest':r.content_digest.hex() if r.content_digest else None,'index_result':r.index_result,
                'reconcile_state':r.reconcile_state,'task_id':r.task_id,'attempt_count':r.attempt_count,
                'observed_at':r.observed_at.isoformat()+'Z','reason':r.reason} for r,identity in rows]
